"""Batch 3 — REQ-SE-001..007: 存储引擎 (Page / FileStore / BufferPool)。"""

from __future__ import annotations

import os

import pytest

from tinydb.storage import (
    FILE_HEADER_FREE_HEAD_OFFSET,
    FILE_HEADER_MAGIC,
    FILE_HEADER_PAGE_SIZE_OFFSET,
    FILE_HEADER_SIZE,
    BufferPool,
    FileStore,
    Page,
    PageType,
    _unpack_header,
    alloc_page,
    free_page,
    fsync,
    pack_header,
    write_page,
)


def test_page_header_roundtrip() -> None:
    """Page 头部 round-trip 精确（REQ-SE-003）。"""
    raw = pack_header(page_id=7, page_type=PageType.TABLE, lsn=42, body_len=100)
    assert len(raw) == FILE_HEADER_SIZE
    page_id, page_type, lsn, body_len = _unpack_header(raw)
    assert page_id == 7
    assert page_type is PageType.TABLE
    assert lsn == 42
    assert body_len == 100


def test_page_type_constants() -> None:
    """页类型常量值与 spec 一致。"""
    assert PageType.FREE.value == 0
    assert PageType.HEADER.value == 1
    assert PageType.TABLE.value == 2
    assert PageType.INDEX.value == 3
    assert PageType.OVERFLOW.value == 4


def test_file_header_magic_layout() -> None:
    """文件头 0..7 字节是魔数，8..11 字节是 page_size u32。"""
    assert len(FILE_HEADER_MAGIC) == 8
    assert FILE_HEADER_PAGE_SIZE_OFFSET == 8
    assert FILE_HEADER_FREE_HEAD_OFFSET == 12


def test_open_creates_header_page(tmp_path) -> None:
    """新文件 open 后分配 1 个 header page，page_size 默认 4096（REQ-SE-001）。"""
    store = FileStore.open(tmp_path / "test.db")
    try:
        assert store.page_size == 4096
        assert store.page_count >= 1
        header = store.read_page(0)
        assert header.page_type is PageType.HEADER
    finally:
        store.close()


def test_open_custom_page_size(tmp_path) -> None:
    """自定义 page_size=8192 被记录到文件头（REQ-SE-001）。"""
    store = FileStore.open(tmp_path / "test.db", page_size=8192)
    try:
        assert store.page_size == 8192
    finally:
        store.close()


def test_open_page_size_out_of_range(tmp_path) -> None:
    """page_size 超出 [512, 65536] 范围应拒绝。"""
    with pytest.raises(ValueError):
        FileStore.open(tmp_path / "bad.db", page_size=256)
    with pytest.raises(ValueError):
        FileStore.open(tmp_path / "bad.db", page_size=100_000)


def test_write_then_read_roundtrip(tmp_path) -> None:
    """写入一页后读回一致（REQ-SE-002）。"""
    store = FileStore.open(tmp_path / "test.db")
    try:
        pid = alloc_page(store, PageType.TABLE)
        page = Page(page_id=pid, page_type=PageType.TABLE, lsn=1, body=b"\x01\x02\x03")
        write_page(store, page)
        read = store.read_page(pid)
        assert read.page_id == pid
        assert read.page_type is PageType.TABLE
        assert read.body == b"\x01\x02\x03"
    finally:
        store.close()


def test_data_survives_close_and_reopen(tmp_path) -> None:
    """数据在 close 后重新打开仍然存在（REQ-SE-002）。"""
    path = tmp_path / "test.db"
    store = FileStore.open(path)
    pid = alloc_page(store, PageType.TABLE)
    write_page(store, Page(page_id=pid, page_type=PageType.TABLE, lsn=1, body=b"hello"))
    store.close()

    store2 = FileStore.open(path)
    try:
        page = store2.read_page(pid)
        assert page.body == b"hello"
    finally:
        store2.close()


def test_lru_evicts_unpinned(tmp_path) -> None:
    """LRU 在满时驱逐 unpinned 页（REQ-SE-004）。"""
    store = FileStore.open(tmp_path / "test.db")
    try:
        pool = BufferPool(store, capacity=2)
        p1 = alloc_page(store, PageType.TABLE)
        p2 = alloc_page(store, PageType.TABLE)
        p3 = alloc_page(store, PageType.TABLE)
        pool.get(p1)
        pool.get(p2)
        assert pool._has(p1) and pool._has(p2)
        pool.get(p3)  # 触发驱逐
        assert pool._has(p3)
        assert not (pool._has(p1) and pool._has(p2))
    finally:
        store.close()


def test_pinned_pages_never_evicted(tmp_path) -> None:
    """pinned 页不会被驱逐（REQ-SE-004）。"""
    store = FileStore.open(tmp_path / "test.db")
    try:
        pool = BufferPool(store, capacity=2)
        p1 = alloc_page(store, PageType.TABLE)
        p2 = alloc_page(store, PageType.TABLE)
        p3 = alloc_page(store, PageType.TABLE)
        handle = pool.get(p1)
        handle.pin()
        pool.get(p2)
        pool.get(p3)  # 应该驱逐 p2 而不是 p1
        assert pool._has(p1)
        assert not pool._has(p2)
        handle.unpin()
    finally:
        store.close()


def test_dirty_pages_flushed_on_evict(tmp_path) -> None:
    """驱逐脏页前先写回磁盘（REQ-SE-004）。"""
    store = FileStore.open(tmp_path / "test.db")
    try:
        pool = BufferPool(store, capacity=1)
        p1 = alloc_page(store, PageType.TABLE)
        p2 = alloc_page(store, PageType.TABLE)
        h1 = pool.get(p1)
        h1.mark_dirty()
        h1.page.body = b"dirty-data"
        h1.unpin()
        pool.get(p2)  # 驱逐 p1
        # 磁盘上的 p1 应该是 dirty-data
        raw_page = store.read_page(p1)
        assert raw_page.body == b"dirty-data"
    finally:
        store.close()


def test_alloc_returns_distinct_ids(tmp_path) -> None:
    """alloc 返回不重复的 page_id（REQ-SE-005）。"""
    store = FileStore.open(tmp_path / "test.db")
    try:
        ids = [alloc_page(store, PageType.TABLE) for _ in range(5)]
        assert len(set(ids)) == 5
    finally:
        store.close()


def test_free_then_alloc_reuses_id(tmp_path) -> None:
    """释放的 page_id 被 LIFO 复用（REQ-SE-005）。"""
    store = FileStore.open(tmp_path / "test.db")
    try:
        p1 = alloc_page(store, PageType.TABLE)
        p2 = alloc_page(store, PageType.TABLE)
        free_page(store, p2)
        p3 = alloc_page(store, PageType.TABLE)
        assert p3 == p2  # LIFO 复用
        free_page(store, p1)
        p4 = alloc_page(store, PageType.TABLE)
        assert p4 == p1
    finally:
        store.close()


def test_fsync_persists(tmp_path) -> None:
    """fsync 后数据落盘（REQ-SE-006）。"""
    path = tmp_path / "test.db"
    store = FileStore.open(path)
    try:
        pid = alloc_page(store, PageType.TABLE)
        write_page(store, Page(page_id=pid, page_type=PageType.TABLE, lsn=1, body=b"fsync-me"))
        fsync(store)
    finally:
        store.close()
    # 重新打开验证
    store2 = FileStore.open(path)
    try:
        assert store2.read_page(pid).body == b"fsync-me"
    finally:
        store2.close()


def test_replay_runs_on_open_when_wal_exists(tmp_path) -> None:
    """存在 WAL 时 open 自动 replay（REQ-SE-007）。"""
    pytest.importorskip("tinydb.wal")
    from tinydb import tx as tx_module

    if not hasattr(tx_module, "TxManager"):
        pytest.skip("TxManager 在 Batch 4 实现")
    from tinydb.tx import TxManager
    from tinydb.wal import Wal

    path = tmp_path / "test.db"
    # 先创建 db + WAL
    store = FileStore.open(path)
    wal = Wal.open(str(path) + "-wal")
    pool = BufferPool(store, capacity=8)
    tx = TxManager(store, pool, wal)
    tx.begin()
    pid = alloc_page(store, PageType.TABLE)
    write_page(store, Page(page_id=pid, page_type=PageType.TABLE, lsn=1, body=b"committed"))
    tx.commit(1)
    wal.fsync()
    wal.close()
    store.close()

    # 重新打开应该触发 replay
    store2 = FileStore.open(path)
    try:
        assert store2.read_page(pid).body == b"committed"
    finally:
        store2.close()


def test_no_wal_is_noop(tmp_path) -> None:
    """没有 WAL 文件时 open 不调用 WAL 模块（REQ-SE-007）。"""
    path = tmp_path / "test.db"
    store = FileStore.open(path)
    try:
        assert not os.path.exists(str(path) + "-wal")
        # 正常打开即可，不抛错
        assert store.page_size == 4096
    finally:
        store.close()


def test_storage_has_all() -> None:
    """storage 模块声明 __all__。"""
    from tinydb import storage

    assert "FileStore" in storage.__all__
    assert "BufferPool" in storage.__all__
    assert "PageType" in storage.__all__
