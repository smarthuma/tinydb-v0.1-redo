"""Batch 9 — Database 包装层 (REQ-DB-001..006, REWRITE-PENDING 3.8)。"""

from __future__ import annotations

import pytest

from tinydb import Database, TableNotFound


def test_open_and_close(tmp_path) -> None:
    """打开关闭数据库。"""
    db = Database(tmp_path / "test.db")
    try:
        db.execute("CREATE TABLE users (id INT);")
    finally:
        db.close()


def test_close_is_idempotent(tmp_path) -> None:
    """close 幂等。"""
    db = Database(tmp_path / "test.db")
    db.close()
    db.close()  # 不应抛错


def test_select_returns_list_of_dicts(tmp_path) -> None:
    """SELECT 返回字典列表。"""
    db = Database(tmp_path / "test.db")
    try:
        db.execute("CREATE TABLE users (id INT, name TEXT);")
        db.execute("INSERT INTO users (id, name) VALUES (1, 'alice');")
        db.execute("INSERT INTO users (id, name) VALUES (2, 'bob');")
        rows = db.execute("SELECT id, name FROM users ORDER BY id;")
        assert rows == [{"id": 1, "name": "alice"}, {"id": 2, "name": "bob"}]
    finally:
        db.close()


def test_insert_returns_rows_affected(tmp_path) -> None:
    """INSERT 返回 rows_affected。"""
    db = Database(tmp_path / "test.db")
    try:
        db.execute("CREATE TABLE users (id INT);")
        result = db.execute("INSERT INTO users (id) VALUES (1);")
        assert result == [{"rows_affected": 1}]
    finally:
        db.close()


def test_select_empty_returns_empty_list(tmp_path) -> None:
    """空表 SELECT 返回 []。"""
    db = Database(tmp_path / "test.db")
    try:
        db.execute("CREATE TABLE users (id INT);")
        assert db.execute("SELECT * FROM users;") == []
    finally:
        db.close()


def test_error_raised_not_swallowed(tmp_path) -> None:
    """错误应抛出而非吞掉。"""
    db = Database(tmp_path / "test.db")
    try:
        with pytest.raises(TableNotFound):
            db.execute("SELECT * FROM nonexistent;")
        # 数据库仍可用
        db.execute("CREATE TABLE users (id INT);")
    finally:
        db.close()


def test_transaction_auto_commit(tmp_path) -> None:
    """事务成功自动提交。"""
    db = Database(tmp_path / "test.db")
    try:
        db.execute("CREATE TABLE users (id INT);")
        with db.transaction():
            db.execute("INSERT INTO users (id) VALUES (1);")
        rows = db.execute("SELECT * FROM users;")
        assert len(rows) == 1
    finally:
        db.close()


def test_transaction_auto_rollback(tmp_path) -> None:
    """事务异常自动回滚。"""
    db = Database(tmp_path / "test.db")
    try:
        db.execute("CREATE TABLE users (id INT);")
        with pytest.raises(RuntimeError):
            with db.transaction():
                db.execute("INSERT INTO users (id) VALUES (1);")
                raise RuntimeError("boom")
        assert db.execute("SELECT * FROM users;") == []
    finally:
        db.close()


def test_database_context_manager(tmp_path) -> None:
    """with 语句自动关闭。"""
    with Database(tmp_path / "test.db") as db:
        db.execute("CREATE TABLE users (id INT);")
        db.execute("INSERT INTO users (id) VALUES (1);")
    # 重新打开验证持久化
    with Database(tmp_path / "test.db") as db:
        rows = db.execute("SELECT * FROM users;")
        assert len(rows) == 1


def test_top_level_import() -> None:
    """顶层 import 可用。"""
    import tinydb

    assert hasattr(tinydb, "Database")
    assert hasattr(tinydb, "TinyDBError")
    assert hasattr(tinydb, "TableNotFound")


def test_database_has_all() -> None:
    """database 模块声明 __all__。"""
    from tinydb import database

    assert "Database" in database.__all__


def test_execute_after_error(tmp_path) -> None:
    """错误后数据库仍可用。"""
    db = Database(tmp_path / "test.db")
    try:
        db.execute("CREATE TABLE t (id INT);")
        from tinydb.errors import ParseError
        with pytest.raises(ParseError):
            db.execute("BAD SQL;")
        # 仍可用
        db.execute("INSERT INTO t (id) VALUES (1);")
        rows = db.execute("SELECT * FROM t;")
        assert len(rows) == 1
    finally:
        db.close()


def test_ddl_returns_ok(tmp_path) -> None:
    """DDL 返回 status ok。"""
    db = Database(tmp_path / "test.db")
    try:
        result = db.execute("CREATE TABLE t (id INT);")
        assert result == [{"status": "ok"}]
        result = db.execute("DROP TABLE t;")
        assert result == [{"status": "ok"}]
    finally:
        db.close()


def test_update_returns_rows_affected(tmp_path) -> None:
    """UPDATE 返回影响行数。"""
    db = Database(tmp_path / "test.db")
    try:
        db.execute("CREATE TABLE t (id INT, name TEXT);")
        db.execute("INSERT INTO t (id, name) VALUES (1, 'a');")
        db.execute("INSERT INTO t (id, name) VALUES (2, 'a');")
        result = db.execute("UPDATE t SET name = 'X' WHERE name = 'a';")
        assert result == [{"rows_affected": 2}]
    finally:
        db.close()


def test_init_failure_releases_resources(tmp_path) -> None:
    """init 失败释放资源（无效路径）。"""
    with pytest.raises((OSError, RuntimeError)):
        Database("/nonexistent/path/to/db.db")
