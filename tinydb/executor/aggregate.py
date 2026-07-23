"""聚合执行：COUNT / SUM / AVG + GROUP BY（REQ-QE-009）。"""

from __future__ import annotations

from tinydb.parser import ast


def exec_aggregate(
    rows: list[dict[str, object]],
    projections: list[object],
    group_by: list[object],
) -> list[dict[str, object]]:
    """执行聚合。"""
    if not group_by:
        return [_aggregate_group(rows, projections)]
    groups: dict[tuple[object, ...], list[dict[str, object]]] = {}
    for row in rows:
        key = tuple(_eval_group_key(expr, row) for expr in group_by)
        groups.setdefault(key, []).append(row)
    result: list[dict[str, object]] = []
    for key in sorted(groups):
        group_rows = groups[key]
        agg = _aggregate_group(group_rows, projections)
        for i, expr in enumerate(group_by):
            if isinstance(expr, ast.Column):
                agg[expr.name] = key[i]
        result.append(agg)
    return result


def _aggregate_group(
    rows: list[dict[str, object]], projections: list[object],
) -> dict[str, object]:
    """对一组行求聚合。"""
    out: dict[str, object] = {}
    for i, proj in enumerate(projections):
        if isinstance(proj, ast.SqlLiteral) and isinstance(proj.value, str):
            if proj.value.startswith("COUNT"):
                out["count"] = len(rows)
            elif proj.value.startswith("SUM"):
                col = proj.value[4:-1]
                out["sum"] = sum(
                    _num(r.get(col)) for r in rows
                )
            elif proj.value.startswith("AVG"):
                col = proj.value[4:-1]
                vals = [_num(r.get(col)) for r in rows]
                out["avg"] = sum(vals) / len(vals) if vals else 0
            else:
                out[f"col_{i}"] = proj.value
        elif isinstance(proj, ast.Column):
            out[proj.name] = rows[0].get(proj.name) if rows else None
        else:
            out[f"col_{i}"] = None
    return out


def _num(value: object) -> float:
    """将值转为数字（NULL 视为 0）。"""
    if value is None:
        return 0
    return float(value)  # type: ignore[arg-type]


def _eval_group_key(expr: object, row: dict[str, object]) -> object:
    """求 GROUP BY 键。"""
    if isinstance(expr, ast.Column):
        return row.get(expr.name)
    return None


__all__: list[str] = ["exec_aggregate"]
