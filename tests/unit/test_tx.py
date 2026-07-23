"""Batch 4 — T-4.4: TxManager BEGIN/COMMIT/ROLLBACK/CHECKPOINT (REQ-TM-001,002,003,006,008)。"""

from __future__ import annotations

import pytest

from tinydb.errors import TransactionAlreadyActive
from tinydb.storage import (
    FILE_HEADER_SIZE,
    FileStore,
    Page,
    PageType,
    alloc_page,
    write_page,
)
from tinydb.tx import TxManager
from tinydb.wal import MUTATE, Wal


def test_begin_returns_tx_id(tmp_path) -> None:
    """BEGIN 返回事务 id。"""
    store, pool, wal, tx = _setup(tmp_path)
    try:
        tx_id = tx.begin()
        assert tx_id >= 1
        wal.close()
    finally:
        store.close()


def test_nested_begin_raises(tmp_path) -> None:
    """重复 BEGIN 抛出 TransactionAlreadyActive（REQ-TM-006）。"""
    store, pool, wal, tx = _setup(tmp_path)
    try:
        tx.begin()
        with pytest.raises(TransactionAlreadyActive):
            tx.begin()
        wal.close()
    finally:
        store.close()


def test_commit_makes_write_visible_after_reopen(tmp_path) -> None:
    """COMMIT 后写入在重新打开后可见（REQ-TM-002）。"""
    path = str(tmp_path / "test.db")
    store = FileStore.open(path)
    wal = Wal.open(path + "-wal")
    tx = TxManager(store, wal)
    tx.begin()
    pid = alloc_page(store, PageType.TABLE)
    write_page(store, Page(page_id=pid, page_type=PageType.TABLE, lsn=1, body=b"committed"))
    tx.commit(1)
    wal.fsync()
    wal.close()
    store.close()

    store2 = FileStore.open(path)
    try:
        assert store2.read_page(pid).body == b"committed"
    finally:
        store2.close()


def test_rollback_discards_writes(tmp_path) -> None:
    """ROLLBACK 后写入不可见（REQ-TM-003）：WAL 有 before-image 可 undo。"""
    path = str(tmp_path / "test.db")
    store = FileStore.open(path)
    wal = Wal.open(path + "-wal")
    # 先写一条已提交的数据作为 baseline
    pid = alloc_page(store, PageType.TABLE)
    empty_body = b"\x00" * (store.page_size - FILE_HEADER_SIZE)
    write_page(store, Page(page_id=pid, page_type=PageType.TABLE, lsn=0, body=empty_body))
    wal.close()
    store.close()

    # 开启事务，写入 MUTATE 记录 + 修改页，然后 ROLLBACK
    store = FileStore.open(path)
    wal = Wal.open(path + "-wal")
    tx = TxManager(store, wal)
    tx.begin()
    wal.append(
        MUTATE,
        tx_id=1,
        page_id=pid,
        before=empty_body,
        after=b"rolled-back",
    )
    write_page(store, Page(page_id=pid, page_type=PageType.TABLE, lsn=1, body=b"rolled-back"))
    tx.rollback(1)
    wal.fsync()
    wal.close()
    store.close()

    # 重新打开：WAL replay 应该 undo 未提交的 MUTATE
    store2 = FileStore.open(path)
    try:
        body = store2.read_page(pid).body.rstrip(b"\x00")
        assert body != b"rolled-back"
    finally:
        store2.close()


def test_checkpoint_truncates_wal(tmp_path) -> None:
    """CHECKPOINT 后 WAL 归零（REQ-TM-008）。"""
    import os

    path = str(tmp_path / "test.db")
    store = FileStore.open(path)
    wal = Wal.open(path + "-wal")
    tx = TxManager(store, wal)
    tx.begin()
    pid = alloc_page(store, PageType.TABLE)
    write_page(store, Page(page_id=pid, page_type=PageType.TABLE, lsn=1, body=b"ckpt"))
    tx.commit(1)
    assert os.path.getsize(path + "-wal") > 0
    tx.checkpoint()
    wal.close()
    store.close()
    assert os.path.getsize(path + "-wal") == 0


def test_checkpoint_without_transaction_is_safe(tmp_path) -> None:
    """无事务时 CHECKPOINT 安全（REQ-TM-008）。"""
    path = str(tmp_path / "test.db")
    store = FileStore.open(path)
    wal = Wal.open(path + "-wal")
    tx = TxManager(store, wal)
    tx.checkpoint()  # 不应抛错
    wal.close()
    store.close()


def test_tx_has_all() -> None:
    """tx 模块声明 __all__。"""
    from tinydb import tx

    assert "TxManager" in tx.__all__


def _setup(tmp_path: object) -> tuple[FileStore, object, Wal, TxManager]:
    """构造 store + wal + tx 三元组。"""
    path = str(tmp_path / "test.db")
    store = FileStore.open(path)
    wal = Wal.open(path + "-wal")
    tx = TxManager(store, wal)
    return store, None, wal, tx
