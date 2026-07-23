"""DDL 执行：CREATE TABLE / DROP TABLE（REQ-QE-001/002）。"""

from __future__ import annotations

from tinydb.executor.catalog import Catalog
from tinydb.parser import ast
from tinydb.storage import FileStore
from tinydb.types import ColumnType

_TYPE_MAP = {ct.value: ct for ct in ColumnType}


def exec_create_table(
    store: FileStore, catalog: Catalog, stmt: ast.CreateTable,
) -> None:
    """执行 CREATE TABLE。"""
    columns = []
    for col_def in stmt.columns:
        col_type = _TYPE_MAP.get(col_def.col_type.upper())
        if col_type is None:
            from tinydb.errors import ParseError

            raise ParseError(f"unknown type {col_def.col_type!r}", 1, 1)
        columns.append((col_def.name, col_type))
    catalog.create_table(stmt.name, columns)


def exec_drop_table(
    store: FileStore, catalog: Catalog, stmt: ast.DropTable,
) -> None:
    """执行 DROP TABLE。"""
    for name in stmt.names:
        catalog.drop_table(name)


__all__: list[str] = ["exec_create_table", "exec_drop_table"]
