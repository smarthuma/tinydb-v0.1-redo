"""TinyDB — 用于学习数据库内部原理的嵌入式关系型 Python 数据库。"""

from __future__ import annotations

from tinydb.database import Database
from tinydb.errors import (
    IntegerOverflow,
    NotNullViolation,
    PageCorrupt,
    ParseError,
    TableNotFound,
    TinyDBError,
    TransactionAlreadyActive,
    TransactionLogCorrupt,
    TypeMismatch,
    UniqueViolation,
    UnsafeDeleteWithoutWhere,
)

__version__ = "0.2.0"

__all__: list[str] = [
    "Database",
    "TinyDBError",
    "ParseError",
    "TypeMismatch",
    "UniqueViolation",
    "NotNullViolation",
    "TableNotFound",
    "UnsafeDeleteWithoutWhere",
    "IntegerOverflow",
    "TransactionAlreadyActive",
    "PageCorrupt",
    "TransactionLogCorrupt",
]
