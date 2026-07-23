"""SQL 解析器子包：lexer → AST → 各语句解析器。

公共入口 `parse(sql: str) -> Statement` 在 Batch 7 填充（REQ-SP-007）。
"""

__all__: list[str] = ["parse"]


def parse(sql: str):  # noqa: ANN001, ANN201 — 占位，Batch 7 替换
    """SQL 解析公共入口（占位，Batch 7 实现）。"""
    raise NotImplementedError("parser.parse 在 Batch 7 实现")
