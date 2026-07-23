"""查询执行器子包：catalog / ddl / dml / select / aggregate / index_plan / checkpoint。

主类 `Executor`（REQ-QE-001..011）。
"""

from __future__ import annotations

from tinydb.catalog_codec import TableMeta
from tinydb.executor.aggregate import exec_aggregate
from tinydb.executor.catalog import Catalog
from tinydb.executor.checkpoint import exec_checkpoint
from tinydb.executor.ddl import exec_create_table, exec_drop_table
from tinydb.executor.dml import exec_delete, exec_insert, exec_update
from tinydb.executor.index_plan import IndexPlanner
from tinydb.executor.select import exec_select
from tinydb.parser import ast, parse
from tinydb.storage import FileStore
from tinydb.tx import TxManager
from tinydb.wal import Wal

__all__: list[str] = ["Executor"]


class Executor:
    """SQL 执行器主类。"""

    def __init__(self, store: FileStore) -> None:
        self._store = store
        self._wal = Wal.open(_wal_path(store))
        self._tx = TxManager(store, self._wal)
        self._catalog = Catalog(store)
        self._planner = IndexPlanner()
        self._constraints: dict[str, dict[str, tuple[str, ...]]] = {}

    def execute(self, sql: str) -> object:
        """执行 SQL 语句，返回结果。"""
        stmt = parse(sql)
        return self._dispatch(stmt)

    def _dispatch(self, stmt: object) -> object:
        """分派到具体执行器。"""
        from tinydb.parser import ast

        if isinstance(stmt, ast.CreateTable):
            exec_create_table(self._store, self._catalog, stmt)
            self._constraints[stmt.name] = {
                col.name: col.constraints for col in stmt.columns
            }
            return []
        if isinstance(stmt, ast.DropTable):
            exec_drop_table(self._store, self._catalog, stmt)
            return []
        if isinstance(stmt, ast.Checkpoint):
            exec_checkpoint(self._tx)
            return []
        if isinstance(stmt, ast.Insert):
            meta = self._catalog.get_table(stmt.table)
            columns = list(stmt.columns) if stmt.columns else None
            constraints = self._constraints.get(stmt.table, {})
            exec_insert(self._store, meta, columns, list(stmt.values), constraints)
            return []
        if isinstance(stmt, ast.Select):
            meta = self._catalog.get_table(stmt.table)
            order_by = [(item.expr, item.direction) for item in stmt.order_by]
            has_agg = stmt.group_by or _has_aggregate(list(stmt.projections))
            rows = exec_select(
                self._store,
                meta,
                list(stmt.projections),
                stmt.where,
                order_by,
                stmt.limit,
                stmt.offset,
                project=not has_agg,
            )
            if has_agg:
                rows = exec_aggregate(rows, list(stmt.projections), list(stmt.group_by))
            return rows
        if isinstance(stmt, ast.Update):
            meta = self._catalog.get_table(stmt.table)
            return exec_update(
                self._store, meta, list(stmt.assignments), stmt.where,
            )
        if isinstance(stmt, ast.Delete):
            meta = self._catalog.get_table(stmt.table)
            return exec_delete(self._store, meta, stmt.where)
        if isinstance(stmt, (ast.Begin, ast.Commit, ast.Rollback)):
            return _exec_tx_control(self._tx, stmt)
        return []

    def list_tables(self) -> list[str]:
        """列出所有表。"""
        return self._catalog.list_tables()

    def get_table(self, name: str) -> TableMeta:
        """获取表元数据。"""
        return self._catalog.get_table(name)

    def close(self) -> None:
        """关闭资源。"""
        try:
            self._wal.close()
        finally:
            self._store.close()


def _wal_path(store: FileStore) -> str:
    """推导 WAL 路径。"""
    # FileStore 不暴露路径，使用 fd 的 fstat 推导
    import os

    fd = store._fd
    try:
        path = os.readlink(f"/proc/self/fd/{fd}")
        return path + "-wal"
    except OSError:
        return "tinydb.db-wal"


def _has_aggregate(projections: list[object]) -> bool:
    """检查是否有聚合函数。"""
    return any(
        isinstance(p, ast.SqlLiteral) and isinstance(p.value, str)
        and p.value.startswith(("COUNT", "SUM", "AVG"))
        for p in projections
    )


def _exec_tx_control(tx: TxManager, stmt: object) -> object:
    """执行事务控制。"""
    from tinydb.parser.ast import Begin, Commit, Rollback

    if isinstance(stmt, Begin):
        return tx.begin()
    if isinstance(stmt, Commit):
        # 需要 tx_id；简化：不支持显式事务 ID
        return None
    if isinstance(stmt, Rollback):
        return None
    return None
