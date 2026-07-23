"""Batch 11 — executor 边缘场景补覆盖率。"""

from __future__ import annotations

import pytest

from tinydb.executor import Executor
from tinydb.executor.select import _eval_predicate
from tinydb.parser import parse
from tinydb.storage import FileStore


def _make_executor(tmp_path: object) -> Executor:
    store = FileStore.open(str(tmp_path / "test.db"))
    return Executor(store)


def test_update_multiple_rows(tmp_path) -> None:
    """UPDATE 修改多行。"""
    exe = _make_executor(tmp_path)
    try:
        exe.execute("CREATE TABLE t (name TEXT);")
        exe.execute("INSERT INTO t (name) VALUES ('a');")
        exe.execute("INSERT INTO t (name) VALUES ('b');")
        exe.execute("INSERT INTO t (name) VALUES ('a');")
        count = exe.execute("UPDATE t SET name = 'X' WHERE name = 'a';")
        rows = exe.execute("SELECT * FROM t ORDER BY rowid;")
        assert len(rows) == 3
        assert rows[0]["name"] == "X"
        assert rows[1]["name"] == "b"
        assert rows[2]["name"] == "X"
    finally:
        exe.close()


def test_delete_with_where(tmp_path) -> None:
    """DELETE 带 WHERE。"""
    exe = _make_executor(tmp_path)
    try:
        exe.execute("CREATE TABLE t (id INT);")
        for i in range(1, 6):
            exe.execute(f"INSERT INTO t (id) VALUES ({i});")
        exe.execute("DELETE FROM t WHERE id <= 3;")
        rows = exe.execute("SELECT * FROM t;")
        assert len(rows) == 2
        assert all(r["id"] > 3 for r in rows)
    finally:
        exe.close()


def test_order_by_asc_default(tmp_path) -> None:
    """默认 ASC 排序。"""
    exe = _make_executor(tmp_path)
    try:
        exe.execute("CREATE TABLE t (id INT);")
        for i in [3, 1, 2]:
            exe.execute(f"INSERT INTO t (id) VALUES ({i});")
        rows = exe.execute("SELECT * FROM t ORDER BY id;")
        assert [r["id"] for r in rows] == [1, 2, 3]
    finally:
        exe.close()


def test_limit_zero(tmp_path) -> None:
    """LIMIT 0 返回空。"""
    exe = _make_executor(tmp_path)
    try:
        exe.execute("CREATE TABLE t (id INT);")
        exe.execute("INSERT INTO t (id) VALUES (1);")
        rows = exe.execute("SELECT * FROM t LIMIT 0;")
        assert rows == []
    finally:
        exe.close()


def test_avg_aggregate(tmp_path) -> None:
    """AVG 聚合。"""
    exe = _make_executor(tmp_path)
    try:
        exe.execute("CREATE TABLE t (v INT);")
        exe.execute("INSERT INTO t (v) VALUES (10);")
        exe.execute("INSERT INTO t (v) VALUES (20);")
        rows = exe.execute("SELECT AVG(v) FROM t;")
        assert rows[0]["avg"] == 15.0
    finally:
        exe.close()


def test_predicate_and_or(tmp_path) -> None:
    """AND/OR 复合谓词。"""
    exe = _make_executor(tmp_path)
    try:
        exe.execute("CREATE TABLE t (a INT, b TEXT);")
        exe.execute("INSERT INTO t (a, b) VALUES (1, 'x');")
        exe.execute("INSERT INTO t (a, b) VALUES (2, 'y');")
        exe.execute("INSERT INTO t (a, b) VALUES (3, 'x');")
        rows = exe.execute("SELECT * FROM t WHERE a > 1 AND b = 'x';")
        assert len(rows) == 1
        assert rows[0]["a"] == 3
    finally:
        exe.close()


def test_predicate_between(tmp_path) -> None:
    """BETWEEN 谓词。"""
    exe = _make_executor(tmp_path)
    try:
        exe.execute("CREATE TABLE t (v INT);")
        for i in [1, 5, 10, 15, 20]:
            exe.execute(f"INSERT INTO t (v) VALUES ({i});")
        rows = exe.execute("SELECT * FROM t WHERE v BETWEEN 5 AND 15;")
        assert len(rows) == 3
    finally:
        exe.close()


def test_predicate_in(tmp_path) -> None:
    """IN 谓词。"""
    exe = _make_executor(tmp_path)
    try:
        exe.execute("CREATE TABLE t (v INT);")
        for i in [1, 2, 3, 4, 5]:
            exe.execute(f"INSERT INTO t (v) VALUES ({i});")
        rows = exe.execute("SELECT * FROM t WHERE v IN (2, 4);")
        assert len(rows) == 2
    finally:
        exe.close()


def test_predicate_is_null(tmp_path) -> None:
    """IS NULL 谓词。"""
    exe = _make_executor(tmp_path)
    try:
        exe.execute("CREATE TABLE t (v INT);")
        exe.execute("INSERT INTO t (v) VALUES (1);")
        exe.execute("INSERT INTO t (v) VALUES (NULL);")
        rows = exe.execute("SELECT * FROM t WHERE v IS NULL;")
        assert len(rows) == 1
    finally:
        exe.close()


def test_eval_predicate_direct() -> None:
    """直接测试谓词求值。"""
    from tinydb.executor.select import _eval_predicate

    row = {"a": 5, "b": "hello"}
    stmt = parse("SELECT * FROM t WHERE a = 5 AND b = 'hello';")
    assert _eval_predicate(stmt.where, row) is True
    stmt2 = parse("SELECT * FROM t WHERE a = 99;")
    assert _eval_predicate(stmt2.where, row) is False


def test_group_by_count(tmp_path) -> None:
    """GROUP BY + COUNT。"""
    exe = _make_executor(tmp_path)
    try:
        exe.execute("CREATE TABLE t (cat TEXT);")
        exe.execute("INSERT INTO t (cat) VALUES ('A');")
        exe.execute("INSERT INTO t (cat) VALUES ('A');")
        exe.execute("INSERT INTO t (cat) VALUES ('B');")
        rows = exe.execute("SELECT cat, COUNT(*) FROM t GROUP BY cat;")
        result = {r["cat"]: r["count"] for r in rows}
        assert result == {"A": 2, "B": 1}
    finally:
        exe.close()


def test_select_specific_columns(tmp_path) -> None:
    """选择特定列。"""
    exe = _make_executor(tmp_path)
    try:
        exe.execute("CREATE TABLE t (a INT, b TEXT, c FLOAT);")
        exe.execute("INSERT INTO t (a, b, c) VALUES (1, 'x', 1.5);")
        rows = exe.execute("SELECT a, c FROM t;")
        assert set(rows[0].keys()) == {"a", "c"}
        assert rows[0]["c"] == 1.5
    finally:
        exe.close()


def test_float_and_bool_columns(tmp_path) -> None:
    """FLOAT 和 BOOL 列。"""
    exe = _make_executor(tmp_path)
    try:
        exe.execute("CREATE TABLE t (f FLOAT, b BOOL);")
        exe.execute("INSERT INTO t (f, b) VALUES (3.14, TRUE);")
        rows = exe.execute("SELECT * FROM t;")
        assert rows[0]["f"] == 3.14
        assert rows[0]["b"] is True
    finally:
        exe.close()


def test_offset_beyond_range(tmp_path) -> None:
    """OFFSET 超出范围返回空。"""
    exe = _make_executor(tmp_path)
    try:
        exe.execute("CREATE TABLE t (id INT);")
        exe.execute("INSERT INTO t (id) VALUES (1);")
        rows = exe.execute("SELECT * FROM t OFFSET 100;")
        assert rows == []
    finally:
        exe.close()


def test_select_with_no_where(tmp_path) -> None:
    """无 WHERE 的 SELECT。"""
    exe = _make_executor(tmp_path)
    try:
        exe.execute("CREATE TABLE t (id INT);")
        exe.execute("INSERT INTO t (id) VALUES (1);")
        rows = exe.execute("SELECT id FROM t;")
        assert rows == [{"id": 1}]
    finally:
        exe.close()


def test_where_with_false_predicate(tmp_path) -> None:
    """WHERE 条件不匹配返回空。"""
    exe = _make_executor(tmp_path)
    try:
        exe.execute("CREATE TABLE t (id INT);")
        exe.execute("INSERT INTO t (id) VALUES (1);")
        rows = exe.execute("SELECT * FROM t WHERE id = 999;")
        assert rows == []
    finally:
        exe.close()


def test_multiple_predicate_or(tmp_path) -> None:
    """OR 谓词匹配多行。"""
    exe = _make_executor(tmp_path)
    try:
        exe.execute("CREATE TABLE t (id INT);")
        for i in [1, 2, 3, 4, 5]:
            exe.execute(f"INSERT INTO t (id) VALUES ({i});")
        rows = exe.execute("SELECT * FROM t WHERE id = 1 OR id = 5;")
        assert len(rows) == 2
    finally:
        exe.close()


def test_limit_with_order_by(tmp_path) -> None:
    """LIMIT + ORDER BY 组合。"""
    exe = _make_executor(tmp_path)
    try:
        exe.execute("CREATE TABLE t (v TEXT);")
        for c in ["c", "a", "b"]:
            exe.execute(f"INSERT INTO t (v) VALUES ('{c}');")
        rows = db.execute("SELECT * FROM t ORDER BY v LIMIT 2;") if False else exe.execute("SELECT * FROM t ORDER BY v LIMIT 2;")
        assert [r["v"] for r in rows] == ["a", "b"]
    finally:
        exe.close()


def test_group_by_multiple_columns(tmp_path) -> None:
    """多列 GROUP BY。"""
    exe = _make_executor(tmp_path)
    try:
        exe.execute("CREATE TABLE t (a TEXT, b TEXT);")
        exe.execute("INSERT INTO t (a, b) VALUES ('X', '1');")
        exe.execute("INSERT INTO t (a, b) VALUES ('X', '2');")
        exe.execute("INSERT INTO t (a, b) VALUES ('Y', '1');")
        rows = exe.execute("SELECT a, COUNT(*) FROM t GROUP BY a;")
        result = {r["a"]: r["count"] for r in rows}
        assert result == {"X": 2, "Y": 1}
    finally:
        exe.close()


def test_checkpoint_after_insert(tmp_path) -> None:
    """CHECKPOINT 后数据持久。"""
    import os
    exe = _make_executor(tmp_path)
    try:
        exe.execute("CREATE TABLE t (id INT);")
        exe.execute("INSERT INTO t (id) VALUES (42);")
        exe.execute("CHECKPOINT;")
        wal_path = str(tmp_path / "test.db") + "-wal"
        assert os.path.getsize(wal_path) == 0
    finally:
        exe.close()


def test_select_star_with_where(tmp_path) -> None:
    """SELECT * + WHERE。"""
    exe = _make_executor(tmp_path)
    try:
        exe.execute("CREATE TABLE t (a INT, b TEXT);")
        exe.execute("INSERT INTO t (a, b) VALUES (1, 'x');")
        exe.execute("INSERT INTO t (a, b) VALUES (2, 'y');")
        rows = exe.execute("SELECT * FROM t WHERE a = 2;")
        assert len(rows) == 1
        assert rows[0]["b"] == "y"
    finally:
        exe.close()


def test_select_with_group_by_and_agg(tmp_path) -> None:
    """SELECT GROUP BY + 聚合走聚合路径。"""
    exe = _make_executor(tmp_path)
    try:
        exe.execute("CREATE TABLE t (cat TEXT, val INT);")
        exe.execute("INSERT INTO t (cat, val) VALUES ('A', 10);")
        exe.execute("INSERT INTO t (cat, val) VALUES ('A', 20);")
        exe.execute("INSERT INTO t (cat, val) VALUES ('B', 5);")
        rows = exe.execute("SELECT cat, SUM(val), COUNT(*) FROM t GROUP BY cat;")
        result = {r["cat"]: (r["sum"], r["count"]) for r in rows}
        assert result["A"] == (30, 2)
        assert result["B"] == (5, 1)
    finally:
        exe.close()


def test_database_context_manager(tmp_path) -> None:
    """Database with 语句。"""
    from tinydb.database import Database
    with Database(tmp_path / "test.db") as db:
        db.execute("CREATE TABLE t (id INT);")
        db.execute("INSERT INTO t (id) VALUES (1);")
    # 验证持久化
    with Database(tmp_path / "test.db") as db:
        rows = db.execute("SELECT * FROM t;")
        assert len(rows) == 1


def test_transaction_rollback(tmp_path) -> None:
    """事务回滚。"""
    from tinydb.database import Database
    db = Database(tmp_path / "test.db")
    try:
        db.execute("CREATE TABLE t (id INT);")
        with pytest.raises(ValueError):
            with db.transaction():
                db.execute("INSERT INTO t (id) VALUES (1);")
                raise ValueError("boom")
        assert db.execute("SELECT * FROM t;") == []
    finally:
        db.close()


def test_transaction_commit_persistent(tmp_path) -> None:
    """事务提交后持久化。"""
    from tinydb.database import Database
    db = Database(tmp_path / "test.db")
    try:
        db.execute("CREATE TABLE t (id INT);")
        with db.transaction():
            db.execute("INSERT INTO t (id) VALUES (99);")
    finally:
        db.close()
    # 重新打开
    db2 = Database(tmp_path / "test.db")
    try:
        rows = db2.execute("SELECT * FROM t;")
        assert len(rows) == 1
        assert rows[0]["id"] == 99
    finally:
        db2.close()


def test_predicate_not_equal(tmp_path) -> None:
    """<> 操作符。"""
    exe = _make_executor(tmp_path)
    try:
        exe.execute("CREATE TABLE t (v INT);")
        exe.execute("INSERT INTO t (v) VALUES (1);")
        exe.execute("INSERT INTO t (v) VALUES (2);")
        rows = exe.execute("SELECT * FROM t WHERE v <> 1;")
        assert len(rows) == 1
        assert rows[0]["v"] == 2
    finally:
        exe.close()


def test_predicate_or_combination(tmp_path) -> None:
    """OR 组合。"""
    exe = _make_executor(tmp_path)
    try:
        exe.execute("CREATE TABLE t (a INT, b INT);")
        exe.execute("INSERT INTO t (a, b) VALUES (1, 10);")
        exe.execute("INSERT INTO t (a, b) VALUES (2, 20);")
        exe.execute("INSERT INTO t (a, b) VALUES (3, 30);")
        rows = exe.execute("SELECT * FROM t WHERE a = 1 OR b = 30;")
        assert len(rows) == 2
    finally:
        exe.close()


def test_select_count_star_with_group(tmp_path) -> None:
    """COUNT(*) + GROUP BY。"""
    exe = _make_executor(tmp_path)
    try:
        exe.execute("CREATE TABLE t (cat TEXT);")
        exe.execute("INSERT INTO t (cat) VALUES ('X');")
        exe.execute("INSERT INTO t (cat) VALUES ('X');")
        exe.execute("INSERT INTO t (cat) VALUES ('Y');")
        rows = exe.execute("SELECT cat, COUNT(*) FROM t GROUP BY cat;")
        result = {r["cat"]: r["count"] for r in rows}
        assert result == {"X": 2, "Y": 1}
    finally:
        exe.close()


def test_drop_table_if_not_exists(tmp_path) -> None:
    """DROP 不存在的表。"""
    exe = _make_executor(tmp_path)
    try:
        with pytest.raises(Exception):
            exe.execute("DROP TABLE nonexistent;")
    finally:
        exe.close()


def test_insert_multiple_rows(tmp_path) -> None:
    """单条 INSERT 多值。"""
    exe = _make_executor(tmp_path)
    try:
        exe.execute("CREATE TABLE t (id INT);")
        exe.execute("INSERT INTO t (id) VALUES (1), (2), (3);")
        rows = exe.execute("SELECT * FROM t;")
        assert len(rows) == 3
    finally:
        exe.close()


def test_tx_checkpoint(tmp_path) -> None:
    """TxManager checkpoint。"""
    from tinydb.tx import TxManager
    from tinydb.wal import Wal

    store = FileStore.open(str(tmp_path / "test.db"))
    wal = Wal.open(str(tmp_path / "test.db") + "-wal")
    tx = TxManager(store, wal)
    tx.begin()
    tx.commit(1)
    tx.checkpoint()
    wal.close()
    store.close()


def test_tx_nested_begin_raises(tmp_path) -> None:
    """嵌套 BEGIN 抛异常。"""
    from tinydb.errors import TransactionAlreadyActive
    from tinydb.tx import TxManager
    from tinydb.wal import Wal

    store = FileStore.open(str(tmp_path / "test.db"))
    wal = Wal.open(str(tmp_path / "test.db") + "-wal")
    tx = TxManager(store, wal)
    tx.begin()
    with pytest.raises(TransactionAlreadyActive):
        tx.begin()
    wal.close()
    store.close()


def test_wal_truncate(tmp_path) -> None:
    """WAL truncate。"""
    from tinydb.wal import Wal, TX_COMMIT

    wal_path = str(tmp_path / "test.db-wal")
    wal = Wal.open(wal_path)
    wal.append(TX_COMMIT)
    wal.fsync()
    assert wal._fd >= 0  # fd exists
    wal.truncate()
    wal.close()
    import os
    assert os.path.getsize(wal_path) == 0


def test_update_with_no_match(tmp_path) -> None:
    """UPDATE 无匹配行。"""
    exe = _make_executor(tmp_path)
    try:
        exe.execute("CREATE TABLE t (id INT, name TEXT);")
        exe.execute("INSERT INTO t (id, name) VALUES (1, 'a');")
        count = exe.execute("UPDATE t SET name = 'X' WHERE id = 999;")
        assert count == 0
    finally:
        exe.close()


def test_delete_with_no_match(tmp_path) -> None:
    """DELETE 无匹配行。"""
    exe = _make_executor(tmp_path)
    try:
        exe.execute("CREATE TABLE t (id INT);")
        exe.execute("INSERT INTO t (id) VALUES (1);")
        count = exe.execute("DELETE FROM t WHERE id = 999;")
        assert count == 0
    finally:
        exe.close()


def test_select_order_by_desc(tmp_path) -> None:
    """ORDER BY DESC。"""
    exe = _make_executor(tmp_path)
    try:
        exe.execute("CREATE TABLE t (v INT);")
        for i in [1, 3, 2]:
            exe.execute(f"INSERT INTO t (v) VALUES ({i});")
        rows = exe.execute("SELECT * FROM t ORDER BY v DESC;")
        assert [r["v"] for r in rows] == [3, 2, 1]
    finally:
        exe.close()


def test_database_execute_after_error(tmp_path) -> None:
    """错误后数据库仍可用。"""
    from tinydb.database import Database
    db = Database(tmp_path / "test.db")
    try:
        db.execute("CREATE TABLE t (id INT);")
        with pytest.raises(Exception):
            db.execute("BAD SQL;")
        db.execute("INSERT INTO t (id) VALUES (1);")
        rows = db.execute("SELECT * FROM t;")
        assert len(rows) == 1
    finally:
        db.close()


def test_select_order_by_first_column(tmp_path) -> None:
    """ORDER BY 首列排序。"""
    exe = _make_executor(tmp_path)
    try:
        exe.execute("CREATE TABLE t (a INT, b INT);")
        exe.execute("INSERT INTO t (a, b) VALUES (2, 1);")
        exe.execute("INSERT INTO t (a, b) VALUES (1, 2);")
        exe.execute("INSERT INTO t (a, b) VALUES (3, 0);")
        rows = exe.execute("SELECT * FROM t ORDER BY a;")
        assert [r["a"] for r in rows] == [1, 2, 3]
    finally:
        exe.close()


def test_limit_only(tmp_path) -> None:
    """仅 LIMIT。"""
    exe = _make_executor(tmp_path)
    try:
        exe.execute("CREATE TABLE t (id INT);")
        for i in range(1, 6):
            exe.execute(f"INSERT INTO t (id) VALUES ({i});")
        rows = exe.execute("SELECT * FROM t LIMIT 2;")
        assert len(rows) == 2
    finally:
        exe.close()


def test_offset_only(tmp_path) -> None:
    """仅 OFFSET。"""
    exe = _make_executor(tmp_path)
    try:
        exe.execute("CREATE TABLE t (id INT);")
        for i in range(1, 6):
            exe.execute(f"INSERT INTO t (id) VALUES ({i});")
        rows = exe.execute("SELECT * FROM t OFFSET 3;")
        assert len(rows) == 2
    finally:
        exe.close()


def test_predicate_in_with_strings(tmp_path) -> None:
    """IN 字符串列表。"""
    exe = _make_executor(tmp_path)
    try:
        exe.execute("CREATE TABLE t (name TEXT);")
        exe.execute("INSERT INTO t (name) VALUES ('alice');")
        exe.execute("INSERT INTO t (name) VALUES ('bob');")
        exe.execute("INSERT INTO t (name) VALUES ('charlie');")
        rows = exe.execute("SELECT * FROM t WHERE name IN ('alice', 'charlie');")
        assert len(rows) == 2
    finally:
        exe.close()


def test_select_specific_cols_with_star(tmp_path) -> None:
    """SELECT * 展开所有列。"""
    exe = _make_executor(tmp_path)
    try:
        exe.execute("CREATE TABLE t (a INT, b TEXT, c FLOAT);")
        exe.execute("INSERT INTO t (a, b, c) VALUES (1, 'x', 1.5);")
        rows = exe.execute("SELECT * FROM t;")
        assert set(rows[0].keys()) == {"a", "b", "c"}
    finally:
        exe.close()


def test_database_get_table(tmp_path) -> None:
    """get_table 返回元数据。"""
    exe = _make_executor(tmp_path)
    try:
        exe.execute("CREATE TABLE users (id INT, name TEXT);")
        meta = exe.get_table("users")
        assert meta.name == "users"
        assert len(meta.schema) == 2
    finally:
        exe.close()


def test_drop_table_then_recreate(tmp_path) -> None:
    """删除后重建表。"""
    exe = _make_executor(tmp_path)
    try:
        exe.execute("CREATE TABLE t (id INT);")
        exe.execute("INSERT INTO t (id) VALUES (1);")
        exe.execute("DROP TABLE t;")
        exe.execute("CREATE TABLE t (name TEXT);")
        exe.execute("INSERT INTO t (name) VALUES ('x');")
        rows = exe.execute("SELECT * FROM t;")
        assert len(rows) == 1
        assert rows[0]["name"] == "x"
    finally:
        exe.close()


def test_btree_medium_dataset(tmp_path) -> None:
    """B+ Tree 中等数据集。"""
    exe = _make_executor(tmp_path)
    try:
        exe.execute("CREATE TABLE t (id INT);")
        for i in range(50):
            exe.execute(f"INSERT INTO t (id) VALUES ({i});")
        rows = exe.execute("SELECT * FROM t;")
        assert len(rows) == 50
    finally:
        exe.close()


def test_select_with_where_and_limit(tmp_path) -> None:
    """WHERE + LIMIT。"""
    exe = _make_executor(tmp_path)
    try:
        exe.execute("CREATE TABLE t (id INT);")
        for i in range(100):
            exe.execute(f"INSERT INTO t (id) VALUES ({i});")
        rows = exe.execute("SELECT * FROM t WHERE id > 50 LIMIT 3;")
        assert len(rows) == 3
        assert all(r["id"] > 50 for r in rows)
    finally:
        exe.close()


def test_delete_all_rows(tmp_path) -> None:
    """删除所有行。"""
    exe = _make_executor(tmp_path)
    try:
        exe.execute("CREATE TABLE t (id INT);")
        exe.execute("INSERT INTO t (id) VALUES (1);")
        exe.execute("INSERT INTO t (id) VALUES (2);")
        exe.execute("DELETE FROM t WHERE id > 0;")
        rows = exe.execute("SELECT * FROM t;")
        assert len(rows) == 0
    finally:
        exe.close()


def test_update_to_null(tmp_path) -> None:
    """UPDATE 设为 NULL。"""
    exe = _make_executor(tmp_path)
    try:
        exe.execute("CREATE TABLE t (id INT, name TEXT);")
        exe.execute("INSERT INTO t (id, name) VALUES (1, 'alice');")
        exe.execute("UPDATE t SET name = NULL WHERE id = 1;")
        rows = exe.execute("SELECT * FROM t;")
        assert rows[0]["name"] is None
    finally:
        exe.close()


def test_select_multiple_tables(tmp_path) -> None:
    """多表操作。"""
    exe = _make_executor(tmp_path)
    try:
        exe.execute("CREATE TABLE a (id INT);")
        exe.execute("CREATE TABLE b (id INT);")
        exe.execute("INSERT INTO a (id) VALUES (1);")
        exe.execute("INSERT INTO b (id) VALUES (2);")
        rows_a = exe.execute("SELECT * FROM a;")
        rows_b = exe.execute("SELECT * FROM b;")
        assert rows_a[0]["id"] == 1
        assert rows_b[0]["id"] == 2
    finally:
        exe.close()


def test_insert_text_with_special_chars(tmp_path) -> None:
    """插入特殊字符文本。"""
    exe = _make_executor(tmp_path)
    try:
        exe.execute("CREATE TABLE t (name TEXT);")
        exe.execute("INSERT INTO t (name) VALUES ('hello world');")
        rows = exe.execute("SELECT * FROM t;")
        assert rows[0]["name"] == "hello world"
    finally:
        exe.close()


def test_where_with_multiple_and(tmp_path) -> None:
    """多个 AND 条件。"""
    exe = _make_executor(tmp_path)
    try:
        exe.execute("CREATE TABLE t (a INT, b INT, c INT);")
        exe.execute("INSERT INTO t (a, b, c) VALUES (1, 2, 3);")
        exe.execute("INSERT INTO t (a, b, c) VALUES (1, 2, 4);")
        exe.execute("INSERT INTO t (a, b, c) VALUES (1, 3, 3);")
        rows = exe.execute("SELECT * FROM t WHERE a = 1 AND b = 2 AND c = 3;")
        assert len(rows) == 1
    finally:
        exe.close()


def test_storage_buffer_pool(tmp_path) -> None:
    """缓冲池基本功能。"""
    from tinydb.storage import BufferPool, PageType, alloc_page

    store = FileStore.open(str(tmp_path / "test.db"))
    pool = BufferPool(store, capacity=4)
    p1 = alloc_page(store, PageType.TABLE)
    handle = pool.get(p1)
    handle.pin()
    handle.unpin()
    store.close()


def test_wal_fsync(tmp_path) -> None:
    """WAL fsync。"""
    from tinydb.wal import Wal, TX_COMMIT

    wal_path = str(tmp_path / "test.db-wal")
    wal = Wal.open(wal_path)
    wal.append(TX_COMMIT)
    wal.fsync()
    wal.close()


def test_drop_table_multiple(tmp_path) -> None:
    """多表 DROP。"""
    exe = _make_executor(tmp_path)
    try:
        exe.execute("CREATE TABLE a (id INT);")
        exe.execute("CREATE TABLE b (id INT);")
        exe.execute("DROP TABLE a;")
        tables = exe.list_tables()
        assert "a" not in tables
        assert "b" in tables
    finally:
        exe.close()


def test_insert_large_int(tmp_path) -> None:
    """插入大整数。"""
    exe = _make_executor(tmp_path)
    try:
        exe.execute("CREATE TABLE t (v INT);")
        exe.execute("INSERT INTO t (v) VALUES (1000000);")
        rows = exe.execute("SELECT * FROM t;")
        assert rows[0]["v"] == 1000000
    finally:
        exe.close()


def test_select_empty_table(tmp_path) -> None:
    """空表 SELECT。"""
    exe = _make_executor(tmp_path)
    try:
        exe.execute("CREATE TABLE t (id INT);")
        rows = exe.execute("SELECT * FROM t;")
        assert rows == []
    finally:
        exe.close()


def test_transaction_isolation(tmp_path) -> None:
    """事务提交后数据可见。"""
    from tinydb.database import Database
    db = Database(tmp_path / "test.db")
    try:
        db.execute("CREATE TABLE t (id INT);")
        with db.transaction():
            db.execute("INSERT INTO t (id) VALUES (1);")
            db.execute("INSERT INTO t (id) VALUES (2);")
        rows = db.execute("SELECT * FROM t;")
        assert len(rows) == 2
    finally:
        db.close()


def test_types_encode_decode() -> None:
    """类型编解码边缘。"""
    from tinydb.types import (
        ColumnType, decode_int, encode_int, encode_float, decode_float,
        encode_text, decode_text, encode_bool, decode_bool,
    )
    # float round-trip
    assert decode_float(encode_float(2.71828)) == 2.71828
    # text with emoji
    assert decode_text(encode_text("🚀")) == "🚀"
    # bool
    assert decode_bool(encode_bool(False)) is False
    # int boundary
    assert decode_int(encode_int(2**63 - 1)) == 2**63 - 1


def test_select_star_expansion_three_cols(tmp_path) -> None:
    """SELECT * 展开三列。"""
    exe = _make_executor(tmp_path)
    try:
        exe.execute("CREATE TABLE t (a INT, b TEXT, c FLOAT);")
        exe.execute("INSERT INTO t (a, b, c) VALUES (1, 'x', 1.5);")
        exe.execute("INSERT INTO t (a, b, c) VALUES (2, 'y', 2.5);")
        rows = exe.execute("SELECT * FROM t ORDER BY a;")
        assert rows[0]["c"] == 1.5
        assert rows[1]["b"] == "y"
    finally:
        exe.close()


def test_where_or_with_and(tmp_path) -> None:
    """OR + AND 混合。"""
    exe = _make_executor(tmp_path)
    try:
        exe.execute("CREATE TABLE t (a INT, b INT);")
        exe.execute("INSERT INTO t (a, b) VALUES (1, 10);")
        exe.execute("INSERT INTO t (a, b) VALUES (2, 20);")
        exe.execute("INSERT INTO t (a, b) VALUES (3, 10);")
        rows = exe.execute("SELECT * FROM t WHERE a = 1 OR (a = 3 AND b = 10);")
        assert len(rows) == 2
    finally:
        exe.close()


def test_limit_1(tmp_path) -> None:
    """LIMIT 1。"""
    exe = _make_executor(tmp_path)
    try:
        exe.execute("CREATE TABLE t (id INT);")
        exe.execute("INSERT INTO t (id) VALUES (1);")
        exe.execute("INSERT INTO t (id) VALUES (2);")
        rows = exe.execute("SELECT * FROM t LIMIT 1;")
        assert len(rows) == 1
    finally:
        exe.close()


def test_database_list_tables(tmp_path) -> None:
    """list_tables。"""
    from tinydb.database import Database
    db = Database(tmp_path / "test.db")
    try:
        assert db._executor.list_tables() == []
        db.execute("CREATE TABLE a (id INT);")
        db.execute("CREATE TABLE b (id INT);")
        tables = db._executor.list_tables()
        assert set(tables) == {"a", "b"}
    finally:
        db.close()
