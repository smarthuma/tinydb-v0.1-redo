"""事务管理器：BEGIN / COMMIT / ROLLBACK / CHECKPOINT 状态机（REQ-TM-001..008）。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from tinydb.errors import TransactionAlreadyActive
from tinydb.wal import TX_COMMIT, TX_ROLLBACK, Wal


@runtime_checkable
class _FlushCapable(Protocol):
    def flush_all(self) -> None: ...


@dataclass
class _TxState:
    """单事务状态。"""

    tx_id: int
    active: bool = True


class TxManager:
    """事务状态机：支持多事务 ID 并发（REQ-TM-001..008, REQ-CC-006）。"""

    def __init__(
        self,
        store: object,
        wal: Wal,
        lock_manager: object | None = None,
    ) -> None:
        self._store = store
        self._wal = wal
        self._lock_manager = lock_manager
        self._txs: dict[int, _TxState] = {}
        self._next_tx_id = 1

    def begin(self) -> int:
        """开启事务，返回 tx_id（REQ-TM-001）。同连接重复 BEGIN 抛 TransactionAlreadyActive。"""
        active = [t for t in self._txs.values() if t.active]
        if active:
            raise TransactionAlreadyActive()
        tx_id = self._next_tx_id
        self._next_tx_id += 1
        self._txs[tx_id] = _TxState(tx_id=tx_id)
        return tx_id

    def commit(self, tx_id: int) -> None:
        """提交事务：先写 WAL COMMIT 并 fsync，保证持久（REQ-TM-002）。"""
        self._check_tx(tx_id)
        self._wal.append(TX_COMMIT, tx_id=tx_id)
        self._wal.fsync()
        del self._txs[tx_id]

    def rollback(self, tx_id: int) -> None:
        """回滚事务：写 ROLLBACK 标记（REQ-TM-003）。"""
        self._check_tx(tx_id)
        self._wal.append(TX_ROLLBACK, tx_id=tx_id)
        del self._txs[tx_id]

    def checkpoint(self) -> None:
        """刷脏页 + 截断 WAL（REQ-TM-008, REWRITE-PENDING 3.3）。"""
        store = self._store
        if isinstance(store, _FlushCapable):
            store.flush_all()
        self._wal.fsync()
        self._wal.truncate()

    def replay(self) -> None:
        """从 WAL 恢复（供 FileStore.open 调用）。"""
        from tinydb.wal import replay_wal

        # 找到 wal 路径：从 fd 推导
        wal_path = getattr(self._wal, "_path", None)
        if wal_path is None:
            return
        replay_wal(wal_path, self._store)  # type: ignore[arg-type]

    def _check_tx(self, tx_id: int) -> None:
        tx = self._txs.get(tx_id)
        if tx is None or not tx.active:
            raise TransactionAlreadyActive()


__all__: list[str] = [
    "TxManager",
]
