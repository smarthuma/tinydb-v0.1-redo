"""Batch 2 — REQ-TS-001..007: 类型编解码、强制、NULL、比较语义。"""

from tinydb.types import (
    ColumnType,
    coerce_in,
    compare,
    decode,
    decode_bool,
    decode_float,
    decode_int,
    decode_text,
    encode,
    encode_bool,
    encode_float,
    encode_int,
    encode_text,
)


def test_int_roundtrip_negative() -> None:
    """INT 负数 round-trip 精确。"""
    raw = encode_int(-1234567890)
    assert decode_int(raw) == -1234567890


def test_int_overflow_raises() -> None:
    """超出有符号 64 位范围抛出 IntegerOverflow。"""
    from tinydb.errors import IntegerOverflow

    try:
        encode_int(2**63)
    except IntegerOverflow as exc:
        assert exc.value == 2**63
        assert exc.max == 2**63 - 1
    else:
        raise AssertionError("expected IntegerOverflow")


def test_float_roundtrip() -> None:
    """FLOAT IEEE-754 binary64 round-trip。"""
    raw = encode_float(3.141592653589793)
    assert decode_float(raw) == 3.141592653589793


def test_text_roundtrip_non_ascii() -> None:
    """TEXT 支持非 ASCII / emoji round-trip。"""
    raw = encode_text("你好, tinydb 🚀")
    assert decode_text(raw) == "你好, tinydb 🚀"


def test_text_empty_string_ok() -> None:
    """TEXT 接受空字符串。"""
    assert decode_text(encode_text("")) == ""


def test_bool_rejects_int() -> None:
    """BOOL 拒绝整数 0/1。"""
    from tinydb.errors import TypeMismatch

    try:
        encode_bool(0)  # type: ignore[arg-type]
    except TypeMismatch as exc:
        assert exc.expected == "BOOL"
        assert exc.got == "INT"
    else:
        raise AssertionError("expected TypeMismatch for int->BOOL")


def test_bool_roundtrip() -> None:
    """BOOL True/False round-trip。"""
    assert decode_bool(encode_bool(True)) is True
    assert decode_bool(encode_bool(False)) is False


def test_bool_type_is_still_bool() -> None:
    """解码后仍是 bool 类型，不是 0/1。"""
    assert type(decode_bool(encode_bool(True))) is bool


def test_encode_dispatch_int() -> None:
    """统一分派 encode(value, ColumnType.INT) 工作。"""
    assert decode_int(encode(123, ColumnType.INT)) == 123


def test_encode_dispatch_float() -> None:
    """统一分派 encode(value, ColumnType.FLOAT) 工作。"""
    assert decode_float(encode(2.5, ColumnType.FLOAT)) == 2.5


def test_encode_dispatch_text() -> None:
    """统一分派 encode(value, ColumnType.TEXT) 工作。"""
    assert decode_text(encode("hi", ColumnType.TEXT)) == "hi"


def test_encode_dispatch_bool() -> None:
    """统一分派 encode(value, ColumnType.BOOL) 工作。"""
    assert decode_bool(encode(True, ColumnType.BOOL)) is True


def test_coerce_bool_to_int() -> None:
    """INT 列接受 bool，False->0，True->1。"""
    assert coerce_in(True, ColumnType.INT) == 1
    assert coerce_in(False, ColumnType.INT) == 0


def test_coerce_int_into_text_rejected() -> None:
    """TEXT 列拒绝整数。"""
    from tinydb.errors import TypeMismatch

    try:
        coerce_in(42, ColumnType.TEXT)
    except TypeMismatch as exc:
        assert exc.column == "?"
        assert exc.expected == "TEXT"
        assert exc.got == "INT"
    else:
        raise AssertionError("expected TypeMismatch for int->TEXT")


def test_null_roundtrip() -> None:
    """NULL (None) round-trip 为 Python None（经 dispatch 分派）。

    注意：INT 的数值 0 与 NULL sentinel (8 字节全零) 在纯编解码层碰撞，
    实际由行层 null bitmap 区分；此处仅验证 dispatch 层对 sentinel 的处理。
    """
    assert decode(encode(None, ColumnType.INT), ColumnType.INT) is None
    assert decode(encode(None, ColumnType.FLOAT), ColumnType.FLOAT) is None
    assert decode(encode(None, ColumnType.TEXT), ColumnType.TEXT) is None
    assert decode(encode(None, ColumnType.BOOL), ColumnType.BOOL) is None


def test_null_excluded_from_where() -> None:
    """NULL 比较返回 None（调用方据此排除该行）。"""
    assert compare(None, 5, ColumnType.INT) is None


def test_compare_int_ordering() -> None:
    """INT 数值序。"""
    assert compare(1, 2, ColumnType.INT) is True
    assert compare(2, 1, ColumnType.INT) is False


def test_compare_float_ordering() -> None:
    """FLOAT 数值序。"""
    assert compare(1.5, 2.5, ColumnType.FLOAT) is True


def test_compare_text_byte_order() -> None:
    """TEXT 字节序（UTF-8 codepoint 序）。"""
    assert compare("Apple", "Banana", ColumnType.TEXT) is True
    # 大写字母 UTF-8 字节序在小写之前
    assert compare("apple", "Banana", ColumnType.TEXT) is False


def test_compare_bool_ordering() -> None:
    """BOOL False < True。"""
    assert compare(False, True, ColumnType.BOOL) is True
    assert compare(True, False, ColumnType.BOOL) is False


def test_types_has_all() -> None:
    """types 模块声明 __all__。"""
    from tinydb import types

    assert "ColumnType" in types.__all__
    assert "encode" in types.__all__
    assert "coerce_in" in types.__all__
