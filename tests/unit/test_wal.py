"""Batch 4 — WAL 记录编解码 / append / replay / truncate (REQ-TM-004/005)。"""

from __future__ import annotations

import os
from collections.abc import Iterator

import pytest

from tinydb.wal import (
    MUTATE,
    TX_COMMIT,
    TX_ROLLBACK,
    Wal,
    WalRecord,
    decode_record,
    encode_record,
)


@pytest.fixture
def wal_path(tmp_path) -> Iterator[str]:
    path = str(tmp_path / "test.db-wal")
    yield path
    if os.path.exists(path):
        os.remove(path)


def test_record_roundtrip_mutation() -> None:
    """MUTATE 记录 round-trip 精确。"""
    rec = WalRecord(
        lsn=1,
        tx_id=42,
        kind=MUTATE,
        page_id=7,
        before=b"old",
        after=b"new",
    )
    raw = encode_record(rec)
    decoded = decode_record(raw)
    assert decoded.lsn == 1
    assert decoded.tx_id == 42
    assert decoded.kind is MUTATE
    assert decoded.page_id == 7
    assert decoded.before == b"old"
    assert decoded.after == b"new"


def test_record_roundtrip_commit() -> None:
    """TX_COMMIT 记录 round-trip。"""
    rec = WalRecord(lsn=2, tx_id=42, kind=TX_COMMIT)
    decoded = decode_record(encode_record(rec))
    assert decoded.kind is TX_COMMIT
    assert decoded.tx_id == 42


def test_record_roundtrip_rollback() -> None:
    """TX_ROLLBACK 记录 round-trip。"""
    rec = WalRecord(lsn=3, tx_id=42, kind=TX_ROLLBACK)
    decoded = decode_record(encode_record(rec))
    assert decoded.kind is TX_ROLLBACK


def test_corrupted_checksum_raises() -> None:
    """校验和损坏的 record 解码应抛出 TransactionLogCorrupt。"""
    from tinydb.errors import TransactionLogCorrupt

    rec = WalRecord(lsn=1, tx_id=1, kind=TX_COMMIT)
    raw = bytearray(encode_record(rec))
    raw[-1] ^= 0xFF  # 破坏最后一个 checksum 字节
    with pytest.raises(TransactionLogCorrupt):
        decode_record(bytes(raw))


def test_wal_appends_in_order(wal_path: str) -> None:
    """Wal 按顺序追加记录，返回递增 lsn。"""
    wal = Wal.open(wal_path)
    try:
        lsn1 = wal.append(MUTATE, page_id=1, before=b"a", after=b"b")
        lsn2 = wal.append(MUTATE, page_id=2, before=b"c", after=b"d")
        lsn3 = wal.append(TX_COMMIT)
        assert lsn1 < lsn2 < lsn3
    finally:
        wal.close()


def test_wal_fsync_persists(wal_path: str) -> None:
    """WAL fsync 后记录落盘。"""
    wal = Wal.open(wal_path)
    wal.append(TX_COMMIT, tx_id=1)
    wal.fsync()
    wal.close()
    assert os.path.getsize(wal_path) > 0
    # 重新打开验证可读
    wal2 = Wal.open(wal_path)
    try:
        records = list(wal2.iter_records())
        assert len(records) == 1
        assert records[0].kind is TX_COMMIT
    finally:
        wal2.close()


def test_replay_redoes_committed(tmp_path) -> None:
    """replay 重放已提交事务的写入。"""
    from tinydb.storage import FileStore, PageType, alloc_page

    db_path = str(tmp_path / "test.db")
    store = FileStore.open(db_path)
    wal_path = db_path + "-wal"
    wal = Wal.open(wal_path)
    pid = alloc_page(store, PageType.TABLE)
    # 手动写入一条 committed MUTATE 到 WAL
    wal.append_rec(
        WalRecord(
            lsn=1,
            tx_id=1,
            kind=MUTATE,
            page_id=pid,
            before=b"\x00" * (store.page_size - 11),
            after=b"committed-write",
        )
    )
    wal.append(TX_COMMIT, tx_id=1)
    wal.fsync()
    wal.close()

    # replay
    from tinydb.wal import replay_wal

    replay_wal(wal_path, store)
    store.close()

    # 验证
    store2 = FileStore.open(db_path)
    try:
        assert store2.read_page(pid).body.startswith(b"committed-write")
    finally:
        store2.close()


def test_replay_ignores_uncommitted(tmp_path) -> None:
    """replay 忽略未提交事务。"""
    from tinydb.storage import FileStore, PageType, alloc_page

    db_path = str(tmp_path / "test.db")
    store = FileStore.open(db_path)
    wal_path = db_path + "-wal"
    wal = Wal.open(wal_path)
    pid = alloc_page(store, PageType.TABLE)
    wal.append_rec(
        WalRecord(
            lsn=1,
            tx_id=99,
            kind=MUTATE,
            page_id=pid,
            before=b"\x00" * (store.page_size - 11),
            after=b"uncommitted-write",
        )
    )
    # 没有 TX_COMMIT
    wal.fsync()
    wal.close()

    from tinydb.wal import replay_wal

    replay_wal(wal_path, store)
    store.close()

    store2 = FileStore.open(db_path)
    try:
        body = store2.read_page(pid).body.rstrip(b"\x00")
        assert body != b"uncommitted-write"
    finally:
        store2.close()


def test_truncate_zeros_wal(wal_path: str) -> None:
    """truncate 后 WAL 文件归零。"""
    wal = Wal.open(wal_path)
    wal.append(TX_COMMIT)
    wal.fsync()
    assert os.path.getsize(wal_path) > 0
    wal.truncate()
    wal.close()
    assert os.path.getsize(wal_path) == 0


def test_wal_has_all() -> None:
    """wal 模块声明 __all__。"""
    from tinydb import wal

    assert "Wal" in wal.__all__
    assert "WalRecord" in wal.__all__
    assert "encode_record" in wal.__all__
    assert "decode_record" in wal.__all__
