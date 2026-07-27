"""JOIN 解析：INNER/LEFT JOIN 子句（REQ-JQ-001..007）。"""

from __future__ import annotations

from typing import TYPE_CHECKING

from tinydb.parser import ast
from tinydb.parser.lexer import TokenType

if TYPE_CHECKING:
    from tinydb.parser import Parser


def parse_join_clauses(parser: Parser) -> tuple[ast.JoinClause, ...]:
    """解析零个或多个 JOIN 子句。"""
    joins: list[ast.JoinClause] = []
    while _match_join_start(parser):
        joins.append(_parse_join_clause(parser))
    return tuple(joins)


def _match_join_start(parser: Parser) -> bool:
    """检查下一个 token 是否是 JOIN 起始。"""
    token = parser._peek()
    if token.type is not TokenType.KEYWORD:
        return False
    return token.value.upper() in ("JOIN", "INNER", "LEFT")


def _parse_join_clause(parser: Parser) -> ast.JoinClause:
    """解析单个 JOIN 子句: [INNER|LEFT] JOIN table [AS alias] ON condition。"""
    token = parser._peek()
    kind = ast.JoinType.INNER
    if token.value.upper() == "LEFT":
        kind = ast.JoinType.LEFT
        parser._advance()
        parser._expect_keyword("JOIN")
    elif token.value.upper() == "INNER":
        parser._advance()
        parser._expect_keyword("JOIN")
    else:
        parser._expect_keyword("JOIN")
    table = _parse_ident(parser)
    alias = _parse_optional_alias(parser)
    parser._expect_keyword("ON")
    from tinydb.parser.predicate import parse_expression

    on = parse_expression(parser)
    return ast.JoinClause(kind=kind, table=table, alias=alias, on=on)


def _parse_optional_alias(parser: Parser) -> str | None:
    """解析可选的 [AS] alias。

    词法分析器已将保留字标记为 KEYWORD、标识符标记为 IDENT，
    所以紧跟表名后的 IDENT 必为隐式别名。
    """
    if parser._match_keyword("AS"):
        return _parse_ident(parser)
    if parser._peek().type is TokenType.IDENT:
        return _parse_ident(parser)
    return None


def _parse_ident(parser: Parser) -> str:
    """解析标识符。"""
    token = parser._expect(TokenType.IDENT)
    return token.value


__all__ = ["parse_join_clauses"]
