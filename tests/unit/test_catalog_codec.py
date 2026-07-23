"""Batch 5 — T-5.3: Catalog 编解码 (REWRITE-PENDING 2.4)。"""

from __future__ import annotations

from tinydb.catalog_codec import TableMeta, decode_catalog, encode_catalog
from tinydb.types import ColumnType


def _make_table() -> TableMeta:
    return TableMeta(
        name="users",
        root_page_id=3,
        schema=[
            ("id", ColumnType.INT),
            ("name", ColumnType.TEXT),
        ],
    )


def test_catalog_roundtrip_single_table() -> None:
    """单表 round-trip。"""
    entry = _make_table()
    raw = encode_catalog([entry])
    decoded = decode_catalog(raw)
    assert len(decoded) == 1
    assert decoded[0].name == "users"
    assert decoded[0].root_page_id == 3
    assert decoded[0].schema == [("id", ColumnType.INT), ("name", ColumnType.TEXT)]


def test_catalog_roundtrip_multiple_tables() -> None:
    """多表 round-trip。"""
    entries = [
        _make_table(),
        TableMeta(
            name="orders",
            root_page_id=7,
            schema=[("order_id", ColumnType.INT), ("total", ColumnType.FLOAT)],
        ),
    ]
    raw = encode_catalog(entries)
    decoded = decode_catalog(raw)
    assert len(decoded) == 2
    assert decoded[0].name == "users"
    assert decoded[1].name == "orders"
    assert decoded[1].schema[1] == ("total", ColumnType.FLOAT)


def test_catalog_empty_roundtrip() -> None:
    """空 catalog round-trip。"""
    raw = encode_catalog([])
    assert decode_catalog(raw) == []


def test_catalog_has_all() -> None:
    """catalog_codec 模块声明 __all__。"""
    from tinydb import catalog_codec

    assert "TableMeta" in catalog_codec.__all__
    assert "encode_catalog" in catalog_codec.__all__
    assert "decode_catalog" in catalog_codec.__all__
