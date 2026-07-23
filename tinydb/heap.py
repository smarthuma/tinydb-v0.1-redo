"""堆访问层：行追加 / 扫描 / 删除 / 原地更新（REWRITE-PENDING 2.2, REQ-QE-004）。

单页 TABLE 堆：页 body 为 `[row_count u16][row_length u32][row_bytes...]` 的连续布局。
每行带删除标记字节（0=存活，1=删除），更新原地覆盖（要求新行长度 <= 旧行长度）。
"""

from __future__ import annotations

import struct

from tinydb.row_layout import decode_row, decode_rowid, encode_row
from tinydb.storage import FileStore, fsync
from tinydb.types import ColumnType

_COUNT_STRUCT = struct.Struct("<H")
_ROW_LEN_STRUCT = struct.Struct("<I")
_DELETED_FLAG_SIZE = 1
_ALIVE = b"\x00"


class Heap:
    """基于单页 TABLE 的堆。

    行格式：``[row_length u32][deleted u1][row_data]``，``row_length`` 仅计 ``row_data``
    （不含 deleted 标志），``row_data`` 由 ``encode_row`` 产出（内部已含
    ``[rowid u64][col_count u16][values...]``）。
    """

    def __init__(
        self,
        store: FileStore,
        root_page_id: int,
        schema: list[tuple[str, ColumnType]],
    ) -> None:
        self._store = store
        self._root_page_id = root_page_id
        self._schema = schema

    def close(self) -> None:
        """刷盘关闭。"""
        fsync(self._store)

    def _read_count(self, body: bytes) -> tuple[int, bytes]:
        """读取行计数；空 body 返回 (0, b"")。"""
        if len(body) < _COUNT_STRUCT.size:
            return 0, b""
        return _COUNT_STRUCT.unpack(body[: _COUNT_STRUCT.size])[0], body

    def append(self, values: tuple[object, ...]) -> int:
        """追加一行，返回 rowid（= 行序号，从 1 开始）。"""
        page = self._store.read_page(self._root_page_id)
        count, body = self._read_count(page.body)
        rowid = count + 1
        row_data = self._encode_row_with_rowid(rowid, values)
        row_len = len(row_data) + _DELETED_FLAG_SIZE
        new_body = (
            _COUNT_STRUCT.pack(count + 1)
            + body[_COUNT_STRUCT.size :]
            + _ROW_LEN_STRUCT.pack(row_len)
            + _ALIVE
            + row_data
        )
        page.body = new_body
        self._store.write_page(page)
        return rowid

    def scan(self) -> list[tuple[int, tuple[object, ...]]]:
        """扫描所有存活行。"""
        page = self._store.read_page(self._root_page_id)
        count, body = self._read_count(page.body)
        offset = _COUNT_STRUCT.size
        rows: list[tuple[int, tuple[object, ...]]] = []
        for _ in range(count):
            row_len = _ROW_LEN_STRUCT.unpack(
                body[offset : offset + _ROW_LEN_STRUCT.size]
            )[0]
            offset += _ROW_LEN_STRUCT.size
            row_bytes = body[offset : offset + row_len]
            offset += row_len
            deleted = row_bytes[:_DELETED_FLAG_SIZE]
            row_bytes = row_bytes[_DELETED_FLAG_SIZE:]
            if deleted == _ALIVE:
                rowid = decode_rowid(row_bytes)
                values = decode_row(row_bytes, self._schema)
                rows.append((rowid, values))
        return rows

    def delete(self, rowid: int) -> None:
        """标记删除指定 rowid 的行。"""
        page = self._store.read_page(self._root_page_id)
        body = bytearray(page.body)
        count = _COUNT_STRUCT.unpack(body[: _COUNT_STRUCT.size])[0]
        offset = _COUNT_STRUCT.size
        for _ in range(count):
            row_len = _ROW_LEN_STRUCT.unpack(
                body[offset : offset + _ROW_LEN_STRUCT.size]
            )[0]
            offset += _ROW_LEN_STRUCT.size
            row_bytes = bytes(body[offset : offset + row_len])
            offset += row_len
            row_data = row_bytes[_DELETED_FLAG_SIZE:]
            if decode_rowid(row_data) == rowid:
                body[offset - row_len] = 1  # 标记删除
                page.body = bytes(body)
                self._store.write_page(page)
                return

    def update(self, rowid: int, values: tuple[object, ...]) -> None:
        """原地更新；若新行更长则标记旧行删除并追加新行。"""
        page = self._store.read_page(self._root_page_id)
        body = bytearray(page.body)
        count = _COUNT_STRUCT.unpack(body[: _COUNT_STRUCT.size])[0]
        offset = _COUNT_STRUCT.size
        for _ in range(count):
            row_len_offset = offset
            row_len = _ROW_LEN_STRUCT.unpack(
                body[offset : offset + _ROW_LEN_STRUCT.size]
            )[0]
            offset += _ROW_LEN_STRUCT.size
            row_bytes = bytes(body[offset : offset + row_len])
            offset += row_len
            row_data = row_bytes[_DELETED_FLAG_SIZE:]
            if decode_rowid(row_data) == rowid:
                new_row_data = self._encode_row_with_rowid(rowid, values)
                new_len = len(new_row_data)
                if new_len <= len(row_data):
                    # 原地更新：保持原 row_len 不变，不足部分补零
                    body[row_len_offset : row_len_offset + _ROW_LEN_STRUCT.size] = (
                        _ROW_LEN_STRUCT.pack(len(row_bytes))
                    )
                    start = row_len_offset + _ROW_LEN_STRUCT.size
                    body[start : start + _DELETED_FLAG_SIZE] = _ALIVE
                    body[start + _DELETED_FLAG_SIZE :
                         start + _DELETED_FLAG_SIZE + new_len] = new_row_data
                    # 清零尾部残留
                    pad_start = start + _DELETED_FLAG_SIZE + new_len
                    pad_end = start + len(row_bytes)
                    body[pad_start:pad_end] = b"\x00" * (pad_end - pad_start)
                else:
                    # 溢出：标记删除 + 追加（保持相同 rowid）
                    start = row_len_offset + _ROW_LEN_STRUCT.size
                    body[start] = 1
                    extra = (
                        _ROW_LEN_STRUCT.pack(new_len + _DELETED_FLAG_SIZE)
                        + _ALIVE
                        + new_row_data
                    )
                    body.extend(extra)
                    body[: _COUNT_STRUCT.size] = _COUNT_STRUCT.pack(count + 1)
                page.body = bytes(body)
                self._store.write_page(page)
                return

    def _encode_row_with_rowid(
        self, rowid: int, values: tuple[object, ...]
    ) -> bytes:
        """编码一行：encode_row 内部 rowid 占位为 0，这里直接调用。"""
        return encode_row(values, self._schema, rowid=rowid)


__all__: list[str] = [
    "Heap",
]
