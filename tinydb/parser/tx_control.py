"""事务控制解析：BEGIN / COMMIT / ROLLBACK（REQ-TM-007）。"""

from __future__ import annotations

from typing import TYPE_CHECKING

from tinydb.parser import ast

if TYPE_CHECKING:
    from tinydb.parser import Parser



def parse_tx_control(parser: Parser) -> object:
    """解析 BEGIN / COMMIT / ROLLBACK。"""
    token = parser._peek()
    keyword = token.value.upper()
    parser._advance()
    if keyword == "BEGIN":
        parser._match_keyword("TRANSACTION")
        return ast.Begin()
    if keyword in ("COMMIT", "END"):
        return ast.Commit()
    if keyword == "ROLLBACK":
        return ast.Rollback()
    from tinydb.errors import ParseError

    raise ParseError(
        f"unexpected transaction keyword {keyword!r}", token.line, token.column
    )


__all__: list[str] = ["parse_tx_control"]
