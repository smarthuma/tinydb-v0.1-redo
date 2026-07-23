"""类型编解码、强制规则与比较语义（REQ-TS-001..007）。"""

from __future__ import annotations

import struct
from enum import Enum
from typing import Protocol, cast, runtime_checkable

from tinydb.errors import IntegerOverflow, TypeMismatch


@runtime_checkable
class _SupportsLessThan(Protocol):
    def __lt__(self, other: object) -> bool: ...

_INT64_MIN = -(2**63)
_INT64_MAX = 2**63 - 1


class ColumnType(Enum):
    """支持的列类型。"""

    INT = "INT"
    FLOAT = "FLOAT"
    TEXT = "TEXT"
    BOOL = "BOOL"


def _python_type_name(value: object) -> str:
    """把 Python 值映射成引擎类型名（用于 TypeMismatch 的 got 字段）。"""
    if isinstance(value, bool):
        return "BOOL"
    if isinstance(value, int):
        return "INT"
    if isinstance(value, float):
        return "FLOAT"
    if isinstance(value, str):
        return "TEXT"
    return type(value).__name__.upper()


def encode_int(value: int) -> bytes:
    """INT 编码为 little-endian int64（REQ-TS-001）。"""
    if not isinstance(value, int) or isinstance(value, bool):
        raise TypeMismatch(column="?", expected="INT", got=_python_type_name(value))
    if value < _INT64_MIN or value > _INT64_MAX:
        raise IntegerOverflow(value=value, max=_INT64_MAX)
    return value.to_bytes(8, "little", signed=True)


def decode_int(raw: bytes) -> int:
    """little-endian int64 解码为 Python int（REQ-TS-001）。"""
    return int.from_bytes(raw[:8], "little", signed=True)


def encode_float(value: float) -> bytes:
    """FLOAT 编码为 IEEE-754 binary64（REQ-TS-002）。"""
    if not isinstance(value, float):
        raise TypeMismatch(column="?", expected="FLOAT", got=_python_type_name(value))
    return struct.pack("<d", value)


def decode_float(raw: bytes) -> float:
    """binary64 解码为 Python float（REQ-TS-002）。"""
    (value,) = struct.unpack("<d", raw[:8])
    return cast("float", value)


def encode_text(value: str) -> bytes:
    """TEXT 编码为 u32 长度前缀 + UTF-8 字节（REQ-TS-003）。"""
    if not isinstance(value, str):
        raise TypeMismatch(column="?", expected="TEXT", got=_python_type_name(value))
    encoded = value.encode("utf-8")
    return len(encoded).to_bytes(4, "little") + encoded


def decode_text(raw: bytes) -> str:
    """带长度前缀的 UTF-8 解码为 Python str（REQ-TS-003）。"""
    length = int.from_bytes(raw[:4], "little")
    return raw[4 : 4 + length].decode("utf-8")


def encode_bool(value: bool) -> bytes:
    """BOOL 编码为单字节（REQ-TS-004）。拒绝非 bool（包括 0/1）。"""
    if not isinstance(value, bool):
        raise TypeMismatch(column="?", expected="BOOL", got=_python_type_name(value))
    return b"\x01" if value else b"\x00"


def decode_bool(raw: bytes) -> bool:
    """单字节解码为 Python bool（REQ-TS-004）。"""
    return raw[0] != 0


def encode(value: object, column_type: ColumnType) -> bytes:
    """统一编码分派，NULL（None）产出 8 字节全零占位。"""
    if value is None:
        return b"\x00" * 8
    match column_type:
        case ColumnType.INT:
            return encode_int(value)  # type: ignore[arg-type]
        case ColumnType.FLOAT:
            return encode_float(value)  # type: ignore[arg-type]
        case ColumnType.TEXT:
            return encode_text(value)  # type: ignore[arg-type]
        case ColumnType.BOOL:
            return encode_bool(value)  # type: ignore[arg-type]


def decode(raw: bytes, column_type: ColumnType) -> object:
    """统一解码分派，全零占位视为 NULL。"""
    if raw == b"\x00" * 8:
        return None
    match column_type:
        case ColumnType.INT:
            return decode_int(raw)
        case ColumnType.FLOAT:
            return decode_float(raw)
        case ColumnType.TEXT:
            return decode_text(raw)
        case ColumnType.BOOL:
            return decode_bool(raw)


def coerce_in(value: object, column_type: ColumnType, column: str = "?") -> object:
    """插入前强制：INT 接受 bool（False->0，True->1），其余跨类型拒绝（REQ-TS-005）。"""
    if column_type is ColumnType.INT and isinstance(value, bool):
        return 1 if value else 0
    if column_type is ColumnType.INT and isinstance(value, int):
        return value
    if column_type is ColumnType.FLOAT and isinstance(value, float):
        return value
    if column_type is ColumnType.TEXT and isinstance(value, str):
        return value
    if column_type is ColumnType.BOOL and isinstance(value, bool):
        return value
    if value is None:
        return None
    raise TypeMismatch(column=column, expected=column_type.value, got=_python_type_name(value))


def compare(
    left: _SupportsLessThan | None,
    right: _SupportsLessThan | None,
    column_type: ColumnType,
) -> bool | None:
    """WHERE 比较语义（REQ-TS-007）。任一操作数为 NULL 返回 None（调用方排除该行）。"""
    if left is None or right is None:
        return None
    if column_type is ColumnType.BOOL:
        # False < True
        return bool(left) < bool(right)
    return left < right


__all__: list[str] = [
    "ColumnType",
    "encode_int",
    "decode_int",
    "encode_float",
    "decode_float",
    "encode_text",
    "decode_text",
    "encode_bool",
    "decode_bool",
    "encode",
    "decode",
    "coerce_in",
    "compare",
]
