"""JOIN 执行：嵌套循环连接 + 哈希连接（REQ-JQ-008..012）。"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from tinydb.catalog_codec import TableMeta
from tinydb.heap import Heap
from tinydb.parser import ast
from tinydb.storage import FileStore


@runtime_checkable
class _Catalog(Protocol):
    def get_table(self, name: str) -> TableMeta: ...


def exec_nested_loop_join(
    store: FileStore,
    catalog: _Catalog,
    left_rows: list[dict[str, object]],
    join: ast.JoinClause,
) -> list[dict[str, object]]:
    """嵌套循环连接：对每个左行扫描右表找匹配。

    LEFT JOIN 保留所有左行（无匹配时右表列填 NULL）。
    """
    right_table = _resolve_table_name(join)
    right_meta = catalog.get_table(right_table)
    right_rows = _scan_table(store, right_meta)
    is_left = join.kind == ast.JoinType.LEFT

    result: list[dict[str, object]] = []
    for left_row in left_rows:
        matched = False
        for right_row in right_rows:
            merged = _merge_rows(left_row, right_row, join)
            if _match_join_condition(join.on, merged, join):
                result.append(merged)
                matched = True
        if is_left and not matched:
            # 左表行无匹配：右表列填 NULL
            null_right: dict[str, object] = {
                f"{right_table}.{col}": None
                for col, _typ in right_meta.schema
            }
            null_right["rowid"] = None
            merged = {**left_row, **null_right}
            result.append(merged)
    return result


def exec_hash_join(
    store: FileStore,
    catalog: _Catalog,
    left_rows: list[dict[str, object]],
    join: ast.JoinClause,
) -> list[dict[str, object]]:
    """哈希连接（仅 INNER）：对小表构建哈希表，大表探测。

    NOTE: 不支持 LEFT JOIN（会丢弃无匹配的左行）。
    对 LEFT JOIN 请使用 exec_nested_loop_join。
    """
    if join.kind == ast.JoinType.LEFT:
        # LEFT JOIN 回退到 NLJ 以保留无匹配左行
        return exec_nested_loop_join(store, catalog, left_rows, join)

    right_table = _resolve_table_name(join)
    right_meta = catalog.get_table(right_table)
    right_rows = _scan_table(store, right_meta)

    # 构建哈希表（右表）
    hash_table: dict[object, list[dict[str, object]]] = {}
    for row in right_rows:
        key = _extract_join_key(join.on, row, right_table)
        if key is not None:
            hash_table.setdefault(key, []).append(row)

    result: list[dict[str, object]] = []
    for left_row in left_rows:
        key = _extract_join_key(join.on, left_row, None)
        if key is not None and key in hash_table:
            for right_row in hash_table[key]:
                merged = _merge_rows(left_row, right_row, join)
                if _match_join_condition(join.on, merged, join):
                    result.append(merged)
    return result


def resolve_qualified_columns(
    projections: list[object],
    table: str,
    joins: tuple[ast.JoinClause, ...],
    catalog: _Catalog,
) -> tuple[list[object], dict[str, tuple[str, ...]]]:
    """解析限定列，检测歧义。

    返回 (解析后的投影列表, 表名 -> 列名元组映射)。
    歧义列（无限定且存在于多表）抛 AmbiguousColumn。
    """
    from tinydb.errors import AmbiguousColumn

    # 收集所有表的列
    all_columns: dict[str, str] = {}  # col_name -> table_name
    ambiguous: set[str] = set()

    tables = [table] + [_resolve_table_name(j) for j in joins]
    for tbl in tables:
        try:
            meta = catalog.get_table(tbl)
            for col_name, _typ in meta.schema:
                if col_name in all_columns:
                    ambiguous.add(col_name)
                else:
                    all_columns[col_name] = tbl
        except Exception:
            pass

    resolved: list[object] = []
    for proj in projections:
        if isinstance(proj, ast.Column):
            if proj.name in ambiguous:
                raise AmbiguousColumn(column=proj.name)
            resolved.append(proj)
        else:
            resolved.append(proj)

    return resolved, {t: tuple(c for c, tbl in all_columns.items() if tbl == t) for t in tables}


def check_join_type_compatibility(
    join: ast.JoinClause,
    catalog: _Catalog,
) -> None:
    """校验 JOIN 条件两端列类型兼容（REQ-JQ-011）。"""
    from tinydb.errors import TypeMismatch

    if join.on is None:
        return
    from tinydb.parser import ast

    if not isinstance(join.on, ast.BinaryOp):
        return

    left_type = _column_type(join.on.left, catalog)
    right_type = _column_type(join.on.right, catalog)
    if left_type is not None and right_type is not None:
        if not _types_compatible(left_type, right_type):
            raise TypeMismatch(
                column=str(getattr(join.on.left, "name", "?")),
                expected=left_type,
                got=right_type,
            )


# ---------------------------------------------------------------------------
# 内部辅助
# ---------------------------------------------------------------------------


def _resolve_table_name(join: ast.JoinClause) -> str:
    """获取 JOIN 目标表名（优先别名）。"""
    if join.alias:
        return join.alias
    return join.table


def _scan_table(store: FileStore, meta: TableMeta) -> list[dict[str, object]]:
    """扫描全表为行字典列表。"""
    heap = Heap(store=store, root_page_id=meta.root_page_id, schema=list(meta.schema))
    rows = heap.scan()
    heap.close()
    result: list[dict[str, object]] = []
    for rowid, values in rows:
        d = {name: val for (name, _typ), val in zip(meta.schema, values, strict=False)}
        d["rowid"] = rowid
        result.append(d)
    return result


def _merge_rows(
    left: dict[str, object],
    right: dict[str, object],
    join: ast.JoinClause,
) -> dict[str, object]:
    """合并左右行，右表列加表前缀避免冲突。"""
    merged: dict[str, object] = dict(left)
    right_prefix = _resolve_table_name(join)
    for key, value in right.items():
        if key in merged:
            merged[f"{right_prefix}.{key}"] = value
        else:
            merged[key] = value
    return merged


def _match_join_condition(
    on: object,
    row: dict[str, object],
    join: ast.JoinClause,
) -> bool:
    """求值 JOIN ON 条件。"""
    if on is None:
        return True
    from tinydb.executor.select import _eval_predicate

    return _eval_predicate(on, row)


def _extract_join_key(
    on: object,
    row: dict[str, object],
    target_table: str | None,
) -> object:
    """从 JOIN 条件中提取连接键值。"""
    if on is None:
        return None
    from tinydb.parser import ast

    if isinstance(on, ast.BinaryOp) and on.op == "=":
        if target_table is None:
            return _eval_expr(on.left, row)
        return _eval_expr(on.right, row)
    return None


def _eval_expr(node: object, row: dict[str, object]) -> object:
    """求值表达式。"""
    from tinydb.parser import ast

    if isinstance(node, ast.Column):
        return row.get(node.name)
    if isinstance(node, ast.QualifiedColumn):
        if node.table is not None:
            return row.get(f"{node.table}.{node.name}", row.get(node.name))
        return row.get(node.name)
    if isinstance(node, ast.SqlLiteral):
        return node.value
    return None


def _column_type(node: object, catalog: _Catalog) -> str | None:
    """获取列的类型字符串。"""
    from tinydb.parser import ast

    if isinstance(node, ast.Column):
        return _find_column_type(node.name, catalog)
    if isinstance(node, ast.QualifiedColumn) and node.table is not None:
        return _find_column_type(node.name, catalog, node.table)
    return None


def _find_column_type(
    name: str,
    catalog: _Catalog,
    table: str | None = None,
) -> str | None:
    """在 catalog 中查找列类型。"""
    if table is not None:
        try:
            meta = catalog.get_table(table)
            for col_name, col_type in meta.schema:
                if col_name == name:
                    return col_type.value if hasattr(col_type, "value") else str(col_type)
        except Exception:
            pass
    return None


def _types_compatible(left: str, right: str) -> bool:
    """检查两种类型是否可比较。"""
    numeric = {"INT", "FLOAT", "INTEGER", "REAL"}
    if left == right:
        return True
    if left in numeric and right in numeric:
        return True
    return False


__all__ = [
    "exec_nested_loop_join",
    "exec_hash_join",
    "resolve_qualified_columns",
    "check_join_type_compatibility",
]
