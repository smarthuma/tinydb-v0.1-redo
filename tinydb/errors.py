"""异常层次与单一错误格式化入口（REQ-TS-008/009）。"""


class TinyDBError(Exception):
    """所有引擎异常的基类。"""


class ParseError(TinyDBError):
    """SQL 解析错误。"""

    def __init__(self, message: str, line: int, column: int) -> None:
        super().__init__(message)
        self.message = message
        self.line = line
        self.column = column


class TypeMismatch(TinyDBError):
    """插入值与列类型不匹配。"""

    def __init__(self, column: str, expected: str, got: str) -> None:
        super().__init__(column, expected, got)
        self.column = column
        self.expected = expected
        self.got = got


class UniqueViolation(TinyDBError):
    """UNIQUE 约束冲突。"""

    def __init__(self, column: str, table: str, value: object) -> None:
        super().__init__(column, table, value)
        self.column = column
        self.table = table
        self.value = value


class NotNullViolation(TinyDBError):
    """NOT NULL 约束冲突。"""

    def __init__(self, column: str, table: str) -> None:
        super().__init__(column, table)
        self.column = column
        self.table = table


class TableNotFound(TinyDBError):
    """表不存在。"""

    def __init__(self, table: str) -> None:
        super().__init__(table)
        self.table = table


class UnsafeDeleteWithoutWhere(TinyDBError):
    """无 WHERE 条件的 DELETE/UPDATE 被拒绝。"""


class IntegerOverflow(TinyDBError):
    """INT 值超出有符号 64 位范围。"""

    def __init__(self, value: int, max: int) -> None:
        super().__init__(value, max)
        self.value = value
        self.max = max


class TransactionAlreadyActive(TinyDBError):
    """重复 BEGIN。"""


class PageCorrupt(TinyDBError):
    """存储页校验失败。"""

    def __init__(self, page_id: int) -> None:
        super().__init__(page_id)
        self.page_id = page_id


class TransactionLogCorrupt(TinyDBError):
    """WAL 日志校验失败。"""

    def __init__(self, offset: int) -> None:
        super().__init__(offset)
        self.offset = offset


class DatabaseBusy(TinyDBError):
    """锁超时或数据库被其他连接占用（REQ-CC-004）。"""

    def __init__(self, message: str = "database is locked") -> None:
        super().__init__(message)
        self.message = message


def format(exc: BaseException) -> str:
    """把任意异常转成单行可读字符串（CLI/REPL 唯一出口）。"""
    match exc:
        case ParseError(message=msg, line=ln, column=col):
            return f"parse error at line {ln} column {col}: {msg}"
        case TypeMismatch(column=col, expected=exp, got=got):
            return f"type mismatch: column '{col}' expected {exp}, got {got}"
        case UniqueViolation(column=col, table=tbl, value=val):
            return f"unique violation: column '{col}' in table '{tbl}' value {val!r} already exists"
        case NotNullViolation(column=col, table=tbl):
            return f"not null violation: column '{col}' in table '{tbl}'"
        case TableNotFound(table=tbl):
            return f"table not found: '{tbl}'"
        case UnsafeDeleteWithoutWhere():
            return "unsafe delete/update without WHERE clause refused"
        case IntegerOverflow(value=val, max=mx):
            return f"integer overflow: {val} exceeds max {mx}"
        case TransactionAlreadyActive():
            return "transaction already active"
        case PageCorrupt(page_id=pid):
            return f"page corrupt: page_id={pid}"
        case TransactionLogCorrupt(offset=off):
            return f"transaction log corrupt: offset={off}"
        case DatabaseBusy(message=msg):
            return msg
        case TinyDBError():
            return str(exc.args[0]) if exc.args else exc.__class__.__name__
        case _:
            return f"{exc.__class__.__name__}: {exc}"


__all__: list[str] = [
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
    "DatabaseBusy",
    "format",
]
