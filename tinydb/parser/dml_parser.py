"""DML 解析：INSERT / SELECT / UPDATE / DELETE（REQ-SP-003, REWRITE-PENDING 3.5）。"""

from __future__ import annotations

from typing import TYPE_CHECKING

from tinydb.parser import ast

if TYPE_CHECKING:
    from tinydb.parser import Parser

from tinydb.errors import ParseError
from tinydb.parser.lexer import TokenType
from tinydb.parser.predicate import parse_expression, parse_primary


def parse_insert(parser: Parser) -> ast.Insert:
    """解析 INSERT INTO 语句。"""
    parser._expect_keyword("INSERT")
    parser._expect_keyword("INTO")
    table = _parse_ident(parser)
    columns: tuple[str, ...] | None = None
    if parser._peek().value == "(":
        parser._advance()
        cols: list[str] = [_parse_ident(parser)]
        while _match_punct(parser, ","):
            cols.append(_parse_ident(parser))
        parser._expect_punct(")")
        columns = tuple(cols)
    parser._expect_keyword("VALUES")
    values_list = [_parse_value_tuple(parser)]
    while _match_punct(parser, ","):
        values_list.append(_parse_value_tuple(parser))
    return ast.Insert(table=table, columns=columns, values=tuple(values_list))


def _parse_value_tuple(parser: Parser) -> tuple[object, ...]:
    """解析 (...) 值元组。"""
    parser._expect_punct("(")
    values = [_parse_value(parser)]
    while _match_punct(parser, ","):
        values.append(_parse_value(parser))
    parser._expect_punct(")")
    return tuple(values)


def _parse_value(parser: Parser) -> object:
    """解析单个值。"""
    from tinydb.parser.predicate import _parse_number

    token = parser._peek()
    if token.type is TokenType.NUMBER:
        parser._advance()
        return _parse_number(token.value)
    if token.type is TokenType.STRING:
        parser._advance()
        return token.value
    if token.type is TokenType.KEYWORD and token.value in ("TRUE", "FALSE"):
        parser._advance()
        return token.value == "TRUE"
    if token.type is TokenType.KEYWORD and token.value == "NULL":
        parser._advance()
        return None
    raise ParseError(f"unexpected value {token.value!r}", token.line, token.column)


def parse_select(parser: Parser) -> ast.Select:
    """解析 SELECT 语句。"""
    parser._expect_keyword("SELECT")
    projections = [_parse_projection(parser)]
    while _match_punct(parser, ","):
        projections.append(_parse_projection(parser))
    table = ""
    alias: str | None = None
    joins: tuple[ast.JoinClause, ...] = ()
    if parser._match_keyword("FROM"):
        table = _parse_ident(parser)
        from tinydb.parser.join_parser import _parse_optional_alias, parse_join_clauses
        alias = _parse_optional_alias(parser)
        joins = parse_join_clauses(parser)
    where = None
    if parser._match_keyword("WHERE"):
        where = parse_expression(parser)
    group_by_list: list[object] = []
    if parser._match_keyword("GROUP"):
        parser._expect_keyword("BY")
        group_by_list = [_parse_group_expr(parser)]
        while _match_punct(parser, ","):
            group_by_list.append(_parse_group_expr(parser))
    order_by_list: list[ast.OrderItem] = []
    if parser._match_keyword("ORDER"):
        parser._expect_keyword("BY")
        order_by_list = [_parse_order_item(parser)]
        while _match_punct(parser, ","):
            order_by_list.append(_parse_order_item(parser))
    limit = None
    if parser._match_keyword("LIMIT"):
        limit = _parse_int_literal(parser)
    offset = None
    if parser._match_keyword("OFFSET"):
        offset = _parse_int_literal(parser)
    return ast.Select(
        projections=tuple(projections),
        table=table,
        joins=joins,
        alias=alias,
        where=where,
        order_by=tuple(order_by_list),
        limit=limit,
        offset=offset,
        group_by=tuple(group_by_list),
    )


def _parse_projection(parser: Parser) -> object:
    """解析单个投影（列 / Star / 聚合 / 字面）。"""
    if parser._peek().value == "*":
        parser._advance()
        return ast.Star()
    # 聚合函数
    token = parser._peek()
    if token.type is TokenType.KEYWORD and token.value in ("COUNT", "SUM", "AVG"):
        func = parser._advance().value
        parser._expect_punct("(")
        if parser._peek().value == "*":
            parser._advance()
            parser._expect_punct(")")
            return ast.SqlLiteral(value=f"{func}(*)", raw=f"{func}(*)")
        arg = parse_primary(parser)
        parser._expect_punct(")")
        arg_name = arg.name if isinstance(arg, ast.Column) else str(arg)
        return ast.SqlLiteral(value=f"{func}({arg_name})", raw=f"{func}({arg_name})")
    # 字面量
    if token.type in (TokenType.NUMBER, TokenType.STRING):
        return parse_primary(parser)
    # 普通列（可能限定）
    expr = _parse_column_ref(parser)
    if parser._match_keyword("AS"):
        alias = _parse_ident(parser)
        expr = ast.Column(name=alias)
    return expr


def _parse_group_expr(parser: Parser) -> object:
    """解析 GROUP BY 表达式。"""
    return _parse_column_ref(parser)


def _parse_column_ref(parser: Parser) -> object:
    """解析可能限定的列引用（column 或 table.column）。"""
    name = _parse_ident(parser)
    if parser._peek().type is TokenType.PUNCT and parser._peek().value == ".":
        parser._advance()
        col = _parse_ident(parser)
        return ast.QualifiedColumn(table=name, name=col)
    return ast.Column(name=name)


def _parse_order_item(parser: Parser) -> ast.OrderItem:
    """解析 ORDER BY 项。"""
    from typing import Literal

    expr: object = _parse_column_ref(parser)
    direction: Literal["ASC", "DESC"] = "ASC"
    if parser._match_keyword("ASC"):
        direction = "ASC"
    elif parser._match_keyword("DESC"):
        direction = "DESC"
    return ast.OrderItem(expr=expr, direction=direction)


def _parse_int_literal(parser: Parser) -> int:
    """解析整数。"""
    token = parser._expect(TokenType.NUMBER)
    return int(token.value)


def parse_update(parser: Parser) -> ast.Update:
    """解析 UPDATE 语句。"""
    parser._expect_keyword("UPDATE")
    table = _parse_ident(parser)
    parser._expect_keyword("SET")
    assignments = [_parse_assignment(parser)]
    while _match_punct(parser, ","):
        assignments.append(_parse_assignment(parser))
    where = None
    if parser._match_keyword("WHERE"):
        where = parse_expression(parser)
    return ast.Update(table=table, assignments=tuple(assignments), where=where)


def _parse_assignment(parser: Parser) -> tuple[str, object]:
    """解析 SET col = value。"""
    col = _parse_ident(parser)
    parser._expect(TokenType.OPERATOR, "=")
    value = _parse_value(parser)
    return (col, value)


def parse_delete(parser: Parser) -> ast.Delete:
    """解析 DELETE 语句。"""
    parser._expect_keyword("DELETE")
    parser._expect_keyword("FROM")
    table = _parse_ident(parser)
    where = None
    if parser._match_keyword("WHERE"):
        where = parse_expression(parser)
    return ast.Delete(table=table, where=where)


def _parse_ident(parser: Parser) -> str:
    """解析标识符。"""
    token = parser._expect(TokenType.IDENT)
    return token.value


def _match_punct(parser: Parser, punct: str) -> bool:
    """匹配并消耗标点。"""
    token = parser._peek()
    if token.type is TokenType.PUNCT and token.value == punct:
        parser._advance()
        return True
    return False


__all__: list[str] = [
    "parse_insert",
    "parse_select",
    "parse_update",
    "parse_delete",
]
