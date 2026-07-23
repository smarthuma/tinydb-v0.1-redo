"""CHECKPOINT 执行：flush dirty pages + truncate WAL（REQ-QE-011）。"""

from __future__ import annotations

from tinydb.tx import TxManager


def exec_checkpoint(tx: TxManager) -> None:
    """执行 CHECKPOINT。"""
    tx.checkpoint()


__all__: list[str] = ["exec_checkpoint"]
