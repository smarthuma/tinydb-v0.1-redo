"""Batch 11 — 谓词解析补覆盖率（REQ-SP-004/005/006）。"""

from __future__ import annotations

from tinydb.parser import parse


def test_not_in_predicate() -> None:
    """NOT IN 谓词。"""
    stmt = parse("SELECT * FROM t WHERE v IN (1, 2, 3);")
    where = stmt.where
    assert where.__class__.__name__ == "InPredicate"
    assert where.values == (1, 2, 3)
    assert where.negated is False


def test_is_not_null() -> None:
    """IS NOT NULL。"""
    stmt = parse("SELECT * FROM t WHERE v IS NOT NULL;")
    where = stmt.where
    assert where.op == "IS NOT NULL"


def test_complex_and_or() -> None:
    """复杂 AND/OR 组合。"""
    stmt = parse("SELECT * FROM t WHERE a = 1 OR b = 2 OR c = 3;")
    where = stmt.where
    assert where.op == "OR"


def test_comparison_operators() -> None:
    """各种比较操作符。"""
    for op in ["=", "<>", "<", "<=", ">", ">="]:
        stmt = parse(f"SELECT * FROM t WHERE a {op} 1;")
        assert stmt.where.op == op


def test_logical_and() -> None:
    """AND 谓词。"""
    stmt = parse("SELECT * FROM t WHERE a = 1 AND b = 2;")
    assert stmt.where.op == "AND"


def test_true_false_literals() -> None:
    """TRUE/FALSE 字面。"""
    stmt = parse("SELECT * FROM t WHERE a = TRUE;")
    assert stmt.where.right.value is True
    stmt2 = parse("SELECT * FROM t WHERE a = FALSE;")
    assert stmt2.where.right.value is False


def test_string_literal() -> None:
    """字符串字面。"""
    stmt = parse("SELECT * FROM t WHERE name = 'alice';")
    assert stmt.where.right.value == "alice"


def test_null_literal() -> None:
    """NULL 字面。"""
    stmt = parse("SELECT * FROM t WHERE name = NULL;")
    assert stmt.where.right.value is None
