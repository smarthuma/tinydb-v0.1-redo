"""Batch 7 — SQL Parser 全组件测试（REQ-SP-001..007, REQ-TM-007）。"""

from __future__ import annotations

from tinydb.errors import ParseError
from tinydb.parser import parse
from tinydb.parser.ast import (
    Begin,
    BinaryOp,
    Checkpoint,
    Column,
    ColumnDef,
    Commit,
    CreateTable,
    Delete,
    DropTable,
    Insert,
    LogicalOp,
    OrderItem,
    Rollback,
    Select,
    Star,
    Update,
)
from tinydb.parser.lexer import TokenType, tokenize


# ----------------------------------------------------------------------
# Lexer
# ----------------------------------------------------------------------
def test_tokenize_keywords_and_idents() -> None:
    tokens = tokenize("CREATE TABLE users (id INT)")
    types = [t.type for t in tokens[:-1]]
    assert types == [
        TokenType.KEYWORD,  # CREATE
        TokenType.KEYWORD,  # TABLE
        TokenType.IDENT,    # users
        TokenType.PUNCT,    # (
        TokenType.IDENT,    # id
        TokenType.KEYWORD,  # INT
        TokenType.PUNCT,    # )
    ]


def test_tokenize_string_with_doubled_quote() -> None:
    tokens = tokenize("'O''Brien'")
    string_token = tokens[0]
    assert string_token.type is TokenType.STRING
    assert string_token.value == "O'Brien"


def test_tokenize_position_tracking() -> None:
    tokens = tokenize("SELECT\n  id")
    select = tokens[0]
    assert select.line == 1
    assert select.column == 1
    ident = tokens[1]
    assert ident.value == "id"
    assert ident.line == 2
    assert ident.column == 3


# ----------------------------------------------------------------------
# DDL
# ----------------------------------------------------------------------
def test_parse_create_table_with_pk_and_not_null() -> None:
    ast = parse("CREATE TABLE users (id INT PRIMARY KEY, name TEXT NOT NULL);")
    assert isinstance(ast, CreateTable)
    assert ast.name == "users"
    assert ast.columns == (
        ColumnDef("id", "INT", ("PRIMARY KEY",)),
        ColumnDef("name", "TEXT", ("NOT NULL",)),
    )


def test_parse_drop_table_if_exists() -> None:
    ast = parse("DROP TABLE IF EXISTS legacy;")
    assert isinstance(ast, DropTable)
    assert ast.names == ("legacy",)
    assert ast.if_exists is True


# ----------------------------------------------------------------------
# DML
# ----------------------------------------------------------------------
def test_parse_select_with_where_order_limit_offset() -> None:
    ast = parse("SELECT id, name FROM users WHERE age >= 18 ORDER BY name ASC LIMIT 10 OFFSET 5;")
    assert isinstance(ast, Select)
    assert ast.projections == (Column("id"), Column("name"))
    assert ast.table == "users"
    assert isinstance(ast.where, BinaryOp)
    assert ast.where.op == ">="
    assert ast.order_by == (OrderItem(Column("name"), "ASC"),)
    assert ast.limit == 10
    assert ast.offset == 5


def test_parse_select_star() -> None:
    ast = parse("SELECT * FROM users;")
    assert isinstance(ast, Select)
    assert ast.projections == (Star(),)


def test_parse_update_with_where() -> None:
    ast = parse("UPDATE users SET name = 'alice' WHERE id = 1;")
    assert isinstance(ast, Update)
    assert ast.table == "users"
    assert ast.assignments == (("name", "alice"),)
    assert isinstance(ast.where, BinaryOp)


def test_parse_delete_without_where() -> None:
    ast = parse("DELETE FROM users;")
    assert isinstance(ast, Delete)
    assert ast.table == "users"
    assert ast.where is None


def test_parse_insert() -> None:
    ast = parse("INSERT INTO users (id, name) VALUES (1, 'alice');")
    assert isinstance(ast, Insert)
    assert ast.table == "users"
    assert ast.columns == ("id", "name")
    assert ast.values == ((1, "alice"),)


# ----------------------------------------------------------------------
# Predicate
# ----------------------------------------------------------------------
def test_and_binds_tighter_than_or() -> None:
    ast = parse("SELECT * FROM t WHERE a = 1 OR b = 2 AND c = 3;")
    where = ast.where
    assert isinstance(where, LogicalOp)
    assert where.op == "OR"
    assert isinstance(where.right, LogicalOp)
    assert where.right.op == "AND"


def test_between_produces_synthetic_and() -> None:
    ast = parse("SELECT * FROM t WHERE age BETWEEN 18 AND 65;")
    where = ast.where
    assert isinstance(where, LogicalOp)
    assert where.op == "AND"
    assert isinstance(where.left, BinaryOp)
    assert where.left.op == ">="
    assert isinstance(where.right, BinaryOp)
    assert where.right.op == "<="


def test_count_star_and_group_by() -> None:
    ast = parse("SELECT dept, COUNT(*) FROM employees GROUP BY dept;")
    assert isinstance(ast, Select)
    assert ast.projections[1].value == "COUNT(*)"
    assert ast.group_by == (Column("dept"),)


# ----------------------------------------------------------------------
# Transaction control
# ----------------------------------------------------------------------
def test_parse_begin() -> None:
    assert isinstance(parse("BEGIN;"), Begin)
    assert isinstance(parse("BEGIN TRANSACTION;"), Begin)


def test_parse_commit() -> None:
    assert isinstance(parse("COMMIT;"), Commit)
    assert isinstance(parse("END;"), Commit)


def test_parse_rollback() -> None:
    assert isinstance(parse("ROLLBACK;"), Rollback)


def test_parse_checkpoint() -> None:
    assert isinstance(parse("CHECKPOINT;"), Checkpoint)


# ----------------------------------------------------------------------
# Error
# ----------------------------------------------------------------------
def test_parse_error_reports_position() -> None:
    try:
        parse("CREATE users (id INT);")
    except ParseError as exc:
        assert "TABLE" in str(exc.message)
        assert exc.line == 1
    else:
        raise AssertionError("expected ParseError")


# ----------------------------------------------------------------------
# Purity
# ----------------------------------------------------------------------
def test_parser_pure_function() -> None:
    ast1 = parse("SELECT 1;")
    ast2 = parse("SELECT 1;")
    assert ast1 == ast2
