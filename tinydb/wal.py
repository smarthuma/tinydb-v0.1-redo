"""预写式日志：记录编解码、append、fsync、replay、truncate（D4, REQ-TM-004/005）。"""

from __future__ import annotations

import os
import struct
import zlib
from collections.abc import Iterator
from dataclasses import dataclass
from enum import IntEnum
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from tinydb.storage import Page

MAGIC = b"TINYWAL1"
MAGIC_SIZE = len(MAGIC)
# post-magic header: length(u32) + crc32(u4)
_WAL_POST_MAGIC_STRUCT = struct.Struct("<I I")
_WAL_POST_MAGIC_SIZE = _WAL_POST_MAGIC_STRUCT.size
_RECORD_HEADER_STRUCT = struct.Struct("<I B I H")  # lsn, kind, tx_id, page_id
_RECORD_BODY_LEN_STRUCT = struct.Struct("<H H")  # before_len, after_len
_CHECKSUM_STRUCT = struct.Struct("<I")


class RecordKind(IntEnum):
    """WAL 记录类型。"""

    MUTATE = 1
    TX_COMMIT = 2
    TX_ROLLBACK = 3


MUTATE = RecordKind.MUTATE
TX_COMMIT = RecordKind.TX_COMMIT
TX_ROLLBACK = RecordKind.TX_ROLLBACK


@dataclass
class WalRecord:
    """一条 WAL 记录。"""

    lsn: int
    tx_id: int
    kind: RecordKind
    page_id: int = 0
    before: bytes = b""
    after: bytes = b""


def encode_record(rec: WalRecord) -> bytes:
    """编码一条记录，附 CRC32 校验和（D4）。"""
    body = _RECORD_HEADER_STRUCT.pack(
        rec.lsn, int(rec.kind), rec.tx_id, rec.page_id
    )
    body += _RECORD_BODY_LEN_STRUCT.pack(len(rec.before), len(rec.after))
    body += rec.before + rec.after
    crc = zlib.crc32(body) & 0xFFFFFFFF
    frame = MAGIC + _WAL_POST_MAGIC_STRUCT.pack(len(body) + _CHECKSUM_STRUCT.size, crc)
    frame += body
    frame += _CHECKSUM_STRUCT.pack(crc)
    return frame


def decode_record(raw: bytes) -> WalRecord:
    """解码一条记录，校验失败抛出 TransactionLogCorrupt（D4）。"""
    from tinydb.errors import TransactionLogCorrupt

    header_size = MAGIC_SIZE + _WAL_POST_MAGIC_SIZE
    if len(raw) < header_size:
        raise TransactionLogCorrupt(offset=0)
    magic = raw[:MAGIC_SIZE]
    if magic != MAGIC:
        raise TransactionLogCorrupt(offset=0)
    length, expected_crc = _WAL_POST_MAGIC_STRUCT.unpack(
        raw[MAGIC_SIZE:header_size]
    )
    frame_end = header_size + length
    if len(raw) < frame_end:
        raise TransactionLogCorrupt(offset=0)
    body_and_crc = raw[header_size : frame_end]
    body, stored_crc_bytes = body_and_crc[:-4], body_and_crc[-4:]
    stored_crc = _CHECKSUM_STRUCT.unpack(stored_crc_bytes)[0]
    computed_crc = zlib.crc32(body) & 0xFFFFFFFF
    if computed_crc != expected_crc or computed_crc != stored_crc:
        raise TransactionLogCorrupt(offset=0)
    lsn, kind_value, tx_id, page_id = _RECORD_HEADER_STRUCT.unpack(
        body[: _RECORD_HEADER_STRUCT.size]
    )
    body_rest = body[_RECORD_HEADER_STRUCT.size :]
    before_len, after_len = _RECORD_BODY_LEN_STRUCT.unpack(
        body_rest[: _RECORD_BODY_LEN_STRUCT.size]
    )
    payload = body_rest[_RECORD_BODY_LEN_STRUCT.size :]
    before = payload[:before_len]
    after = payload[before_len : before_len + after_len]
    return WalRecord(
        lsn=lsn,
        tx_id=tx_id,
        kind=RecordKind(kind_value),
        page_id=page_id,
        before=before,
        after=after,
    )


class Wal:
    """WAL 文件：追加写 + fsync + truncate（REQ-TM-004）。"""

    def __init__(self, fd: int) -> None:
        self._fd = fd
        self._next_lsn = self._recover_next_lsn()

    @classmethod
    def open(cls, path: str) -> Wal:
        """打开或创建 WAL 文件。"""
        fd = os.open(path, os.O_RDWR | os.O_CREAT, 0o644)
        return cls(fd)

    def close(self) -> None:
        """关闭 WAL 文件描述符。"""
        if self._fd >= 0:
            os.close(self._fd)
            self._fd = -1

    def append_rec(self, rec: WalRecord) -> int:
        """写入一条已构造的记录，返回 lsn。"""
        raw = encode_record(rec)
        os.write(self._fd, raw)
        self._next_lsn = max(self._next_lsn, rec.lsn + 1)
        return rec.lsn

    def append(
        self,
        kind: RecordKind,
        *,
        tx_id: int = 0,
        page_id: int = 0,
        before: bytes = b"",
        after: bytes = b"",
    ) -> int:
        """追加一条记录，自动分配 lsn。"""
        rec = WalRecord(
            lsn=self._next_lsn, tx_id=tx_id, kind=kind, page_id=page_id, before=before, after=after
        )
        return self.append_rec(rec)

    def fsync(self) -> None:
        """刷盘（REQ-TM-004）。"""
        os.fsync(self._fd)

    def truncate(self) -> None:
        """截断 WAL 到零长度（REQ-TM-008）。"""
        os.ftruncate(self._fd, 0)
        os.lseek(self._fd, 0, os.SEEK_SET)
        self._next_lsn = 1

    def iter_records(self) -> Iterator[WalRecord]:
        """顺序迭代所有记录。"""
        header_size = MAGIC_SIZE + _WAL_POST_MAGIC_SIZE
        size = os.lseek(self._fd, 0, os.SEEK_END)
        os.lseek(self._fd, 0, os.SEEK_SET)
        pos = 0
        while pos < size:
            raw = os.pread(self._fd, header_size, pos)
            if len(raw) < header_size:
                break
            (length, _crc) = _WAL_POST_MAGIC_STRUCT.unpack(raw[MAGIC_SIZE:header_size])
            frame_end = header_size + length
            frame = os.pread(self._fd, frame_end, pos)
            yield decode_record(frame)
            pos += frame_end

    def _recover_next_lsn(self) -> int:
        """扫描已有记录，恢复下一个 lsn。"""
        max_lsn = 0
        try:
            for rec in self._scan_records():
                max_lsn = max(max_lsn, rec.lsn)
        except Exception:
            return 1
        return max_lsn + 1 if max_lsn > 0 else 1

    def _scan_records(self) -> Iterator[WalRecord]:
        """与 iter_records 相同但以当前 fd 位置扫描。"""
        yield from self.iter_records()

    def __enter__(self) -> Wal:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()


class _ReplayStore(Protocol):
    """replay_wal 所需的存储接口。"""

    def read_page(self, page_id: int) -> Page: ...
    def write_page(self, page: Page) -> None: ...


def replay_wal(wal_path: str, store: _ReplayStore) -> None:
    """前向扫描 replay：重放已提交事务的 MUTATE（REQ-TM-005）。"""
    if not os.path.exists(wal_path):
        return
    fd = os.open(wal_path, os.O_RDONLY)
    try:
        committed_tx: set[int] = set()
        records: list[WalRecord] = []
        header_size = MAGIC_SIZE + _WAL_POST_MAGIC_SIZE
        size = os.lseek(fd, 0, os.SEEK_END)
        os.lseek(fd, 0, os.SEEK_SET)
        pos = 0
        while pos < size:
            raw = os.pread(fd, header_size, pos)
            if len(raw) < header_size:
                break
            (length, _crc) = _WAL_POST_MAGIC_STRUCT.unpack(raw[MAGIC_SIZE:header_size])
            frame = os.pread(fd, header_size + length, pos)
            rec = decode_record(frame)
            records.append(rec)
            if rec.kind is TX_COMMIT:
                committed_tx.add(rec.tx_id)
            pos += header_size + length
        # 重放 committed 的 MUTATE；undo 未提交事务的 MUTATE（恢复 before-image）
        for rec in records:
            if rec.kind is MUTATE:
                page = store.read_page(rec.page_id)
                if rec.tx_id in committed_tx:
                    page.body = rec.after
                else:
                    page.body = rec.before
                store.write_page(page)
    finally:
        os.close(fd)


__all__: list[str] = [
    "MUTATE",
    "TX_COMMIT",
    "TX_ROLLBACK",
    "Wal",
    "WalRecord",
    "decode_record",
    "encode_record",
    "replay_wal",
]
