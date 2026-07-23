"""DML 执行：INSERT / UPDATE / DELETE（REQ-QE-003/006）。"""

from __future__ import annotations

from tinydb.catalog_codec import TableMeta
from tinydb.errors import (
    NotNullViolation,
    TypeMismatch,
    UniqueViolation,
    UnsafeDeleteWithoutWhere,
)
from tinydb.heap import Heap
from tinydb.storage import FileStore
from tinydb.types import ColumnType, coerce_in


def exec_insert(
    store: FileStore,
    meta: TableMeta,
    columns: list[str] | None,
    values_list: list[tuple[object, ...]],
    constraints: dict[str, tuple[str, ...]] | None = None,
) -> None:
    """执行 INSERT。"""
    constraints = constraints or {}
    heap = Heap(store=store, root_page_id=meta.root_page_id, schema=list(meta.schema))
    col_names = columns or [name for name, _typ in meta.schema]
    pk_cols = {
        col for col, cons in constraints.items() if "PRIMARY KEY" in cons
    }
    for values in values_list:
        _validate_row(meta, col_names, values, constraints)
        row_dict = dict(zip(col_names, values, strict=False))
        ordered = [_coerce(row_dict.get(name), typ) for name, typ in meta.schema]
        if pk_cols:
            _check_unique(heap, meta, ordered, pk_cols)
        heap.append(tuple(ordered))
    heap.close()


def _check_unique(
    heap: Heap,
    meta: TableMeta,
    ordered: list[object],
    pk_cols: set[str],
) -> None:
    """检查主键唯一性。"""
    col_names = [name for name, _typ in meta.schema]
    pk_indices = [i for i, name in enumerate(col_names) if name in pk_cols]
    pk_values = tuple(ordered[i] for i in pk_indices)
    for _rowid, existing in heap.scan():
        existing_values = tuple(existing[i] for i in pk_indices)
        if existing_values == pk_values:
            raise UniqueViolation(
                column=",".join(sorted(pk_cols)),
                table=meta.name,
                value=pk_values,
            )


def _validate_row(
    meta: TableMeta,
    columns: list[str],
    values: tuple[object, ...],
    constraints: dict[str, tuple[str, ...]],
) -> None:
    """校验类型与约束。"""
    schema_dict = {name: typ for name, typ in meta.schema}
    for col, value in zip(columns, values, strict=False):
        col_type = schema_dict[col]
        col_constraints = constraints.get(col, ())
        if value is None:
            if "NOT NULL" in col_constraints:
                raise NotNullViolation(column=col, table=meta.name)
            continue
        got = _python_type_name(value)
        expected = col_type.value
        if got != expected and not (got == "BOOL" and expected == "INT"):
            raise TypeMismatch(column=col, expected=expected, got=got)


def _coerce(value: object, col_type: ColumnType) -> object:
    """强制类型。"""
    if value is None:
        return None
    return coerce_in(value, col_type)


def _python_type_name(value: object) -> str:
    """Python 值 → 类型名。"""
    if isinstance(value, bool):
        return "BOOL"
    if isinstance(value, int):
        return "INT"
    if isinstance(value, float):
        return "FLOAT"
    if isinstance(value, str):
        return "TEXT"
    return type(value).__name__.upper()


def exec_update(
    store: FileStore,
    meta: TableMeta,
    assignments: list[tuple[str, object]],
    where: object,
) -> int:
    """执行 UPDATE，返回修改行数。"""
    from tinydb.executor.select import _eval_predicate

    heap = Heap(store=store, root_page_id=meta.root_page_id, schema=list(meta.schema))
    rows = heap.scan()
    count = 0
    assign_dict = dict(assignments)
    for rowid, values in rows:
        row_dict = _row_to_dict(meta, values)
        row_dict["rowid"] = rowid
        if where is None or _eval_predicate(where, row_dict):
            new_values = []
            for name, typ in meta.schema:
                if name in assign_dict:
                    new_values.append(_coerce(assign_dict[name], typ))
                else:
                    new_values.append(row_dict.get(name))
            heap.update(rowid, tuple(new_values))
            count += 1
    heap.close()
    return count


def exec_delete(
    store: FileStore,
    meta: TableMeta,
    where: object,
) -> int:
    """执行 DELETE，返回删除行数。"""
    from tinydb.executor.select import _eval_predicate

    if where is None:
        raise UnsafeDeleteWithoutWhere()
    heap = Heap(store=store, root_page_id=meta.root_page_id, schema=list(meta.schema))
    rows = heap.scan()
    count = 0
    for rowid, values in rows:
        row_dict = _row_to_dict(meta, values)
        row_dict["rowid"] = rowid
        if _eval_predicate(where, row_dict):
            heap.delete(rowid)
            count += 1
    heap.close()
    return count


def _row_to_dict(meta: TableMeta, values: tuple[object, ...]) -> dict[str, object]:
    """行值 → 字典。"""
    return {
        name: val for (name, _typ), val in zip(meta.schema, values, strict=False)
    }


__all__: list[str] = ["exec_insert", "exec_update", "exec_delete"]
