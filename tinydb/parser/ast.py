"""AST frozen dataclasses（D7 不可变约定）。"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Literal


# ----------------------------------------------------------------------
# 表达式 / 谓词
# ----------------------------------------------------------------------
class JoinType(Enum):
    """JOIN 类型。"""

    INNER = "INNER"
    LEFT = "LEFT"


@dataclass(frozen=True)
class Column:
    name: str


@dataclass(frozen=True)
class Star:
    """SELECT * 投影。"""

    pass


@dataclass(frozen=True)
class SqlLiteral:
    value: object
    raw: str = ""


@dataclass(frozen=True)
class BinaryOp:
    op: str
    left: object
    right: object


@dataclass(frozen=True)
class LogicalOp:
    op: Literal["AND", "OR"]
    left: object
    right: object


@dataclass(frozen=True)
class UnaryOp:
    op: str
    operand: object


@dataclass(frozen=True)
class InPredicate:
    expr: object
    values: tuple[object, ...]
    negated: bool = False


# ----------------------------------------------------------------------
# 语句
# ----------------------------------------------------------------------
@dataclass(frozen=True)
class ColumnDef:
    """列定义。"""

    name: str
    col_type: str
    constraints: tuple[str, ...] = ()


@dataclass(frozen=True)
class CreateTable:
    name: str
    columns: tuple[ColumnDef, ...]
    if_not_exists: bool = False


@dataclass(frozen=True)
class DropTable:
    names: tuple[str, ...]
    if_exists: bool = False


@dataclass(frozen=True)
class Insert:
    table: str
    columns: tuple[str, ...] | None
    values: tuple[tuple[object, ...], ...]


@dataclass(frozen=True)
class OrderItem:
    expr: object
    direction: Literal["ASC", "DESC"] = "ASC"


@dataclass(frozen=True)
class JoinClause:
    """JOIN 子句。"""

    kind: JoinType
    table: str
    alias: str | None
    on: object


@dataclass(frozen=True)
class QualifiedColumn:
    """带表限定的列引用。"""

    table: str | None
    name: str


@dataclass(frozen=True)
class Select:
    projections: tuple[object, ...]
    table: str
    joins: tuple[JoinClause, ...] = ()
    where: object = None
    order_by: tuple[OrderItem, ...] = ()
    limit: int | None = None
    offset: int | None = None
    group_by: tuple[object, ...] = ()


@dataclass(frozen=True)
class Update:
    table: str
    assignments: tuple[tuple[str, object], ...]
    where: object = None


@dataclass(frozen=True)
class Delete:
    table: str
    where: object = None


@dataclass(frozen=True)
class Begin:
    pass


@dataclass(frozen=True)
class Commit:
    pass


@dataclass(frozen=True)
class Rollback:
    pass


@dataclass(frozen=True)
class Checkpoint:
    pass


@dataclass(frozen=True)
class Explain:
    """EXPLAIN 语句。"""

    statement: object


Statement = (
    CreateTable
    | DropTable
    | Insert
    | Select
    | Update
    | Delete
    | Begin
    | Commit
    | Rollback
    | Checkpoint
    | Explain
)
