"""Batch 5 — T-5.1: 行编解码 (REQ-QE-004 + REWRITE-PENDING 2.2)。"""

from __future__ import annotations

from tinydb.row_layout import decode_row, encode_row
from tinydb.types import ColumnType


def _schema() -> list[tuple[str, ColumnType]]:
    return [
        ("id", ColumnType.INT),
        ("name", ColumnType.TEXT),
        ("score", ColumnType.FLOAT),
        ("active", ColumnType.BOOL),
    ]


def test_encode_decode_roundtrip_mixed_types() -> None:
    """混合类型行 round-trip 精确。"""
    schema = _schema()
    row = (1, "alice", 3.5, True)
    raw = encode_row(row, schema)
    decoded = decode_row(raw, schema)
    assert decoded[0] == 1
    assert decoded[1] == "alice"
    assert decoded[2] == 3.5
    assert decoded[3] is True


def test_encode_decode_with_null() -> None:
    """NULL 值 round-trip 为 None。"""
    schema = _schema()
    row = (None, None, None, None)
    raw = encode_row(row, schema)
    decoded = decode_row(raw, schema)
    assert all(v is None for v in decoded)


def test_encode_decode_non_ascii_text() -> None:
    """非 ASCII 文本 round-trip。"""
    schema = [("name", ColumnType.TEXT)]
    row = ("你好, tinydb 🚀",)
    raw = encode_row(row, schema)
    assert decode_row(raw, schema)[0] == "你好, tinydb 🚀"


def test_encode_decode_single_column() -> None:
    """单列 round-trip。"""
    schema = [("id", ColumnType.INT)]
    row = (42,)
    raw = encode_row(row, schema)
    assert decode_row(raw, schema) == (42,)


def test_row_layout_has_all() -> None:
    """row_layout 模块声明 __all__。"""
    from tinydb import row_layout

    assert "encode_row" in row_layout.__all__
    assert "decode_row" in row_layout.__all__
