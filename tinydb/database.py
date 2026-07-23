"""Database 包装层：生命周期封装、execute()、transaction() 上下文管理器（REQ-DB-001..006）。"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from tinydb.errors import TransactionAlreadyActive
from tinydb.executor import Executor
from tinydb.parser import parse
from tinydb.storage import FileStore, fsync

__all__: list[str] = ["Database"]


class Database:
    """TinyDB 公共入口。"""

    def __init__(
        self,
        path: str | Path,
        page_size: int = 4096,
    ) -> None:
        self._path = Path(path)
        self._store: FileStore | None = None
        self._executor: Executor | None = None
        self._closed = False
        self._init_resources(page_size)

    def _init_resources(self, page_size: int) -> None:
        """初始化底层资源。"""
        try:
            self._store = FileStore.open(str(self._path), page_size=page_size)
            self._executor = Executor(self._store)
        except BaseException:
            self._cleanup()
            raise

    def _cleanup(self) -> None:
        """释放资源。"""
        if self._store is not None:
            try:
                self._store.close()
            except Exception:
                pass
            self._store = None
        self._executor = None

    def execute(self, sql: str) -> list[dict[str, object]]:
        """执行 SQL 语句。"""
        if self._closed or self._executor is None:
            raise RuntimeError("database is closed")
        stmt = parse(sql)
        result = self._executor.execute(sql)
        return _normalize_result(stmt, result)

    @contextmanager
    def transaction(self) -> Iterator[Database]:
        """事务上下文管理器（快照回滚）。"""
        if self._closed or self._executor is None:
            raise RuntimeError("database is closed")
        # 快照当前页状态用于回滚
        snapshot = self._snapshot_pages()
        try:
            self._executor._tx.begin()
        except TransactionAlreadyActive:
            raise
        try:
            yield self
            self._executor._tx.commit(1)
        except BaseException:
            self._executor._tx.rollback(1)
            self._restore_pages(snapshot)
            raise

    def _snapshot_pages(self) -> dict[int, bytes]:
        """快照所有页的 body。"""
        snapshot: dict[int, bytes] = {}
        if self._store is None:
            return snapshot
        for pid in range(self._store.page_count):
            page = self._store.read_page(pid)
            snapshot[pid] = page.body
        return snapshot

    def _restore_pages(self, snapshot: dict[int, bytes]) -> None:
        """从快照恢复页状态。"""
        if self._store is None:
            return
        for pid, body in snapshot.items():
            page = self._store.read_page(pid)
            page.body = body
            self._store.write_page(page)
        # 重建 catalog 缓存
        if self._executor is not None:
            self._executor._catalog._load()
        fsync(self._store)

    def close(self) -> None:
        """关闭数据库（幂等）。"""
        if self._closed:
            return
        self._cleanup()
        self._closed = True

    def __enter__(self) -> Database:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()


def _normalize_result(stmt: object, result: object) -> list[dict[str, object]]:
    """归一化执行结果。"""
    from tinydb.parser import ast

    if isinstance(stmt, ast.Select):
        if isinstance(result, list):
            return result
        return []
    if isinstance(stmt, ast.Insert):
        return [{"rows_affected": 1}]
    if isinstance(stmt, (ast.Update, ast.Delete)):
        if isinstance(result, int):
            return [{"rows_affected": result}]
        if isinstance(result, list) and result:
            return result
        return [{"rows_affected": 0}]
    # DDL / CHECKPOINT / TX
    return [{"status": "ok"}]
