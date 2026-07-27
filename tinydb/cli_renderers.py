"""CLI 渲染器：table / csv / JSON lines。"""

from __future__ import annotations

import json
from typing import TextIO


def _truncate(value: str, width: int) -> str:
    """截断超长值并追加 ...。"""
    if width <= 0:
        return value
    if len(value) <= width:
        return value
    return value[:width] + "..."


def print_table(
    rows: list[dict[str, object]],
    stdout: TextIO,
    width: int = 30,
    nullvalue: str = "",
) -> None:
    """渲染 ASCII 表。"""
    if not rows:
        return
    columns = list(rows[0].keys())
    widths = [
        max(len(str(c)), max((len(str(r.get(c, "") or nullvalue)) for r in rows), default=0))
        for c in columns
    ]
    if width > 0:
        widths = [min(w, width) for w in widths]
    header = " | ".join(_truncate(c, w).ljust(w) for c, w in zip(columns, widths, strict=True))
    sep = "-+-".join("-" * w for w in widths)
    print(header, file=stdout)
    print(sep, file=stdout)
    for row in rows:
        line = " | ".join(
            _truncate(str(row.get(c, "") or nullvalue), w).ljust(w)
            for c, w in zip(columns, widths, strict=True)
        )
        print(line, file=stdout)


def print_csv(
    rows: list[dict[str, object]],
    stdout: TextIO,
    width: int = 0,
    nullvalue: str = "",
) -> None:
    """渲染 CSV 格式。"""
    if not rows:
        return
    columns = list(rows[0].keys())
    print(",".join(columns), file=stdout)
    for row in rows:
        cells: list[str] = []
        for c in columns:
            value = row.get(c, "")
            cell = nullvalue if value is None else str(value)
            if width > 0:
                cell = _truncate(cell, width)
            if "," in cell or '"' in cell or "\n" in cell:
                cell = '"' + cell.replace('"', '""') + '"'
            cells.append(cell)
        print(",".join(cells), file=stdout)


def print_json(rows: list[dict[str, object]], stdout: TextIO) -> None:
    """渲染 JSON lines 格式。"""
    for row in rows:
        print(json.dumps(row, ensure_ascii=False), file=stdout)


def render_plan_node(node: dict[str, object], stdout: TextIO, indent: int = 0) -> None:
    """渲染单个计划节点（缩进 2 空格/层）。"""
    prefix = "  " * indent
    node_type = str(node.get("node", "?"))
    table = node.get("table")
    column = node.get("column")
    rows = node.get("estimated_rows")
    cost = node.get("estimated_cost")
    parts: list[str] = [node_type]
    if table:
        parts.append(f"({table})")
    if column:
        parts.append(f"[{column}]")
    if rows is not None:
        parts.append(f"rows={rows}")
    if cost is not None:
        parts.append(f"cost={cost}")
    print(prefix + " ".join(parts), file=stdout)
    children_raw = node.get("children") or ()
    if isinstance(children_raw, (list, tuple)):
        for child in children_raw:
            if isinstance(child, dict):
                render_plan_node(child, stdout, indent + 1)
