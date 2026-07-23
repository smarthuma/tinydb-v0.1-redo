"""词法分析器（REQ-SP-001）。"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

KEYWORDS = frozenset(
    {
        "CREATE", "TABLE", "IF", "NOT", "EXISTS", "DROP", "INSERT", "INTO",
        "VALUES", "SELECT", "FROM", "WHERE", "ORDER", "BY", "ASC", "DESC",
        "LIMIT", "OFFSET", "GROUP", "UPDATE", "SET", "DELETE", "AND", "OR",
        "NULL", "IS", "IN", "BETWEEN", "TRUE", "FALSE", "PRIMARY", "KEY",
        "UNIQUE", "CHECKPOINT", "BEGIN", "TRANSACTION", "COMMIT", "END",
        "ROLLBACK", "INT", "FLOAT", "TEXT", "BOOL", "INTEGER", "REAL",
        "VARCHAR", "BOOLEAN", "AVG", "SUM", "COUNT", "AS", "JOIN", "ON",
        "LEFT", "RIGHT", "INNER", "OUTER", "CROSS", "NULLS", "FIRST", "LAST",
    }
)


class TokenType(Enum):
    """Token 类型。"""

    KEYWORD = "KEYWORD"
    IDENT = "IDENT"
    NUMBER = "NUMBER"
    STRING = "STRING"
    OPERATOR = "OPERATOR"
    PUNCT = "PUNCT"
    EOF = "EOF"


@dataclass(frozen=True)
class Token:
    """带位置的 typed token。"""

    type: TokenType
    value: str
    line: int
    column: int

    EOF: TokenType = TokenType.EOF  # 便捷访问


Token.EOF = TokenType.EOF


_SINGLE_CHAR_PUNCT = set("(),;*")
_OPERATOR_PATTERNS = ("<>", "<=", ">=", "=", "<", ">")


def tokenize(sql: str) -> list[Token]:
    """把 SQL 字符串转为 token 列表（末尾带 EOF）。"""
    tokens: list[Token] = []
    pos = 0
    line = 1
    column = 1
    length = len(sql)

    while pos < length:
        ch = sql[pos]

        # 跳过空白
        if ch in " \t\r\n":
            if ch == "\n":
                line += 1
                column = 1
            else:
                column += 1
            pos += 1
            continue

        # 行注释
        if ch == "-" and pos + 1 < length and sql[pos + 1] == "-":
            while pos < length and sql[pos] != "\n":
                pos += 1
            continue

        # 字符串字面
        if ch == "'":
            start_col = column
            pos += 1
            column += 1
            parts: list[str] = []
            while pos < length:
                c = sql[pos]
                if c == "'":
                    if pos + 1 < length and sql[pos + 1] == "'":
                        parts.append("'")
                        pos += 2
                        column += 2
                        continue
                    pos += 1
                    column += 1
                    break
                parts.append(c)
                if c == "\n":
                    line += 1
                    column = 1
                else:
                    column += 1
                pos += 1
            tokens.append(Token(TokenType.STRING, "".join(parts), line, start_col))
            continue

        # 数字
        if ch.isdigit() or (ch == "." and pos + 1 < length and sql[pos + 1].isdigit()):
            start_col = column
            start = pos
            while pos < length and (sql[pos].isdigit() or sql[pos] == "."):
                pos += 1
                column += 1
            tokens.append(Token(TokenType.NUMBER, sql[start:pos], line, start_col))
            continue

        # 标识符或关键词
        if ch.isalpha() or ch == "_":
            start_col = column
            start = pos
            while pos < length and (sql[pos].isalnum() or sql[pos] == "_"):
                pos += 1
                column += 1
            word = sql[start:pos]
            if word.upper() in KEYWORDS:
                tokens.append(Token(TokenType.KEYWORD, word.upper(), line, start_col))
            else:
                tokens.append(Token(TokenType.IDENT, word, line, start_col))
            continue

        # 操作符
        start_col = column
        matched = False
        for op in _OPERATOR_PATTERNS:
            if sql[pos : pos + len(op)] == op:
                tokens.append(Token(TokenType.OPERATOR, op, line, start_col))
                pos += len(op)
                column += len(op)
                matched = True
                break
        if matched:
            continue

        # 单字符标点
        if ch in _SINGLE_CHAR_PUNCT:
            tokens.append(Token(TokenType.PUNCT, ch, line, column))
            pos += 1
            column += 1
            continue

        # 未知字符
        from tinydb.errors import ParseError

        raise ParseError(f"unexpected character {ch!r}", line, column)

    tokens.append(Token(TokenType.EOF, "", line, column))
    return tokens


__all__: list[str] = ["Token", "TokenType", "tokenize", "KEYWORDS"]
