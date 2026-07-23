"""Batch 2 — REQ-TS-008/009: 异常层次 + errors.format 单一入口。"""

from tinydb import errors
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
    format,
)


def test_base_catches_all_subclasses() -> None:
    """所有引擎异常都能被 `except TinyDBError` 捕获。"""
    for exc_cls in (
        ParseError,
        TypeMismatch,
        UniqueViolation,
        NotNullViolation,
        TableNotFound,
        UnsafeDeleteWithoutWhere,
        IntegerOverflow,
        TransactionAlreadyActive,
        PageCorrupt,
        TransactionLogCorrupt,
    ):
        err = exc_cls(*_dummy_args(exc_cls))
        assert isinstance(err, TinyDBError)
        assert isinstance(err, Exception)


def _dummy_args(cls: type) -> tuple[object, ...]:
    """为各异常类的结构化字段提供占位参数。"""
    fields: dict[type, tuple[object, ...]] = {
        ParseError: ("msg", 1, 2),
        TypeMismatch: ("col", "INT", "TEXT"),
        UniqueViolation: ("col", "t", 1),
        NotNullViolation: ("col", "t"),
        TableNotFound: ("t",),
        UnsafeDeleteWithoutWhere: (),
        IntegerOverflow: (2**63, 2**63 - 1),
        TransactionAlreadyActive: (),
        PageCorrupt: (7,),
        TransactionLogCorrupt: (3,),
    }
    return fields[cls]


def test_format_type_mismatch_contains_fields() -> None:
    """format 输出单行，包含列名与期望/实际类型。"""
    msg = format(TypeMismatch(column="age", expected="INT", got="TEXT"))
    assert "\n" not in msg
    for token in ("age", "INT", "TEXT"):
        assert token in msg


def test_format_parse_error_contains_position() -> None:
    """format 输出包含行列位置信息。"""
    msg = format(ParseError(message="bad", line=2, column=5))
    assert "\n" not in msg
    for token in ("2", "5"):
        assert token in msg


def test_format_integer_overflow_contains_bounds() -> None:
    """format 输出包含越界值与上限。"""
    msg = format(IntegerOverflow(value=2**63, max=2**63 - 1))
    assert "\n" not in msg
    assert str(2**63) in msg
    assert str(2**63 - 1) in msg


def test_format_unknown_exception_still_one_line() -> None:
    """对非 TinyDBError 的异常，format 也能稳定输出单行。"""
    msg = format(ValueError("boom"))
    assert "\n" not in msg
    assert "boom" in msg


def test_errors_has_all() -> None:
    """errors 模块声明 __all__，覆盖公共 API。"""
    assert hasattr(errors, "__all__")
    assert "TinyDBError" in errors.__all__
    assert "format" in errors.__all__
