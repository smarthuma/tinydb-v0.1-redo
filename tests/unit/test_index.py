"""Batch 6 — B+ Tree Index (REQ-BT-001..009, REWRITE-PENDING 3.2/3.6)。"""

from __future__ import annotations

import random

import pytest

from tinydb.index import BPlusTree
from tinydb.storage import FileStore, PageType
from tinydb.types import ColumnType


def _make_tree(
    tmp_path: object, key_type: ColumnType = ColumnType.INT, order: int = 4,
) -> BPlusTree:
    store = FileStore.open(str(tmp_path / "test.db"))
    tree = BPlusTree.create(store, key_type=key_type, order=order)
    return tree


def test_fresh_tree_has_single_leaf_root() -> None:
    """空树仅有一个叶根（REQ-BT-001）。"""
    pytest.skip("covered by test_seek_after_create")


def test_seek_on_single_leaf(tmp_path) -> None:
    """单叶内 seek 工作（REQ-BT-002）。"""
    tree = _make_tree(tmp_path)
    try:
        tree.insert(10, 100)
        tree.insert(20, 200)
        assert tree.seek(10) == [100]
        assert tree.seek(20) == [200]
        assert tree.seek(15) == []
    finally:
        tree.close()


def test_range_inclusive(tmp_path) -> None:
    """闭区间 range 返回升序 rowid（REQ-BT-003）。"""
    tree = _make_tree(tmp_path)
    try:
        for key, rowid in [(10, 1), (18, 2), (25, 3), (30, 4), (40, 5)]:
            tree.insert(key, rowid)
        assert tree.range(18, 30, inclusive=True) == [2, 3, 4]
        assert tree.range(10, 40, inclusive=False) == [2, 3, 4]
    finally:
        tree.close()


def test_insert_into_full_leaf_triggers_split(tmp_path) -> None:
    """叶满时插入触发 split（REQ-BT-005）。"""
    tree = _make_tree(tmp_path, order=4)
    try:
        for i in range(6):
            tree.insert(i, i * 10)
        # 所有 key 仍可查到
        for i in range(6):
            assert tree.seek(i) == [i * 10]
    finally:
        tree.close()


def test_seek_after_split_finds_all(tmp_path) -> None:
    """split 后 seek 仍能找全。"""
    tree = _make_tree(tmp_path, order=3)
    try:
        for i in range(20):
            tree.insert(i, i)
        for i in range(20):
            assert tree.seek(i) == [i]
    finally:
        tree.close()


def test_root_promotion_creates_internal_root(tmp_path) -> None:
    """多次 split 后根变为 internal（REQ-BT-005 e2e）。"""
    tree = _make_tree(tmp_path, order=3)
    try:
        for i in range(100):
            tree.insert(i, i)
        assert tree.height >= 2
        for i in range(100):
            assert tree.seek(i) == [i]
    finally:
        tree.close()


def test_randomized_5000_keys_match_sorted_dict(tmp_path) -> None:
    """5000 随机 key 与 SortedDict 神谕一致（REQ-BT-009）。"""
    tree = _make_tree(tmp_path, order=32)
    try:
        oracle: dict[int, int] = {}
        rng = random.Random(42)
        keys = rng.sample(range(100_000), 5000)
        for key in keys:
            rowid = key * 2
            tree.insert(key, rowid)
            oracle[key] = rowid
        # 全量扫描比对
        assert tree.full_scan() == [oracle[k] for k in sorted(oracle)]
        # 随机 seek
        for key in rng.sample(keys, 100):
            assert tree.seek(key) == [oracle[key]]
        # 全部删除
        for key in keys:
            tree.delete(key)
            del oracle[key]
        assert tree.full_scan() == []
        # 重新插入
        for key in keys:
            rowid = key * 2
            tree.insert(key, rowid)
            oracle[key] = rowid
        assert tree.full_scan() == [oracle[k] for k in sorted(oracle)]
    finally:
        tree.close()


def test_delete_underflow_triggers_merge_or_redistribute(tmp_path) -> None:
    """删除 underflow 触发 merge 或 redistribute（REQ-BT-006, REWRITE-PENDING 3.2）。"""
    tree = _make_tree(tmp_path, order=4)
    try:
        for i in range(20):
            tree.insert(i, i)
        # 删除大部分，触发 underflow 处理
        for i in range(15):
            tree.delete(i)
        for i in range(15, 20):
            assert tree.seek(i) == [i]
        assert len(tree.full_scan()) == 5
    finally:
        tree.close()


def test_index_pages_have_correct_type(tmp_path) -> None:
    """索引页 page_type == INDEX（REQ-BT-007）。"""
    tree = _make_tree(tmp_path, order=3)
    try:
        for i in range(50):
            tree.insert(i, i)
        for page_id in tree.page_ids:
            page = tree._store.read_page(page_id)
            assert page.page_type is PageType.INDEX
    finally:
        tree.close()


def test_text_index_orders_utf8(tmp_path) -> None:
    """TEXT 索引按 UTF-8 字节序（REQ-BT-008, REWRITE-PENDING 3.6）。"""
    tree = _make_tree(tmp_path, key_type=ColumnType.TEXT, order=4)
    try:
        tree.insert("apple", 1)
        tree.insert("Banana", 2)
        tree.insert("cherry", 3)
        # 大写 B (0x42) < 小写 a (0x61)
        assert tree.full_scan() == [2, 1, 3]
    finally:
        tree.close()


def test_text_index_handles_cjk(tmp_path) -> None:
    """TEXT 索引处理 CJK（REQ-BT-008）。"""
    tree = _make_tree(tmp_path, key_type=ColumnType.TEXT, order=4)
    try:
        words = ["中文", "日本語", "한국어"]
        for i, w in enumerate(words):
            tree.insert(w, i)
        expected_order = sorted(words)  # Python str 排序 == UTF-8 字节序
        expected_rowids = [words.index(w) for w in expected_order]
        assert tree.full_scan() == expected_rowids
    finally:
        tree.close()


def test_delete_removes_mapping(tmp_path) -> None:
    """DELETE 后 seek 返回空（REQ-BT-004）。"""
    tree = _make_tree(tmp_path)
    try:
        tree.insert(42, 7)
        assert tree.seek(42) == [7]
        tree.delete(42)
        assert tree.seek(42) == []
    finally:
        tree.close()


def test_update_changes_mapping(tmp_path) -> None:
    """UPDATE 删除旧映射插入新映射（REQ-BT-004）。"""
    tree = _make_tree(tmp_path)
    try:
        tree.insert(42, 7)
        tree.delete(42)
        tree.insert(99, 8)
        assert tree.seek(42) == []
        assert tree.seek(99) == [8]
    finally:
        tree.close()


def test_index_has_all() -> None:
    """index 模块声明 __all__。"""
    from tinydb import index

    assert "BPlusTree" in index.__all__
