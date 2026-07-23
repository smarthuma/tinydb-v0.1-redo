"""DDL 解析：CREATE TABLE / DROP TABLE（REQ-SP-002）。"""

from __future__ import annotations

from typing import TYPE_CHECKING

from tinydb.parser import ast

if TYPE_CHECKING:
    from tinydb.parser import Parser

from tinydb.parser.lexer import TokenType


def parse_create_table(parser: Parser) -> ast.CreateTable:
    """解析 CREATE TABLE 语句。"""
    parser._expect_keyword("CREATE")
    parser._expect_keyword("TABLE")
    if_not_exists = False
    if parser._match_keyword("IF"):
        parser._expect_keyword("NOT")
        parser._expect_keyword("EXISTS")
        if_not_exists = True
    name_token = parser._expect(TokenType.IDENT)
    parser._expect(TokenType.PUNCT, "(")
    columns = [_parse_column_def(parser)]
    while _match_punct(parser, ","):
        columns.append(_parse_column_def(parser))
    parser._expect(TokenType.PUNCT, ")")
    return ast.CreateTable(
        name=name_token.value, columns=tuple(columns), if_not_exists=if_not_exists
    )


def _parse_column_def(parser: Parser) -> ast.ColumnDef:
    """解析单个列定义。"""
    name_token = parser._expect(TokenType.IDENT)
    type_token = parser._expect(TokenType.KEYWORD)
    constraints: list[str] = []
    while parser._peek().type is TokenType.KEYWORD:
        kw = parser._peek().value.upper()
        if kw in ("PRIMARY", "NOT", "UNIQUE"):
            if kw == "PRIMARY":
                parser._advance()
                parser._expect_keyword("KEY")
                constraints.append("PRIMARY KEY")
            elif kw == "NOT":
                parser._advance()
                parser._expect_keyword("NULL")
                constraints.append("NOT NULL")
            elif kw == "UNIQUE":
                parser._advance()
                constraints.append("UNIQUE")
        else:
            break
    return ast.ColumnDef(
        name=name_token.value,
        col_type=type_token.value,
        constraints=tuple(constraints),
    )


def parse_drop_table(parser: Parser) -> ast.DropTable:
    """解析 DROP TABLE 语句。"""
    parser._expect_keyword("DROP")
    parser._expect_keyword("TABLE")
    if_exists = False
    if parser._match_keyword("IF"):
        parser._expect_keyword("EXISTS")
        if_exists = True
    names = [_parse_ident(parser)]
    while _match_punct(parser, ","):
        names.append(_parse_ident(parser))
    return ast.DropTable(names=tuple(names), if_exists=if_exists)


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


__all__: list[str] = ["parse_create_table", "parse_drop_table"]
