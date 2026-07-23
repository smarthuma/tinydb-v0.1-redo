"""Batch 8 — Query Executor (REQ-QE-001..011)。"""

from __future__ import annotations

import pytest

from tinydb.errors import (
    NotNullViolation,
    TableNotFound,
    TypeMismatch,
    UniqueViolation,
    UnsafeDeleteWithoutWhere,
)
from tinydb.executor import Executor
from tinydb.storage import FileStore
from tinydb.types import ColumnType


def _make_executor(tmp_path: object) -> Executor:
    store = FileStore.open(str(tmp_path / "test.db"))
    return Executor(store)


def test_catalog_create_then_get(tmp_path) -> None:
    """CREATE TABLE 后 catalog 可查到。"""
    exe = _make_executor(tmp_path)
    try:
        exe.execute("CREATE TABLE users (id INT, name TEXT);")
        tables = exe.list_tables()
        assert "users" in tables
        meta = exe.get_table("users")
        assert meta.name == "users"
    finally:
        exe.close()


def test_create_table_with_pk_and_not_null(tmp_path) -> None:
    """带约束的 CREATE TABLE。"""
    exe = _make_executor(tmp_path)
    try:
        exe.execute("CREATE TABLE users (id INT PRIMARY KEY, name TEXT NOT NULL);")
        meta = exe.get_table("users")
        assert meta.schema[0] == ("id", ColumnType.INT)
        assert meta.schema[1] == ("name", ColumnType.TEXT)
    finally:
        exe.close()


def test_drop_removes_table(tmp_path) -> None:
    """DROP TABLE 后 catalog 移除。"""
    exe = _make_executor(tmp_path)
    try:
        exe.execute("CREATE TABLE users (id INT);")
        exe.execute("DROP TABLE users;")
        assert "users" not in exe.list_tables()
        with pytest.raises(TableNotFound):
            exe.execute("SELECT * FROM users;")
    finally:
        exe.close()


def test_insert_type_mismatch_rejected(tmp_path) -> None:
    """类型不匹配拒绝插入。"""
    exe = _make_executor(tmp_path)
    try:
        exe.execute("CREATE TABLE users (id INT, name TEXT);")
        with pytest.raises(TypeMismatch):
            exe.execute("INSERT INTO users (id, name) VALUES ('alice', 1);")
    finally:
        exe.close()


def test_insert_not_null_violation(tmp_path) -> None:
    """NOT NULL 违反。"""
    exe = _make_executor(tmp_path)
    try:
        exe.execute("CREATE TABLE users (id INT, name TEXT NOT NULL);")
        with pytest.raises(NotNullViolation):
            exe.execute("INSERT INTO users (id, name) VALUES (1, NULL);")
    finally:
        exe.close()


def test_insert_unique_violation(tmp_path) -> None:
    """主键唯一性违反。"""
    exe = _make_executor(tmp_path)
    try:
        exe.execute("CREATE TABLE users (id INT PRIMARY KEY);")
        exe.execute("INSERT INTO users (id) VALUES (1);")
        with pytest.raises(UniqueViolation):
            exe.execute("INSERT INTO users (id) VALUES (1);")
    finally:
        exe.close()


def test_insert_and_select_roundtrip(tmp_path) -> None:
    """插入后查询返回正确行。"""
    exe = _make_executor(tmp_path)
    try:
        exe.execute("CREATE TABLE users (id INT, name TEXT);")
        exe.execute("INSERT INTO users (id, name) VALUES (1, 'alice');")
        exe.execute("INSERT INTO users (id, name) VALUES (2, 'bob');")
        rows = exe.execute("SELECT * FROM users;")
        assert len(rows) == 2
        assert rows[0]["name"] == "alice"
        assert rows[1]["name"] == "bob"
    finally:
        exe.close()


def test_select_star_expansion(tmp_path) -> None:
    """SELECT * 展开为全列。"""
    exe = _make_executor(tmp_path)
    try:
        exe.execute("CREATE TABLE users (id INT, name TEXT);")
        exe.execute("INSERT INTO users (id, name) VALUES (1, 'alice');")
        rows = exe.execute("SELECT * FROM users;")
        assert set(rows[0].keys()) == {"id", "name"}
    finally:
        exe.close()


def test_where_filter(tmp_path) -> None:
    """WHERE 过滤。"""
    exe = _make_executor(tmp_path)
    try:
        exe.execute("CREATE TABLE users (id INT, name TEXT);")
        exe.execute("INSERT INTO users (id, name) VALUES (1, 'alice');")
        exe.execute("INSERT INTO users (id, name) VALUES (2, 'bob');")
        exe.execute("INSERT INTO users (id, name) VALUES (3, 'alice');")
        rows = exe.execute("SELECT * FROM users WHERE name = 'alice';")
        assert len(rows) == 2
        assert all(r["name"] == "alice" for r in rows)
    finally:
        exe.close()


def test_update_with_where(tmp_path) -> None:
    """UPDATE 带 WHERE。"""
    exe = _make_executor(tmp_path)
    try:
        exe.execute("CREATE TABLE users (id INT, name TEXT);")
        exe.execute("INSERT INTO users (id, name) VALUES (1, 'alice');")
        exe.execute("INSERT INTO users (id, name) VALUES (2, 'bob');")
        exe.execute("UPDATE users SET name = 'X' WHERE name = 'alice';")
        rows = exe.execute("SELECT * FROM users ORDER BY id;")
        assert rows[0]["name"] == "X"
        assert rows[1]["name"] == "bob"
    finally:
        exe.close()


def test_delete_without_where_rejected(tmp_path) -> None:
    """无 WHERE 的 DELETE 被拒绝。"""
    exe = _make_executor(tmp_path)
    try:
        exe.execute("CREATE TABLE users (id INT);")
        exe.execute("INSERT INTO users (id) VALUES (1);")
        with pytest.raises(UnsafeDeleteWithoutWhere):
            exe.execute("DELETE FROM users;")
    finally:
        exe.close()


def test_order_by(tmp_path) -> None:
    """ORDER BY 排序。"""
    exe = _make_executor(tmp_path)
    try:
        exe.execute("CREATE TABLE users (id INT);")
        for i in [3, 1, 2]:
            exe.execute(f"INSERT INTO users (id) VALUES ({i});")
        rows = exe.execute("SELECT * FROM users ORDER BY id DESC;")
        assert [r["id"] for r in rows] == [3, 2, 1]
    finally:
        exe.close()


def test_limit_offset(tmp_path) -> None:
    """LIMIT/OFFSET 分页。"""
    exe = _make_executor(tmp_path)
    try:
        exe.execute("CREATE TABLE users (id INT);")
        for i in range(1, 11):
            exe.execute(f"INSERT INTO users (id) VALUES ({i});")
        rows = exe.execute("SELECT * FROM users ORDER BY id LIMIT 3 OFFSET 2;")
        assert [r["id"] for r in rows] == [3, 4, 5]
    finally:
        exe.close()


def test_count_star(tmp_path) -> None:
    """COUNT(*) 聚合。"""
    exe = _make_executor(tmp_path)
    try:
        exe.execute("CREATE TABLE users (id INT);")
        for i in range(7):
            exe.execute(f"INSERT INTO users (id) VALUES ({i});")
        rows = exe.execute("SELECT COUNT(*) FROM users;")
        assert rows[0]["count"] == 7
    finally:
        exe.close()


def test_group_by_sum(tmp_path) -> None:
    """GROUP BY + SUM。"""
    exe = _make_executor(tmp_path)
    try:
        exe.execute("CREATE TABLE sales (dept TEXT, amount INT);")
        exe.execute("INSERT INTO sales (dept, amount) VALUES ('A', 1);")
        exe.execute("INSERT INTO sales (dept, amount) VALUES ('B', 2);")
        exe.execute("INSERT INTO sales (dept, amount) VALUES ('A', 3);")
        rows = exe.execute("SELECT dept, SUM(amount) FROM sales GROUP BY dept;")
        result = {r["dept"]: r["sum"] for r in rows}
        assert result == {"A": 4, "B": 2}
    finally:
        exe.close()


def test_checkpoint(tmp_path) -> None:
    """CHECKPOINT 清空 WAL。"""
    import os

    exe = _make_executor(tmp_path)
    try:
        exe.execute("CREATE TABLE users (id INT);")
        exe.execute("INSERT INTO users (id) VALUES (1);")
        exe.execute("CHECKPOINT;")
        wal_path = str(tmp_path / "test.db") + "-wal"
        assert os.path.getsize(wal_path) == 0
        rows = exe.execute("SELECT * FROM users;")
        assert len(rows) == 1
    finally:
        exe.close()


def test_executor_has_all() -> None:
    """executor 模块声明 __all__。"""
    from tinydb import executor

    assert "Executor" in executor.__all__
