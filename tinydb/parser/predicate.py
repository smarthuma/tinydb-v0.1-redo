"""谓词解析：AND/OR 优先级、BETWEEN、IN、IS NULL（REQ-SP-004/005/006）。"""

from __future__ import annotations

from typing import TYPE_CHECKING

from tinydb.parser import ast

if TYPE_CHECKING:
    from tinydb.parser import Parser

from tinydb.errors import ParseError
from tinydb.parser.lexer import TokenType


def parse_expression(parser: Parser) -> object:
    """解析 OR 表达式（最低优先级）。"""
    left = parse_and_expression(parser)
    while parser._match_keyword("OR"):
        right = parse_and_expression(parser)
        left = ast.LogicalOp(op="OR", left=left, right=right)
    return left


def parse_and_expression(parser: Parser) -> object:
    """解析 AND 表达式。"""
    left = parse_not_expression(parser)
    while parser._match_keyword("AND"):
        right = parse_not_expression(parser)
        left = ast.LogicalOp(op="AND", left=left, right=right)
    return left


def parse_not_expression(parser: Parser) -> object:
    """解析 NOT / 比较 / 原子表达式。"""
    return parse_comparison(parser)


def parse_comparison(parser: Parser) -> object:
    """解析比较表达式。"""
    left = parse_primary(parser)

    # IS NULL / IS NOT NULL
    if parser._match_keyword("IS"):
        negated = False
        if parser._match_keyword("NOT"):
            negated = True
        parser._expect_keyword("NULL")
        op = "IS NOT NULL" if negated else "IS NULL"
        return ast.BinaryOp(op=op, left=left, right=ast.SqlLiteral(None, "NULL"))

    # [NOT] IN (...)
    if parser._match_keyword("NOT"):
        parser._expect_keyword("IN")
        values = _parse_in_list(parser)
        return ast.InPredicate(expr=left, values=values, negated=True)

    if parser._match_keyword("IN"):
        values = _parse_in_list(parser)
        return ast.InPredicate(expr=left, values=values, negated=False)

    # [NOT] BETWEEN a AND b
    if parser._match_keyword("BETWEEN"):
        lo = parse_primary(parser)
        parser._expect_keyword("AND")
        hi = parse_primary(parser)
        return ast.LogicalOp(
            op="AND",
            left=ast.BinaryOp(op=">=", left=left, right=lo),
            right=ast.BinaryOp(op="<=", left=left, right=hi),
        )

    token = parser._peek()
    if token.type is TokenType.OPERATOR:
        parser._advance()
        right = parse_primary(parser)
        return ast.BinaryOp(op=token.value, left=left, right=right)

    return left


def _parse_in_list(parser: Parser) -> tuple[object, ...]:
    """解析 IN (...) 的值列表。"""
    parser._expect_punct("(")
    values = [_parse_value(parser)]
    while _match_punct(parser, ","):
        values.append(_parse_value(parser))
    parser._expect_punct(")")
    return tuple(values)


def parse_primary(parser: Parser) -> object:
    """解析原子表达式。"""
    token = parser._peek()

    if token.type is TokenType.NUMBER:
        parser._advance()
        value: object = _parse_number(token.value)
        return ast.SqlLiteral(value=value, raw=token.value)

    if token.type is TokenType.STRING:
        parser._advance()
        return ast.SqlLiteral(value=token.value, raw=f"'{token.value}'")

    if token.type is TokenType.KEYWORD and token.value in ("TRUE", "FALSE"):
        parser._advance()
        return ast.SqlLiteral(value=token.value == "TRUE", raw=token.value)

    if token.type is TokenType.KEYWORD and token.value == "NULL":
        parser._advance()
        return ast.SqlLiteral(value=None, raw="NULL")

    if token.type is TokenType.IDENT:
        parser._advance()
        # 限定列：table.column
        if parser._peek().type is TokenType.PUNCT and parser._peek().value == ".":
            parser._advance()  # 消耗 '.'
            col_token = parser._expect(TokenType.IDENT)
            return ast.QualifiedColumn(table=token.value, name=col_token.value)
        return ast.Column(name=token.value)

    if token.type is TokenType.PUNCT and token.value == "(":
        parser._advance()
        expr = parse_expression(parser)
        parser._expect_punct(")")
        return expr

    raise ParseError(
        f"unexpected token {token.value!r}", token.line, token.column
    )


def _parse_value(parser: Parser) -> object:
    """解析 IN 列表中的值。"""
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
    raise ParseError(
        f"unexpected value {token.value!r}", token.line, token.column
    )


def _parse_number(text: str) -> object:
    """解析数字字面。"""
    if "." in text:
        return float(text)
    return int(text)


def _match_punct(parser: Parser, punct: str) -> bool:
    """匹配并消耗标点。"""
    token = parser._peek()
    if token.type is TokenType.PUNCT and token.value == punct:
        parser._advance()
        return True
    return False


__all__: list[str] = ["parse_expression"]
