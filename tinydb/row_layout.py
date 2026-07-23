"""行二进制布局编解码（REWRITE-PENDING 2.2）。

变长布局：``[rowid u64][col_count u16][(encoded_len u32 + encoded_bytes) * n]``。
每个值先经 ``types.encode`` 产出字节，再带长度前缀写入，解码时按长度切片后
用 ``types.decode`` 还原。NULL 用 ``encoded_len=0`` 标记。
"""

from __future__ import annotations

import struct

from typing import cast

from tinydb.types import ColumnType, decode, encode

_ROWID_STRUCT = struct.Struct("<Q")
_COUNT_STRUCT = struct.Struct("<H")
_LEN_STRUCT = struct.Struct("<I")


def encode_row(
    values: tuple[object, ...],
    schema: list[tuple[str, ColumnType]],
    rowid: int = 0,
) -> bytes:
    """把一行值编码为字节。"""
    parts = [_ROWID_STRUCT.pack(rowid), _COUNT_STRUCT.pack(len(schema))]
    for value, (_name, col_type) in zip(values, schema, strict=False):
        if value is None:
            parts.append(_LEN_STRUCT.pack(0))
        else:
            encoded = encode(value, col_type)
            parts.append(_LEN_STRUCT.pack(len(encoded)))
            parts.append(encoded)
    return b"".join(parts)


def decode_row(raw: bytes, schema: list[tuple[str, ColumnType]]) -> tuple[object, ...]:
    """从字节解码一行值。"""
    offset = _ROWID_STRUCT.size + _COUNT_STRUCT.size
    values: list[object] = []
    for _name, col_type in schema:
        length = _LEN_STRUCT.unpack(raw[offset : offset + _LEN_STRUCT.size])[0]
        offset += _LEN_STRUCT.size
        if length == 0:
            values.append(None)
        else:
            values.append(decode(raw[offset : offset + length], col_type))
            offset += length
    return tuple(values)


def encode_rowid(rowid: int) -> bytes:
    """编码 rowid 前缀。"""
    return _ROWID_STRUCT.pack(rowid)


def decode_rowid(raw: bytes) -> int:
    """解码 rowid。"""
    return cast("int", _ROWID_STRUCT.unpack(raw[: _ROWID_STRUCT.size])[0])


__all__: list[str] = [
    "encode_row",
    "decode_row",
    "encode_rowid",
    "decode_rowid",
]
