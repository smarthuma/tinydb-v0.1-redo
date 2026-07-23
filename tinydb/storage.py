"""定长页、文件存储与 LRU 缓冲池（REQ-SE-001..007）。"""

from __future__ import annotations

import os
import struct
from collections.abc import Iterator
from dataclasses import dataclass
from enum import IntEnum

FILE_HEADER_SIZE = 11  # u32 page_id + u8 page_type + u32 lsn + u16 body_len
FILE_HEADER_MAGIC = b"TINYDB\x00\x00"
FILE_HEADER_PAGE_SIZE_OFFSET = 8  # body offset
FILE_HEADER_FREE_HEAD_OFFSET = 12  # body offset
_PAGE_HEADER_STRUCT = struct.Struct("<I B I H")  # page_id, page_type, lsn, body_len
_FILE_META_STRUCT = struct.Struct("<8s I I")  # magic, page_size, free_head


class PageType(IntEnum):
    """页类型（REQ-SE-003）。"""

    FREE = 0
    HEADER = 1
    TABLE = 2
    INDEX = 3
    OVERFLOW = 4


@dataclass
class Page:
    """定长页（头部在序列化时产生，不占 body）。"""

    page_id: int
    page_type: PageType
    lsn: int
    body: bytes = b""


@dataclass
class _PoolEntry:
    """缓冲池内部条目。"""

    page: Page
    dirty: bool = False
    pins: int = 0


BAD_PAGE = Page(page_id=~0, page_type=PageType.FREE, lsn=0, body=b"")


def pack_header(page_id: int, page_type: PageType, lsn: int, body_len: int) -> bytes:
    """序列化页头部（REQ-SE-003）。"""
    return _PAGE_HEADER_STRUCT.pack(page_id, int(page_type), lsn, body_len)


def _unpack_header(raw: bytes) -> tuple[int, PageType, int, int]:
    """反序列化页头部（REQ-SE-003）。"""
    page_id, page_type_value, lsn, body_len = _PAGE_HEADER_STRUCT.unpack(
        raw[:FILE_HEADER_SIZE]
    )
    return page_id, PageType(page_type_value), lsn, body_len


class FileStore:
    """单文件定长页存储（REQ-SE-001,002）。"""

    PAGE_SIZE_MIN = 512
    PAGE_SIZE_MAX = 65536
    DEFAULT_PAGE_SIZE = 4096

    def __init__(
        self,
        fd: int,
        page_size: int,
        page_count: int,
        free_head: int,
    ) -> None:
        self._fd = fd
        self.page_size = page_size
        self.page_count = page_count
        self._free_head = free_head

    @classmethod
    def open(cls, path: str | os.PathLike[str], page_size: int = 4096) -> FileStore:
        """打开或创建数据库文件。"""
        if not (cls.PAGE_SIZE_MIN <= page_size <= cls.PAGE_SIZE_MAX):
            raise ValueError(
                f"page_size must be in [{cls.PAGE_SIZE_MIN}, {cls.PAGE_SIZE_MAX}], "
                f"got {page_size}"
            )
        path_str = os.fspath(path)
        fd = os.open(path_str, os.O_RDWR | os.O_CREAT, 0o644)
        try:
            size = os.lseek(fd, 0, os.SEEK_END)
            if size == 0:
                # 新文件：写 header page
                page_count = 1
                free_head = 0
                header_body = _FILE_META_STRUCT.pack(
                    FILE_HEADER_MAGIC, page_size, free_head
                )
                header_raw = pack_header(0, PageType.HEADER, 0, len(header_body)) + _pad_body(
                    header_body, page_size
                )
                os.write(fd, header_raw)
            else:
                # 已有文件：读 header page body
                os.lseek(fd, 0, os.SEEK_SET)
                raw = os.read(fd, page_size)
                page_id, page_type, lsn, _body_len = _unpack_header(raw)
                if page_type is not PageType.HEADER:
                    raise RuntimeError(f"corrupt header page: page_type={page_type}")
                body = raw[FILE_HEADER_SIZE:]
                magic, read_page_size, free_head = _FILE_META_STRUCT.unpack(
                    body[: _FILE_META_STRUCT.size]
                )
                if magic != FILE_HEADER_MAGIC:
                    raise RuntimeError("bad file magic")
                if read_page_size != page_size:
                    raise RuntimeError(
                        f"page_size mismatch: file={read_page_size} arg={page_size}"
                    )
                page_count = size // page_size
        except BaseException:
            os.close(fd)
            raise
        store = cls(fd, page_size, page_count, free_head)
        store._maybe_replay_wal(path_str)
        return store

    def close(self) -> None:
        """关闭文件描述符并刷盘。"""
        if self._fd >= 0:
            self._flush_free_head()
            os.fsync(self._fd)
            os.close(self._fd)
            self._fd = -1

    def read_page(self, page_id: int) -> Page:
        """读取一页（REQ-SE-002）。"""
        raw = self._raw_read(page_id)
        pid, page_type, lsn, body_len = _unpack_header(raw)
        return Page(
            page_id=pid,
            page_type=page_type,
            lsn=lsn,
            body=raw[FILE_HEADER_SIZE : FILE_HEADER_SIZE + body_len],
        )

    def write_page(self, page: Page) -> None:
        """写入一页（REQ-SE-002）。"""
        raw = pack_header(page.page_id, page.page_type, page.lsn, len(page.body)) + _pad_body(
            page.body, self.page_size
        )
        os.pwrite(self._fd, raw, page.page_id * self.page_size)

    def _raw_read(self, page_id: int) -> bytes:
        return os.pread(self._fd, self.page_size, page_id * self.page_size)

    def _flush_free_head(self) -> None:
        """把内存中的 free_head 写回 header page body。"""
        header_body = _FILE_META_STRUCT.pack(
            FILE_HEADER_MAGIC, self.page_size, self._free_head
        )
        raw = pack_header(0, PageType.HEADER, 0, len(header_body)) + _pad_body(
            header_body, self.page_size
        )
        os.pwrite(self._fd, raw, 0)

    def _maybe_replay_wal(self, path_str: str) -> None:
        """存在 WAL 时触发 replay（REQ-SE-007）。"""
        wal_path = path_str + "-wal"
        if not os.path.exists(wal_path):
            return
        # WAL 模块在 Batch 4 提供；延迟导入避免循环依赖
        try:
            from tinydb.wal import replay_wal
        except ImportError:
            return
        replay_wal(wal_path, self)

    def __enter__(self) -> FileStore:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()


def _pad_body(body: bytes, page_size: int) -> bytes:
    """将 body 填充/截断到 page_size - FILE_HEADER_SIZE。"""
    body_size = page_size - FILE_HEADER_SIZE
    if len(body) >= body_size:
        return body[:body_size]
    return body + b"\x00" * (body_size - len(body))


class BufferPool:
    """LRU 缓冲池（REQ-SE-004）。"""

    def __init__(self, store: FileStore, capacity: int) -> None:
        self._store = store
        self._capacity = capacity
        self._entries: dict[int, _PoolEntry] = {}

    def get(self, page_id: int) -> PageHandle:
        """获取一页；若不在池中则加载，满时驱逐 LRU unpinned 页。"""
        if page_id in self._entries:
            entry = self._entries[page_id]
        else:
            self._evict_if_full()
            page = self._store.read_page(page_id)
            entry = _PoolEntry(page=page)
            self._entries[page_id] = entry
        handle = PageHandle(entry)
        return handle

    def put(self, page: Page) -> PageHandle:
        """显式把页放入池（标记为脏）。"""
        self._evict_if_full()
        entry = _PoolEntry(page=page, dirty=True)
        self._entries[page.page_id] = entry
        return PageHandle(entry)

    def flush_all(self) -> None:
        """把所有脏页写回磁盘。"""
        for entry in self._entries.values():
            if entry.dirty:
                self._store.write_page(entry.page)
                entry.dirty = False

    def _evict_if_full(self) -> None:
        if len(self._entries) < self._capacity:
            return
        # 驱逐 LRU（dict 插入顺序）中第一个 unpinned 页
        for pid, entry in list(self._entries.items()):
            if entry.pins == 0:
                if entry.dirty:
                    self._store.write_page(entry.page)
                del self._entries[pid]
                return
        raise RuntimeError("buffer pool full: all pages pinned")

    def _has(self, page_id: int) -> bool:
        return page_id in self._entries

    def __iter__(self) -> Iterator[Page]:
        return iter(entry.page for entry in self._entries.values())


class PageHandle:
    """页访问句柄，支持 pin/unpin 与脏标记。"""

    def __init__(self, entry: _PoolEntry) -> None:
        self._entry = entry

    @property
    def page(self) -> Page:
        return self._entry.page

    def pin(self) -> None:
        self._entry.pins += 1

    def unpin(self) -> None:
        if self._entry.pins > 0:
            self._entry.pins -= 1

    def mark_dirty(self) -> None:
        self._entry.dirty = True


def alloc_page(store: FileStore, page_type: PageType) -> int:
    """分配一页，优先从空闲链 LIFO 复用（REQ-SE-005）。"""
    if store._free_head != 0:
        pid = store._free_head
        raw = store._raw_read(pid)
        # 空闲链的"下一页"存在 body 前 4 字节
        store._free_head = struct.unpack("<I", raw[FILE_HEADER_SIZE : FILE_HEADER_SIZE + 4])[0]
        page = Page(page_id=pid, page_type=page_type, lsn=0, body=b"")
        store.write_page(page)
        return pid
    # 没有空闲页，扩展文件
    pid = store.page_count
    store.page_count += 1
    page = Page(page_id=pid, page_type=page_type, lsn=0, body=b"")
    store.write_page(page)
    return pid


def free_page(store: FileStore, page_id: int) -> None:
    """释放一页到空闲链头部（REQ-SE-005）。"""
    if page_id == 0:
        raise ValueError("cannot free header page")
    # 把旧的 free_head 写入该页 body 前 4 字节
    next_head = struct.pack("<I", store._free_head)
    raw = pack_header(page_id, PageType.FREE, 0, len(next_head)) + _pad_body(
        next_head, store.page_size
    )
    os.pwrite(store._fd, raw, page_id * store.page_size)
    store._free_head = page_id


def read_page(store: FileStore, page_id: int) -> Page:
    """模块级便捷函数。"""
    return store.read_page(page_id)


def write_page(store: FileStore, page: Page) -> None:
    """模块级便捷函数。"""
    store.write_page(page)


def fsync(store: FileStore) -> None:
    """显式 fsync 落盘（REQ-SE-006）。"""
    os.fsync(store._fd)


__all__: list[str] = [
    "BAD_PAGE",
    "BufferPool",
    "FILE_HEADER_FREE_HEAD_OFFSET",
    "FILE_HEADER_MAGIC",
    "FILE_HEADER_PAGE_SIZE_OFFSET",
    "FILE_HEADER_SIZE",
    "FileStore",
    "Page",
    "PageHandle",
    "PageType",
    "_unpack_header",
    "alloc_page",
    "free_page",
    "fsync",
    "pack_header",
    "read_page",
    "write_page",
]
