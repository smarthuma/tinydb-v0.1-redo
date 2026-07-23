"""Batch 5 — T-5.2: Heap 追加/扫描/删除/更新 (REQ-QE-004 + REWRITE-PENDING 2.2)。"""

from __future__ import annotations

from tinydb.heap import Heap
from tinydb.storage import FileStore, PageType, alloc_page
from tinydb.types import ColumnType

_SCHEMA = [("id", ColumnType.INT), ("name", ColumnType.TEXT)]


def _new_heap(tmp_path: object, schema: list[tuple[str, ColumnType]] | None = None) -> Heap:
    schema = schema or _SCHEMA
    store = FileStore.open(str(tmp_path / "test.db"))
    root_page_id = alloc_page(store, PageType.TABLE)
    heap = Heap(store=store, root_page_id=root_page_id, schema=schema)
    return heap


def test_append_and_scan_returns_rows_in_order(tmp_path) -> None:
    """追加后扫描按插入顺序返回。"""
    heap = _new_heap(tmp_path)
    try:
        heap.append((1, "alice"))
        heap.append((2, "bob"))
        rows = list(heap.scan())
        assert len(rows) == 2
        assert rows[0][1] == (1, "alice")
        assert rows[1][1] == (2, "bob")
    finally:
        heap.close()


def test_delete_removes_row(tmp_path) -> None:
    """删除后该行不再出现在扫描中。"""
    heap = _new_heap(tmp_path)
    try:
        rowid = heap.append((1, "alice"))
        heap.append((2, "bob"))
        heap.delete(rowid)
        rows = list(heap.scan())
        assert len(rows) == 1
        assert rows[0][1] == (2, "bob")
    finally:
        heap.close()


def test_update_changes_row(tmp_path) -> None:
    """更新后扫描返回新值。"""
    heap = _new_heap(tmp_path)
    try:
        rowid = heap.append((1, "alice"))
        heap.update(rowid, (1, "alice-updated"))
        rows = list(heap.scan())
        assert rows[0][1] == (1, "alice-updated")
    finally:
        heap.close()


def test_heap_scan_after_reopen(tmp_path) -> None:
    """close 后重新打开 Heap 数据仍可读。"""
    path = str(tmp_path / "test.db")
    store = FileStore.open(path)
    root_page_id = alloc_page(store, PageType.TABLE)
    heap = Heap(store=store, root_page_id=root_page_id, schema=_SCHEMA)
    heap.append((1, "persist"))
    store.close()

    store2 = FileStore.open(path)
    heap2 = Heap(store=store2, root_page_id=root_page_id, schema=_SCHEMA)
    try:
        rows = list(heap2.scan())
        assert len(rows) == 1
        assert rows[0][1] == (1, "persist")
    finally:
        heap2.close()


def test_heap_has_all() -> None:
    """heap 模块声明 __all__。"""
    from tinydb import heap

    assert "Heap" in heap.__all__
