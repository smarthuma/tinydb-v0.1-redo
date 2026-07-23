"""Catalog 执行：create_table / drop_table / get_table / list_tables（D5, REQ-QE-001/002）。"""

from __future__ import annotations

from dataclasses import replace

from tinydb.catalog_codec import TableMeta, decode_catalog, encode_catalog
from tinydb.storage import FILE_HEADER_SIZE, FileStore, PageType, alloc_page, free_page, fsync
from tinydb.types import ColumnType

# catalog 存储在文件头页（page 0）body 的尾部，前缀 4 字节存 catalog body 长度
_CATALOG_OFFSET = FILE_HEADER_SIZE


class Catalog:
    """表目录：维护 table_name → TableMeta 映射。"""

    def __init__(self, store: FileStore) -> None:
        self._store = store
        self._entries: dict[str, TableMeta] = {}
        self._load()

    def _load(self) -> None:
        """从文件头页 body 加载 catalog。"""
        if self._store.page_count < 1:
            return
        page = self._store.read_page(0)
        body = page.body
        if len(body) < _CATALOG_OFFSET:
            return
        cat_len = int.from_bytes(body[_CATALOG_OFFSET : _CATALOG_OFFSET + 4], "little")
        if cat_len == 0:
            return
        cat_raw = body[_CATALOG_OFFSET + 4 : _CATALOG_OFFSET + 4 + cat_len]
        if not cat_raw:
            return
        entries = decode_catalog(cat_raw)
        self._entries = {e.name: e for e in entries}

    def _flush(self) -> None:
        """写回 catalog 到文件头页 body（dataclasses.replace 保证不可变）。"""
        raw = encode_catalog(list(self._entries.values()))
        page = self._store.read_page(0)
        body = bytearray(page.body)
        # 确保 body 足够长
        needed = _CATALOG_OFFSET + 4 + len(raw)
        if len(body) < needed:
            body.extend(b"\x00" * (needed - len(body)))
        # 写 catalog 长度 + 数据
        body[_CATALOG_OFFSET : _CATALOG_OFFSET + 4] = len(raw).to_bytes(4, "little")
        body[_CATALOG_OFFSET + 4 : _CATALOG_OFFSET + 4 + len(raw)] = raw
        page.body = bytes(body)
        self._store.write_page(page)
        fsync(self._store)

    def create_table(
        self,
        name: str,
        columns: list[tuple[str, ColumnType]],
    ) -> None:
        """创建表：分配数据页 + 写入 catalog。"""
        if name in self._entries:
            from tinydb.errors import UniqueViolation

            raise UniqueViolation(column="TABLE_NAME", table=name, value=name)
        root_page_id = alloc_page(self._store, PageType.TABLE)
        schema = [(col_name, col_type) for col_name, col_type in columns]
        meta = TableMeta(name=name, root_page_id=root_page_id, schema=schema)
        self._entries[name] = meta
        self._flush()

    def drop_table(self, name: str) -> None:
        """删除表：释放数据页 + 移除 catalog。"""
        from tinydb.errors import TableNotFound

        if name not in self._entries:
            raise TableNotFound(table=name)
        meta = self._entries.pop(name)
        free_page(self._store, meta.root_page_id)
        self._flush()

    def get_table(self, name: str) -> TableMeta:
        """获取表元数据。"""
        from tinydb.errors import TableNotFound

        if name not in self._entries:
            raise TableNotFound(table=name)
        return self._entries[name]

    def list_tables(self) -> list[str]:
        """列出所有表名。"""
        return list(self._entries.keys())

    def replace_meta(self, meta: TableMeta) -> None:
        """用新 meta 替换（dataclasses.replace 保证不可变）。"""
        self._entries[meta.name] = replace(meta)
        self._flush()


__all__: list[str] = ["Catalog"]
