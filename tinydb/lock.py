"""连接级读写锁 + 文件锁（REQ-CC-001..004）。"""

from __future__ import annotations

import io
import threading
import time
from collections.abc import Iterator
from contextlib import contextmanager

from tinydb.errors import DatabaseBusy


class RWLock:
    """连接级读写锁：多读单写，写者优先。"""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._readers_ok = threading.Condition(self._lock)
        self._writers_ok = threading.Condition(self._lock)
        self._readers = 0
        self._writers = 0
        self._writer_waiters = 0

    def acquire_read(self, timeout: float = 5.0) -> None:
        """获取读锁。超时抛 DatabaseBusy。"""
        deadline = time.monotonic() + timeout
        with self._lock:
            while self._writers > 0 or self._writer_waiters > 0:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise DatabaseBusy("timeout acquiring read lock")
                self._readers_ok.wait(timeout=remaining)
            self._readers += 1

    def release_read(self) -> None:
        """释放读锁。"""
        with self._lock:
            self._readers -= 1
            if self._readers == 0:
                self._writers_ok.notify()

    def acquire_write(self, timeout: float = 5.0) -> None:
        """获取写锁。超时抛 DatabaseBusy。"""
        deadline = time.monotonic() + timeout
        with self._lock:
            self._writer_waiters += 1
            try:
                while self._readers > 0 or self._writers > 0:
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        raise DatabaseBusy("timeout acquiring write lock")
                    self._writers_ok.wait(timeout=remaining)
                self._writers += 1
            finally:
                self._writer_waiters -= 1

    def release_write(self) -> None:
        """释放写锁。"""
        with self._lock:
            self._writers -= 1
            self._writers_ok.notify()
            self._readers_ok.notify_all()

    @contextmanager
    def read(self, timeout: float = 5.0) -> Iterator[None]:
        """读锁上下文管理器。"""
        self.acquire_read(timeout)
        try:
            yield
        finally:
            self.release_read()

    @contextmanager
    def write(self, timeout: float = 5.0) -> Iterator[None]:
        """写锁上下文管理器。"""
        self.acquire_write(timeout)
        try:
            yield
        finally:
            self.release_write()


class FileLock:
    """多进程文件锁（Unix fcntl.flock）。"""

    def __init__(self, path: str) -> None:
        import fcntl

        self._fcntl = fcntl
        self._path = path
        self._file: io.IOBase | None = None
        self._fd: int | None = None

    def _open(self) -> None:
        if self._fd is None:
            self._file = open(self._path, "a+b")
            self._fd = self._file.fileno()

    def _get_fd(self) -> int:
        """获取已打开的文件描述符（调用方保证已 _open）。"""
        assert self._fd is not None
        return self._fd

    def shared(self, timeout: float = 5.0) -> None:
        """获取共享锁（多进程并发读）。"""
        import errno

        self._open()
        fd = self._get_fd()
        deadline = time.monotonic() + timeout
        while True:
            try:
                self._fcntl.flock(fd, self._fcntl.LOCK_SH | self._fcntl.LOCK_NB)
                return
            except OSError as exc:
                if exc.errno not in (errno.EAGAIN, errno.EWOULDBLOCK):
                    raise
                if time.monotonic() >= deadline:
                    raise DatabaseBusy(
                        f"timeout acquiring shared file lock on {self._path}",
                    ) from None
                time.sleep(0.05)

    def exclusive(self, timeout: float = 5.0) -> None:
        """获取排他锁（单进程写）。"""
        import errno

        self._open()
        fd = self._get_fd()
        deadline = time.monotonic() + timeout
        while True:
            try:
                self._fcntl.flock(fd, self._fcntl.LOCK_EX | self._fcntl.LOCK_NB)
                return
            except OSError as exc:
                if exc.errno not in (errno.EAGAIN, errno.EWOULDBLOCK):
                    raise
                if time.monotonic() >= deadline:
                    raise DatabaseBusy(
                        f"timeout acquiring exclusive file lock on {self._path}",
                    ) from None
                time.sleep(0.05)

    def release(self) -> None:
        """释放文件锁。"""
        if self._fd is not None:
            self._fcntl.flock(self._fd, self._fcntl.LOCK_UN)

    def close(self) -> None:
        """关闭文件描述符并释放锁。"""
        if self._fd is not None:
            try:
                self._fcntl.flock(self._fd, self._fcntl.LOCK_UN)
            except Exception:
                pass
            try:
                import os

                os.close(self._fd)
            except Exception:
                pass
            self._fd = None
        if self._file is not None:
            try:
                self._file.close()
            except Exception:
                pass
            self._file = None

    def __enter__(self) -> FileLock:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()


__all__ = ["RWLock", "FileLock", "DatabaseBusy"]
