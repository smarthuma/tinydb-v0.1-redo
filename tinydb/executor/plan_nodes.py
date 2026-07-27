"""执行计划节点（REQ-EP-001）。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True)
class TableScan:
    """全表扫描。"""

    node_type: Literal["TableScan"] = "TableScan"
    table: str = ""
    estimated_rows: int = 0
    estimated_cost: float = 0.0


@dataclass(frozen=True)
class IndexScan:
    """索引扫描。"""

    node_type: Literal["IndexScan"] = "IndexScan"
    table: str = ""
    column: str = ""
    seek_key: object = None
    estimated_rows: int = 0
    estimated_cost: float = 0.0


@dataclass(frozen=True)
class Filter:
    """WHERE 过滤。"""

    node_type: Literal["Filter"] = "Filter"
    predicate: object = None
    child: object = None
    estimated_rows: int = 0
    estimated_cost: float = 0.0


@dataclass(frozen=True)
class NestedLoopJoin:
    """嵌套循环连接。"""

    node_type: Literal["NestedLoopJoin"] = "NestedLoopJoin"
    left: object = None
    right: object = None
    condition: object = None
    estimated_rows: int = 0
    estimated_cost: float = 0.0


@dataclass(frozen=True)
class HashJoin:
    """哈希连接。"""

    node_type: Literal["HashJoin"] = "HashJoin"
    left: object = None
    right: object = None
    condition: object = None
    estimated_rows: int = 0
    estimated_cost: float = 0.0


@dataclass(frozen=True)
class Project:
    """投影。"""

    node_type: Literal["Project"] = "Project"
    columns: tuple[object, ...] = ()
    child: object = None
    estimated_rows: int = 0
    estimated_cost: float = 0.0


@dataclass(frozen=True)
class Sort:
    """排序。"""

    node_type: Literal["Sort"] = "Sort"
    keys: tuple[object, ...] = ()
    child: object = None
    estimated_rows: int = 0
    estimated_cost: float = 0.0


@dataclass(frozen=True)
class Limit:
    """LIMIT/OFFSET。"""

    node_type: Literal["Limit"] = "Limit"
    limit: int | None = None
    offset: int | None = None
    child: object = None
    estimated_rows: int = 0
    estimated_cost: float = 0.0


@dataclass(frozen=True)
class Aggregate:
    """聚合。"""

    node_type: Literal["Aggregate"] = "Aggregate"
    group_by: tuple[object, ...] = ()
    aggregates: tuple[object, ...] = ()
    child: object = None
    estimated_rows: int = 0
    estimated_cost: float = 0.0


PlanNode = (
    TableScan
    | IndexScan
    | Filter
    | NestedLoopJoin
    | HashJoin
    | Project
    | Sort
    | Limit
    | Aggregate
)


def plan_to_dict(node: object) -> dict[str, object]:
    """将计划节点树序列化为 dict（供 EXPLAIN 输出）。"""
    if node is None:
        return {}
    d: dict[str, object] = {"node": getattr(node, "node_type", "Unknown")}
    for key, value in vars(node).items():
        if key in ("node_type", "estimated_rows", "estimated_cost"):
            continue
        if key in ("left", "right", "child", "condition"):
            continue
        d[key] = value
    d["estimated_rows"] = getattr(node, "estimated_rows", 0)
    d["estimated_cost"] = getattr(node, "estimated_cost", 0.0)
    children: list[object] = []
    child = getattr(node, "child", None)
    left = getattr(node, "left", None)
    right = getattr(node, "right", None)
    if child is not None:
        children.append(child)
    if left is not None:
        children.append(left)
    if right is not None:
        children.append(right)
    if children:
        d["children"] = [plan_to_dict(c) for c in children]
    return d


def render_plan(node: object, indent: int = 0) -> str:
    """渲染计划树为缩进字符串。"""
    if node is None:
        return ""
    prefix = "  " * indent
    name = getattr(node, "node_type", "Unknown")
    rows = getattr(node, "estimated_rows", 0)
    cost = getattr(node, "estimated_cost", 0.0)
    parts = [f"{name} [estimated_rows: {rows}, cost: {cost:.1f}]"]
    if isinstance(node, IndexScan) and node.column:
        parts.append(f"  {node.table}.{node.column} = {node.seek_key!r}")
    line = prefix + " ".join(parts)
    children: list[str] = []
    if hasattr(node, "child") and node.child is not None:
        children.append(render_plan(node.child, indent + 1))
    if hasattr(node, "left") and node.left is not None:
        children.append(render_plan(node.left, indent + 1))
    if hasattr(node, "right") and node.right is not None:
        children.append(render_plan(node.right, indent + 1))
    if children:
        line += "\n" + "\n".join(c for c in children if c)
    return line


__all__: list[str] = [
    "TableScan",
    "IndexScan",
    "Filter",
    "NestedLoopJoin",
    "HashJoin",
    "Project",
    "Sort",
    "Limit",
    "Aggregate",
    "PlanNode",
    "plan_to_dict",
    "render_plan",
]
