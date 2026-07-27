"""JOIN 查询测试（REQ-JQ-001..012）。"""

from __future__ import annotations

from tinydb.parser import parse
from tinydb.parser.ast import Explain, JoinType, Select


class TestJoinParsing:
    """JOIN 解析（REQ-JQ-001..007）。"""

    def test_inner_join_basic(self) -> None:
        """基本 INNER JOIN 解析。"""
        stmt = parse("SELECT * FROM A INNER JOIN B ON A.id = B.id")
        assert isinstance(stmt, Select)
        assert stmt.table == "A"
        assert len(stmt.joins) == 1
        assert stmt.joins[0].kind == JoinType.INNER
        assert stmt.joins[0].table == "B"

    def test_left_join(self) -> None:
        """LEFT JOIN 解析。"""
        stmt = parse("SELECT * FROM A LEFT JOIN B ON A.id = B.id")
        assert stmt.joins[0].kind == JoinType.LEFT

    def test_join_without_inner_keyword(self) -> None:
        """JOIN 默认 INNER。"""
        stmt = parse("SELECT * FROM A JOIN B ON A.id = B.id")
        assert stmt.joins[0].kind == JoinType.INNER

    def test_chain_join(self) -> None:
        """链式三表 JOIN。"""
        stmt = parse(
            "SELECT * FROM A JOIN B ON A.id = B.id JOIN C ON B.id = C.id",
        )
        assert len(stmt.joins) == 2
        assert stmt.joins[0].table == "B"
        assert stmt.joins[1].table == "C"

    def test_join_with_alias(self) -> None:
        """JOIN 带 AS 别名。"""
        stmt = parse("SELECT * FROM A a INNER JOIN B b ON a.id = b.id")
        assert stmt.table == "A"
        assert stmt.joins[0].table == "B"
        assert stmt.joins[0].alias == "b"

    def test_join_with_implicit_alias(self) -> None:
        """JOIN 带隐式别名（无 AS）。"""
        stmt = parse("SELECT * FROM A a JOIN B b ON a.id = b.id")
        assert stmt.joins[0].alias == "b"

    def test_join_on_and_condition(self) -> None:
        """JOIN ON 条件含 AND。"""
        stmt = parse(
            "SELECT * FROM A JOIN B ON A.id = B.id AND A.name = B.name",
        )
        assert len(stmt.joins) == 1

    def test_single_table_select_backward_compat(self) -> None:
        """单表 SELECT 向后兼容（joins=()）。"""
        stmt = parse("SELECT * FROM users")
        assert isinstance(stmt, Select)
        assert stmt.table == "users"
        assert stmt.joins == ()

    def test_join_with_where_order_limit(self) -> None:
        """JOIN + WHERE + ORDER BY + LIMIT。"""
        stmt = parse(
            "SELECT a.name, B.score FROM A a "
            "INNER JOIN B ON a.id = B.id "
            "WHERE B.score > 80 "
            "ORDER BY B.score DESC LIMIT 10",
        )
        assert len(stmt.joins) == 1
        assert stmt.where is not None
        assert stmt.limit == 10


class TestExplainParsing:
    """EXPLAIN 解析。"""

    def test_explain_select(self) -> None:
        """EXPLAIN SELECT 解析为 Explain 节点。"""
        stmt = parse("EXPLAIN SELECT * FROM users")
        assert isinstance(stmt, Explain)
        assert isinstance(stmt.statement, Select)
