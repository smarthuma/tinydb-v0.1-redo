"""SQL 解析器子包：lexer → AST → 各语句解析器。

公共入口 ``parse(sql: str) -> Statement``（REQ-SP-007）。
"""

from __future__ import annotations

from typing import Protocol

from tinydb.errors import ParseError
from tinydb.parser import tx_control as _tx_control
from tinydb.parser.ast import Statement
from tinydb.parser.ddl_parser import parse_create_table, parse_drop_table
from tinydb.parser.dml_parser import parse_delete, parse_insert, parse_select, parse_update
from tinydb.parser.lexer import Token, TokenType, tokenize

__all__: list[str] = ["parse", "tokenize", "Token"]


class Parser(Protocol):
    """解析器接口（跨模块使用）。"""

    def _peek(self) -> Token: ...
    def _advance(self) -> Token: ...
    def _expect(self, expected: object, value: str | None = None) -> Token: ...
    def _expect_punct(self, punct: str) -> Token: ...
    def _expect_keyword(self, keyword: str) -> Token: ...
    def _match_keyword(self, keyword: str) -> Token | None: ...
    def _is_keyword(self, keyword: str) -> bool: ...


def parse(sql: str) -> Statement:
    """SQL 字符串 → AST（公共入口，纯函数）。"""
    tokens = tokenize(sql)
    # 移除末尾可选的分号
    if tokens and tokens[-1].type is not TokenType.EOF:
        # 分号不是 EOF 之后的 token；检查倒数第二
        pass
    # 过滤掉末尾分号 token（EOF 之前）
    filtered = [
        t for t in tokens if not (t.type is TokenType.PUNCT and t.value == ";")
    ]
    filtered.append(Token(TokenType.EOF, "", filtered[-1].line if filtered else 1, 1))
    parser = _Parser(filtered)
    statement = parser.parse_statement()
    parser._expect(TokenType.EOF)
    return statement


class _Parser:
    """递归下降解析器。"""

    def __init__(self, tokens: list[Token]) -> None:
        self._tokens = tokens
        self._pos = 0

    def parse_statement(self) -> Statement:
        token = self._peek()
        if token.type is TokenType.KEYWORD:
            keyword = token.value.upper()
            if keyword == "CREATE":
                return parse_create_table(self)
            if keyword == "DROP":
                return parse_drop_table(self)
            if keyword == "INSERT":
                return parse_insert(self)
            if keyword == "SELECT":
                return parse_select(self)
            if keyword == "UPDATE":
                return parse_update(self)
            if keyword == "DELETE":
                return parse_delete(self)
            if keyword == "CHECKPOINT":
                self._advance()
                from tinydb.parser.ast import Checkpoint

                return Checkpoint()
            statement = _tx_control.parse_tx_control(self)
            return statement  # type: ignore[return-value]
        raise ParseError(
            f"unexpected token: {token.value!r}", token.line, token.column
        )

    def _peek(self) -> Token:
        return self._tokens[min(self._pos, len(self._tokens) - 1)]

    def _advance(self) -> Token:
        token = self._peek()
        if self._pos < len(self._tokens) - 1:
            self._pos += 1
        return token

    def _expect(self, expected: object, value: str | None = None) -> Token:
        token = self._peek()
        if token.type is not expected:
            raise ParseError(
                f"expected {expected}, got {token.value!r}",
                token.line,
                token.column,
            )
        if value is not None and token.value != value:
            raise ParseError(
                f"expected {value!r}, got {token.value!r}",
                token.line,
                token.column,
            )
        return self._advance()

    def _expect_punct(self, punct: str) -> Token:
        return self._expect(TokenType.PUNCT, punct)

    def _match_keyword(self, keyword: str) -> Token | None:
        token = self._peek()
        if token.type is TokenType.KEYWORD and token.value.upper() == keyword:
            return self._advance()
        return None

    def _expect_keyword(self, keyword: str) -> Token:
        token = self._peek()
        if token.type is TokenType.KEYWORD and token.value.upper() == keyword:
            return self._advance()
        raise ParseError(
            f"expected keyword {keyword}, got {token.value!r}",
            token.line,
            token.column,
        )

    def _is_keyword(self, keyword: str) -> bool:
        token = self._peek()
        return token.type is TokenType.KEYWORD and token.value.upper() == keyword
