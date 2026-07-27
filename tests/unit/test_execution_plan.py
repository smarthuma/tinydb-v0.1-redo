"""执行计划测试（REQ-EP-001..010）。"""

from __future__ import annotations

from tinydb.executor.index_plan import IndexPlanner
from tinydb.executor.plan_nodes import (
    IndexScan,
    NestedLoopJoin,
    TableScan,
    plan_to_dict,
    render_plan,
)
from tinydb.parser.ast import JoinClause, JoinType


class FakeMeta:
    """测试用 catalog 元数据。"""

    def __init__(
        self,
        name: str,
        schema: tuple[tuple[str, object], ...] = (("id", None), ("name", None)),
        row_count: int = 1000,
        indexes: tuple[tuple[str, int], ...] = (),
    ) -> None:
        self.name = name
        self.schema = schema
        self.root_page_id = 2
        self.indexes = indexes
        self.row_count = row_count


class FakeCatalog:
    """测试用 catalog。"""

    def __init__(self, tables: dict[str, FakeMeta]) -> None:
        self._tables = tables

    def get_table(self, name: str) -> FakeMeta:
        return self._tables[name]


class TestPlanNodes:
    """计划节点（REQ-EP-001）。"""

    def test_table_scan_node(self) -> None:
        node = TableScan(table="users", estimated_rows=1000, estimated_cost=20.0)
        assert node.node_type == "TableScan"

    def test_index_scan_node(self) -> None:
        node = IndexScan(
            table="users", column="id", seek_key=42,
            estimated_rows=1, estimated_cost=4.0,
        )
        assert node.node_type == "IndexScan"

    def test_nested_loop_join_node(self) -> None:
        left = TableScan(table="A", estimated_rows=100, estimated_cost=2.0)
        right = TableScan(table="B", estimated_rows=50, estimated_cost=1.0)
        node = NestedLoopJoin(left=left, right=right, estimated_cost=202.0)
        assert node.node_type == "NestedLoopJoin"


class TestIndexPlanner:
    """索引决策（REQ-EP-002）。"""

    def test_equality_on_index_uses_index_scan(self) -> None:
        """等值查询在索引列上选 IndexScan。"""
        from tinydb.parser.ast import BinaryOp, Column, SqlLiteral

        catalog = FakeCatalog({"users": FakeMeta("users", indexes=(("id", 5),))})
        planner = IndexPlanner()
        where = BinaryOp(op="=", left=Column(name="id"), right=SqlLiteral(value=42, raw="42"))
        plan = planner.plan_select("users", (), where, (), None, None, (), catalog)

        assert isinstance(plan, IndexScan)
        assert plan.column == "id"
        assert plan.seek_key == 42

    def test_non_indexed_column_uses_table_scan(self) -> None:
        """非索引列选 TableScan。"""
        from tinydb.parser.ast import BinaryOp, Column, SqlLiteral

        catalog = FakeCatalog({"users": FakeMeta("users", indexes=())})
        planner = IndexPlanner()
        where = BinaryOp(op="=", left=Column(name="email"), right=SqlLiteral(value="x", raw="'x'"))
        plan = planner.plan_select("users", (), where, (), None, None, (), catalog)

        assert isinstance(plan, TableScan)

    def test_join_produces_nested_loop_join(self) -> None:
        """JOIN 产生 NestedLoopJoin 节点。"""
        from tinydb.parser.ast import BinaryOp, Column

        catalog = FakeCatalog({
            "A": FakeMeta("A"),
            "B": FakeMeta("B"),
        })
        planner = IndexPlanner()
        join = JoinClause(
            kind=JoinType.INNER,
            table="B",
            alias=None,
            on=BinaryOp(op="=", left=Column(name="id"), right=Column(name="id")),
        )
        plan = planner.plan_select("A", (join,), None, (), None, None, (), catalog)

        assert isinstance(plan, NestedLoopJoin)


class TestPlanSerialization:
    """计划序列化与渲染（REQ-EP-005,006）。"""

    def test_plan_to_dict(self) -> None:
        node = TableScan(table="users", estimated_rows=100, estimated_cost=2.0)
        d = plan_to_dict(node)
        assert d["node"] == "TableScan"
        assert d["table"] == "users"
        assert d["estimated_rows"] == 100

    def test_render_plan_indented(self) -> None:
        node = TableScan(table="users", estimated_rows=100, estimated_cost=2.0)
        rendered = render_plan(node)
        assert "TableScan" in rendered
        assert "estimated_rows: 100" in rendered
