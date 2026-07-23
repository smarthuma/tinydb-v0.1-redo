"""SELECT 执行：投影（含 Star 展开）、WHERE、ORDER BY、LIMIT/OFFSET（REQ-QE-004/005/007/008）。"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol, cast, runtime_checkable

from tinydb.catalog_codec import TableMeta
from tinydb.heap import Heap
from tinydb.parser import ast
from tinydb.storage import FileStore


@runtime_checkable
class _Comparable(Protocol):
    def __lt__(self, other: object) -> bool: ...
    def __le__(self, other: object) -> bool: ...
    def __gt__(self, other: object) -> bool: ...
    def __ge__(self, other: object) -> bool: ...


def exec_select(
    store: FileStore,
    meta: TableMeta,
    projections: list[object],
    where: object,
    order_by: Sequence[tuple[object, str]],
    limit: int | None,
    offset: int | None,
    project: bool = True,
) -> list[dict[str, object]]:
    """执行 SELECT。"""
    heap = Heap(store=store, root_page_id=meta.root_page_id, schema=list(meta.schema))
    rows = heap.scan()
    heap.close()

    col_names = [name for name, _typ in meta.schema]

    # WHERE 过滤
    if where is not None:
        rows = [
            (rowid, values)
            for rowid, values in rows
            if _eval_predicate(where, _row_to_dict(meta, values, rowid))
        ]

    # ORDER BY
    if order_by:
        sort_expr, direction = order_by[0]
        reverse = direction == "DESC"
        rows.sort(
            key=lambda r: cast("_Comparable", _eval_expr(
                sort_expr, _row_to_dict(meta, r[1], r[0]),
            )),
            reverse=reverse,
        )

    # LIMIT/OFFSET
    if offset:
        rows = rows[offset:]
    if limit is not None:
        rows = rows[:limit]

    if not project:
        # 返回原始行字典（供聚合使用）
        return [_row_to_dict(meta, values, rowid) for rowid, values in rows]

    # 投影
    has_star = any(isinstance(p, ast.Star) for p in projections)
    result: list[dict[str, object]] = []
    for rowid, values in rows:
        row_dict = _row_to_dict(meta, values, rowid)
        if has_star:
            row_dict.pop("rowid", None)
            result.append(dict(row_dict))
        else:
            result.append(_project_row(projections, row_dict, col_names))
    return result


def _project_row(
    projections: list[object],
    row_dict: dict[str, object],
    col_names: list[str],
) -> dict[str, object]:
    """计算投影。"""
    out: dict[str, object] = {}
    for i, proj in enumerate(projections):
        if isinstance(proj, ast.Column):
            out[proj.name] = row_dict.get(proj.name)
        elif isinstance(proj, ast.SqlLiteral):
            # 聚合占位或常量
            key = _proj_key(i, proj)
            out[key] = row_dict.get(
                proj.value.split("(")[1].rstrip(")") if "(" in proj.value else proj.value
            ) if isinstance(proj.value, str) and proj.value[0].isalpha() else proj.value
        else:
            key = _proj_key(i, proj)
            out[key] = _eval_expr(proj, row_dict)
    return out


def _proj_key(index: int, proj: object) -> str:
    """生成投影列名。"""
    if isinstance(proj, ast.Column):
        return proj.name
    if isinstance(proj, ast.SqlLiteral):
        return str(proj.value).lower().replace("(*)", "").replace("(", "_").replace(")", "")
    return f"col_{index}"


def _row_to_dict(
    meta: TableMeta, values: tuple[object, ...], rowid: int | None = None,
) -> dict[str, object]:
    """行值 → 字典。"""
    d = {name: val for (name, _typ), val in zip(meta.schema, values, strict=False)}
    if rowid is not None:
        d["rowid"] = rowid
    return d


def _eval_predicate(node: object, row: dict[str, object]) -> bool:
    """递归求值谓词。"""
    if node is None:
        return True
    if isinstance(node, ast.LogicalOp):
        left = _eval_predicate(node.left, row)
        if node.op == "AND":
            return left and _eval_predicate(node.right, row)
        return left or _eval_predicate(node.right, row)
    if isinstance(node, ast.BinaryOp):
        return _eval_comparison(node, row)
    if isinstance(node, ast.InPredicate):
        value = _eval_expr(node.expr, row)
        result = value in node.values
        return result if not node.negated else not result
    if isinstance(node, ast.UnaryOp):
        operand = _eval_expr(node.operand, row)
        if node.op == "NOT":
            return not bool(operand)
    return bool(_eval_expr(node, row))


def _eval_comparison(node: ast.BinaryOp, row: dict[str, object]) -> bool:
    """求值比较表达式。"""
    left = _eval_expr(node.left, row)
    if node.op == "IS NULL":
        return left is None
    if node.op == "IS NOT NULL":
        return left is not None
    right = _eval_expr(node.right, row)
    if left is None or right is None:
        return False
    op = node.op
    left_val = cast("_Comparable", left)
    right_val = cast("_Comparable", right)
    if op == "=":
        return left == right
    if op == "<>":
        return left != right
    if op == "<":
        return left_val < right_val
    if op == "<=":
        return left_val <= right_val
    if op == ">":
        return left_val > right_val
    if op == ">=":
        return left_val >= right_val
    return False


def _eval_expr(node: object, row: dict[str, object]) -> object:
    """求值表达式。"""
    if isinstance(node, ast.Column):
        return row.get(node.name)
    if isinstance(node, ast.SqlLiteral):
        return node.value
    if isinstance(node, ast.BinaryOp):
        return _eval_comparison(node, row)
    return None


__all__: list[str] = ["exec_select", "_eval_predicate"]
