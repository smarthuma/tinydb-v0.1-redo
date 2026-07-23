"""Batch 11 — crash recovery E2E（REQ-TM-005 + REWRITE-PENDING 3.1）。"""

from __future__ import annotations

import os
import signal
import subprocess
import sys
import time

import pytest

TINYDBN = [sys.executable, "-m", "tinydb.cli"]


def test_crash_recovery_committed(tmp_path) -> None:
    """已提交事务在 crash 后数据不丢。"""
    db_path = tmp_path / "test.db"
    # 写入一条已提交的数据
    result = subprocess.run(
        TINYDBN + [str(db_path)],
        input="CREATE TABLE users (id INT);\n"
              "INSERT INTO users (id) VALUES (1);\n"
              ".exit\n",
        capture_output=True, text=True,
    )
    assert result.returncode == 0
    # 重新打开验证
    result2 = subprocess.run(
        TINYDBN + [str(db_path)],
        input="SELECT * FROM users;\n"
              ".exit\n",
        capture_output=True, text=True,
    )
    assert result2.returncode == 0
    assert "1" in result2.stdout


def test_crash_recovery_kill9(tmp_path) -> None:
    """kill -9 后 WAL replay 恢复已提交数据。"""
    db_path = tmp_path / "test.db"
    # 启动一个长时间运行的进程，写入后不退出
    proc = subprocess.Popen(
        TINYDBN + [str(db_path)],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    # 写入已提交数据
    proc.stdin.write("CREATE TABLE users (id INT);\n")
    proc.stdin.write("INSERT INTO users (id) VALUES (42);\n")
    proc.stdin.flush()
    time.sleep(0.5)
    # kill -9 模拟 crash
    os.kill(proc.pid, signal.SIGKILL)
    proc.wait()
    # 重新打开验证数据存在
    result = subprocess.run(
        TINYDBN + [str(db_path)],
        input="SELECT * FROM users;\n"
              ".exit\n",
        capture_output=True, text=True,
    )
    assert result.returncode == 0
    assert "42" in result.stdout


def test_reopen_after_reopen(tmp_path) -> None:
    """多次开闭后数据一致。"""
    db_path = tmp_path / "test.db"
    # 首次创建表
    result = subprocess.run(
        TINYDBN + [str(db_path)],
        input=(
            "CREATE TABLE counter (n INT);\n"
            "INSERT INTO counter (n) VALUES (0);\n"
            ".exit\n"
        ),
        capture_output=True, text=True,
    )
    assert result.returncode == 0
    # 后续仅插入
    for i in range(1, 3):
        result = subprocess.run(
            TINYDBN + [str(db_path)],
            input=(
                f"INSERT INTO counter (n) VALUES ({i});\n"
                ".exit\n"
            ),
            capture_output=True, text=True,
        )
        assert result.returncode == 0
    # 最终验证有 3 行
    result = subprocess.run(
        TINYDBN + [str(db_path)],
        input="SELECT COUNT(*) FROM counter;\n"
              ".exit\n",
        capture_output=True, text=True,
    )
    assert result.returncode == 0
    assert "3" in result.stdout
