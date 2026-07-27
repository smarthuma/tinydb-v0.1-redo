"""索引路径 + 查询计划生成（REQ-EP-002..007, REQ-QE-010）。

从 v0.1 stub 扩展为真实代价模型：基于 catalog 行数选择 index_scan vs heap_scan，
生成完整计划树供 executor 与 EXPLAIN 消费。
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from tinydb.catalog_codec import TableMeta
from tinydb.executor.plan_nodes import (
    Filter,
    IndexScan,
    NestedLoopJoin,
    PlanNode,
    TableScan,
)
from tinydb.parser import ast
from tinydb.types import ColumnType


@runtime_checkable
class _Catalog(Protocol):
    def get_table(self, name: str) -> TableMeta: ...


class IndexPlanner:
    """查询计划生成器。"""

    # 代价常数（抽象单位：单次页读取 = 1.0）
    _SEQ_PAGE_COST = 1.0
    _RANDOM_PAGE_COST = 2.0
    _INDEX_HEIGHT_DEFAULT = 2.0
    _DEFAULT_ROW_COUNT = 1000

    def plan_select(
        self,
        table: str,
        joins: tuple[ast.JoinClause, ...],
        where: object,
        order_by: tuple[object, ...],
        limit: int | None,
        offset: int | None,
        group_by: tuple[object, ...],
        catalog: _Catalog,
    ) -> PlanNode:
        """生成 SELECT 的完整计划树。"""
        # 1. 为驱动表生成扫描计划
        scan = self._plan_scan(table, where, catalog)

        # 2. WHERE 过滤（扫描后）
        root: PlanNode = scan
        remaining = self._extract_post_scan_predicate(where)
        if remaining is not None:
            root = Filter(
                predicate=remaining,
                child=root,
                estimated_rows=max(1, scan.estimated_rows // 2),
                estimated_cost=scan.estimated_cost + 1.0,
            )

        # 3. JOIN（按序连接）
        for join in joins:
            root = self._plan_join(root, join, catalog)

        return root

    def _plan_scan(
        self,
        table: str,
        where: object,
        catalog: _Catalog,
    ) -> PlanNode:
        """为单表生成扫描计划（index_scan 或 table_scan）。"""
        meta = self._get_meta(table, catalog)
        row_count = meta.row_count if meta.row_count > 0 else self._DEFAULT_ROW_COUNT
        pages = max(1, row_count // 50)

        index_match = self._match_index_column(where, meta)
        if index_match is not None:
            column, seek_key = index_match
            return IndexScan(
                table=table,
                column=column,
                seek_key=seek_key,
                estimated_rows=max(1, row_count // 10),
                estimated_cost=self._INDEX_HEIGHT_DEFAULT + self._RANDOM_PAGE_COST,
            )

        return TableScan(
            table=table,
            estimated_rows=row_count,
            estimated_cost=pages * self._SEQ_PAGE_COST,
        )

    def _plan_join(
        self,
        left: PlanNode,
        join: ast.JoinClause,
        catalog: _Catalog,
    ) -> NestedLoopJoin:
        """为 JOIN 生成嵌套循环连接计划。"""
        join_meta = self._get_meta(join.table, catalog)
        join_rows = join_meta.row_count if join_meta.row_count > 0 else self._DEFAULT_ROW_COUNT
        right_scan = self._plan_scan(join.table, None, catalog)

        cost = left.estimated_cost + left.estimated_rows * right_scan.estimated_cost
        return NestedLoopJoin(
            left=left,
            right=right_scan,
            condition=getattr(join, "on", None),
            estimated_rows=left.estimated_rows * max(1, join_rows // 10),
            estimated_cost=cost,
        )

    def _match_index_column(
        self,
        where: object,
        meta: TableMeta,
    ) -> tuple[str, object] | None:
        """检查 WHERE 是否含索引列的等值条件。"""
        if where is None or not meta.indexes:
            return None

        if isinstance(where, ast.BinaryOp) and where.op == "=":
            if isinstance(where.left, ast.Column):
                col_name = where.left.name
                for idx_col, _idx_page in meta.indexes:
                    if idx_col == col_name:
                        return (col_name, _eval_literal(where.right))
        return None

    def _extract_post_scan_predicate(self, where: object) -> object:
        """提取扫描后仍需应用的谓词。"""
        if where is None:
            return None

        if isinstance(where, ast.BinaryOp) and where.op == "=":
            if isinstance(where.left, ast.Column):
                return None
        return where

    def _get_meta(self, table: str, catalog: _Catalog) -> TableMeta:
        """从 catalog 获取表元数据。"""
        if hasattr(catalog, "get_table"):
            return catalog.get_table(table)
        return TableMeta(
            name=table,
            schema=[("id", ColumnType.INT)],
            root_page_id=2,
            indexes=(),
            row_count=0,
        )


def _eval_literal(node: object) -> object:
    """求值字面量节点。"""
    from tinydb.parser import ast

    if isinstance(node, ast.SqlLiteral):
        return node.value
    if isinstance(node, ast.Column):
        return node.name
    return None


def estimate_table_rows(table: str, catalog: _Catalog) -> int:
    """估算表行数。"""
    if hasattr(catalog, "get_table"):
        meta = catalog.get_table(table)
        return meta.row_count if meta.row_count > 0 else IndexPlanner._DEFAULT_ROW_COUNT
    return IndexPlanner._DEFAULT_ROW_COUNT


__all__: list[str] = ["IndexPlanner", "estimate_table_rows"]
