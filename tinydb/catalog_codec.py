"""Catalog 编解码（REWRITE-PENDING 2.4）。

紧凑二进制格式：``[table_count u16][table_entry * count]``，每个 table_entry 为
``[name_len u16][name_utf8][root_page_id u32][col_count u16][(col_name_len u16 +
col_name_utf8 + type_len u12 + type_utf8) * n]``。
"""

from __future__ import annotations

import struct
from dataclasses import dataclass

from tinydb.types import ColumnType

_LEN_STRUCT = struct.Struct("<H")
_ROOT_STRUCT = struct.Struct("<I")


@dataclass
class TableMeta:
    """表的 catalog 元数据。"""

    name: str
    root_page_id: int
    schema: list[tuple[str, ColumnType]]


def encode_catalog(entries: list[TableMeta]) -> bytes:
    """编码 catalog。"""
    parts: list[bytes] = [_LEN_STRUCT.pack(len(entries))]
    for entry in entries:
        name_bytes = entry.name.encode("utf-8")
        parts.append(_LEN_STRUCT.pack(len(name_bytes)))
        parts.append(name_bytes)
        parts.append(_ROOT_STRUCT.pack(entry.root_page_id))
        parts.append(_LEN_STRUCT.pack(len(entry.schema)))
        for col_name, col_type in entry.schema:
            col_name_bytes = col_name.encode("utf-8")
            parts.append(_LEN_STRUCT.pack(len(col_name_bytes)))
            parts.append(col_name_bytes)
            type_bytes = col_type.value.encode("utf-8")
            parts.append(_LEN_STRUCT.pack(len(type_bytes)))
            parts.append(type_bytes)
    return b"".join(parts)


def decode_catalog(raw: bytes) -> list[TableMeta]:
    """解码 catalog。"""
    offset = 0
    table_count = _LEN_STRUCT.unpack(raw[offset : offset + 2])[0]
    offset += 2
    entries: list[TableMeta] = []
    for _ in range(table_count):
        name_len = _LEN_STRUCT.unpack(raw[offset : offset + 2])[0]
        offset += 2
        name = raw[offset : offset + name_len].decode("utf-8")
        offset += name_len
        root_page_id = _ROOT_STRUCT.unpack(raw[offset : offset + 4])[0]
        offset += 4
        col_count = _LEN_STRUCT.unpack(raw[offset : offset + 2])[0]
        offset += 2
        schema: list[tuple[str, ColumnType]] = []
        for _ in range(col_count):
            col_name_len = _LEN_STRUCT.unpack(raw[offset : offset + 2])[0]
            offset += 2
            col_name = raw[offset : offset + col_name_len].decode("utf-8")
            offset += col_name_len
            type_len = _LEN_STRUCT.unpack(raw[offset : offset + 2])[0]
            offset += 2
            col_type = ColumnType(raw[offset : offset + type_len].decode("utf-8"))
            offset += type_len
            schema.append((col_name, col_type))
        entries.append(TableMeta(name=name, root_page_id=root_page_id, schema=schema))
    return entries


__all__: list[str] = [
    "TableMeta",
    "encode_catalog",
    "decode_catalog",
]
