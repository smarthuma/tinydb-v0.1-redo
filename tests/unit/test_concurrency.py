"""并发控制测试（REQ-CC-001..009）。"""

from __future__ import annotations

import sys
import threading
import time

import pytest

from tinydb import Database
from tinydb.errors import DatabaseBusy
from tinydb.lock import FileLock, RWLock

# ---------------------------------------------------------------------------
# RWLock 测试
# ---------------------------------------------------------------------------


class TestRWLock:
    """连接级读写锁（REQ-CC-001,002）。"""

    def test_concurrent_reads_do_not_block(self) -> None:
        """多个读者并发获取读锁不互相阻塞。"""
        lock = RWLock()
        results: list[int] = []
        barrier = threading.Barrier(3)

        def reader(idx: int) -> None:
            with lock.read(timeout=2.0):
                barrier.wait(timeout=2.0)
                time.sleep(0.05)
                results.append(idx)

        threads = [threading.Thread(target=reader, args=(i,)) for i in range(3)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=5.0)

        assert sorted(results) == [0, 1, 2]

    def test_write_blocks_other_writers(self) -> None:
        """写锁互斥：两个写操作串行执行。"""
        lock = RWLock()
        order: list[str] = []

        def writer(name: str) -> None:
            with lock.write(timeout=2.0):
                order.append(f"{name}_start")
                time.sleep(0.05)
                order.append(f"{name}_end")

        t1 = threading.Thread(target=writer, args=("a",))
        t2 = threading.Thread(target=writer, args=("b",))
        t1.start()
        time.sleep(0.01)  # 确保 t1 先获取写锁
        t2.start()
        t1.join(timeout=5.0)
        t2.join(timeout=5.0)

        # 两个写操作不交错
        assert order in (
            ["a_start", "a_end", "b_start", "b_end"],
            ["b_start", "b_end", "a_start", "a_end"],
        )

    def test_write_blocks_read(self) -> None:
        """写锁阻塞读锁。"""
        lock = RWLock()
        events: list[str] = []

        def holder() -> None:
            with lock.write(timeout=2.0):
                events.append("write_acquired")
                time.sleep(0.1)

        def waiter() -> None:
            time.sleep(0.02)  # 确保持有者先获取写锁
            with lock.read(timeout=2.0):
                events.append("read_acquired")

        t_holder = threading.Thread(target=holder)
        t_waiter = threading.Thread(target=waiter)
        t_holder.start()
        t_waiter.start()
        t_holder.join(timeout=5.0)
        t_waiter.join(timeout=5.0)

        assert events == ["write_acquired", "read_acquired"]

    def test_read_blocks_write(self) -> None:
        """读锁阻塞写锁。"""
        lock = RWLock()
        events: list[str] = []

        def holder() -> None:
            with lock.read(timeout=2.0):
                events.append("read_acquired")
                time.sleep(0.1)

        def waiter() -> None:
            time.sleep(0.02)
            with lock.write(timeout=2.0):
                events.append("write_acquired")

        t_holder = threading.Thread(target=holder)
        t_waiter = threading.Thread(target=waiter)
        t_holder.start()
        t_waiter.start()
        t_holder.join(timeout=5.0)
        t_waiter.join(timeout=5.0)

        assert events == ["read_acquired", "write_acquired"]

    def test_timeout_raises_database_busy(self) -> None:
        """锁超时抛 DatabaseBusy（REQ-CC-004）。"""
        lock = RWLock()

        def holder() -> None:
            with lock.write(timeout=2.0):
                time.sleep(0.5)

        t = threading.Thread(target=holder)
        t.start()
        time.sleep(0.05)

        with pytest.raises(DatabaseBusy):
            lock.acquire_read(timeout=0.1)

        t.join(timeout=5.0)


# ---------------------------------------------------------------------------
# FileLock 测试（仅 Unix）
# ---------------------------------------------------------------------------


@pytest.mark.skipif(sys.platform == "win32", reason="fcntl.flock Unix-only")
class TestFileLock:
    """多进程文件锁（REQ-CC-003）。"""

    def test_exclusive_lock_blocks_second(self, tmp_path) -> None:
        """排他锁阻止第二个进程获取锁。"""
        path = str(tmp_path / "test.db")
        # 创建文件
        open(path, "a+b").close()
        lock1 = FileLock(path)
        lock1.exclusive(timeout=1.0)

        lock2 = FileLock(path)
        with pytest.raises(DatabaseBusy):
            lock2.exclusive(timeout=0.1)

        lock1.release()

    def test_release_allows_next(self, tmp_path) -> None:
        """释放后下一个进程可获取锁。"""
        path = str(tmp_path / "test.db")
        open(path, "a+b").close()
        lock1 = FileLock(path)
        lock1.exclusive(timeout=1.0)
        lock1.release()

        lock2 = FileLock(path)
        lock2.exclusive(timeout=1.0)  # 不抛
        lock2.release()

    def test_shared_locks_coexist(self, tmp_path) -> None:
        """两个共享锁可共存。"""
        path = str(tmp_path / "test.db")
        open(path, "a+b").close()
        lock1 = FileLock(path)
        lock1.shared(timeout=1.0)

        lock2 = FileLock(path)
        lock2.shared(timeout=1.0)  # 不抛

        lock1.release()
        lock2.release()


# ---------------------------------------------------------------------------
# Database 集成测试
# ---------------------------------------------------------------------------


class TestDatabaseLockLifecycle:
    """Database 锁生命周期（REQ-CC-004,005）。"""

    def test_close_releases_file_lock(self, tmp_path) -> None:
        """close 释放文件锁，第二个 Database 可打开（REQ-CC-005）。"""
        path = tmp_path / "test.db"
        db1 = Database(str(path))
        db1.execute("CREATE TABLE t (id INT)")
        db1.close()

        # 第二个可打开（不阻塞）
        db2 = Database(str(path))
        db2.execute("INSERT INTO t VALUES (1)")
        db2.close()

    def test_lock_timeout_parameter(self, tmp_path) -> None:
        """lock_timeout 参数可配置（REQ-CC-004）。"""
        path = tmp_path / "test.db"
        db = Database(str(path), lock_timeout=1.5)
        assert db._lock_timeout == 1.5
        db.close()

    def test_readonly_parameter(self, tmp_path) -> None:
        """readonly 参数可配置。"""
        path = tmp_path / "test.db"
        db = Database(str(path), readonly=True)
        assert db._readonly is True
        db.close()

    def test_backward_compat_constructor(self, tmp_path) -> None:
        """Database(path) 向后兼容（REQ-CC-007）。"""
        path = tmp_path / "test.db"
        db = Database(str(path))
        db.execute("CREATE TABLE t (id INT)")
        db.execute("INSERT INTO t VALUES (42)")
        rows = db.execute("SELECT * FROM t")
        assert rows == [{"id": 42}]
        db.close()


# ---------------------------------------------------------------------------
# 多事务 TxManager 测试
# ---------------------------------------------------------------------------


class TestMultiTransaction:
    """多事务 ID 支持（REQ-CC-006）。"""

    def test_two_connections_independent_tx(self, tmp_path) -> None:
        """两个连接的事务互不干扰（REQ-CC-006）。

        每个连接有独立的 TxManager，tx_id 空间独立。
        验证：两个连接可同时 BEGIN，各自 COMMIT 互不干扰。
        """
        path = tmp_path / "test.db"
        db1 = Database(str(path))
        db1.execute("CREATE TABLE t (id INT)")

        db2 = Database(str(path))

        tx1 = db1._executor._tx.begin()
        tx2 = db2._executor._tx.begin()
        # 两个事务同时活跃
        assert db1._executor._tx._txs[tx1].active
        assert db2._executor._tx._txs[tx2].active

        db1._executor._tx.commit(tx1)
        # db2 的事务不受 db1 commit 影响
        assert db2._executor._tx._txs[tx2].active
        db2._executor._tx.commit(tx2)

        db1.close()
        db2.close()

    def test_nested_begin_same_connection_raises(self, tmp_path) -> None:
        """同连接嵌套 BEGIN 抛 TransactionAlreadyActive。"""
        path = tmp_path / "test.db"
        from tinydb.errors import TransactionAlreadyActive

        db = Database(str(path))
        db._executor._tx.begin()
        with pytest.raises(TransactionAlreadyActive):
            db._executor._tx.begin()
        db.close()
