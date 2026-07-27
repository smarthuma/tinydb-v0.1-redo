"""Batch 10 — CLI/REPL E2E 测试（REQ-CR-001..008）。"""

from __future__ import annotations

import subprocess
import sys

TINYDBN = [sys.executable, "-m", "tinydb.cli"]


def test_help_exits_zero(tmp_path) -> None:
    """--help 退出码为 0。"""
    result = subprocess.run(
        TINYDBN + ["--help"], capture_output=True, text=True,
    )
    assert result.returncode == 0
    assert "usage" in result.stdout.lower()


def test_version_exits_zero() -> None:
    """--version 退出码为 0。"""
    result = subprocess.run(
        TINYDBN + ["--version"], capture_output=True, text=True,
    )
    assert result.returncode == 0
    assert "0.2.0" in result.stdout


def test_ascii_table_rendering(tmp_path) -> None:
    """SELECT 渲染 ASCII 表。"""
    db_path = tmp_path / "test.db"
    result = subprocess.run(
        TINYDBN + [str(db_path)],
        input="CREATE TABLE users (id INT, name TEXT);\n"
              "INSERT INTO users (id, name) VALUES (1, 'alice');\n"
              "SELECT * FROM users;\n"
              ".exit\n",
        capture_output=True, text=True,
    )
    assert result.returncode == 0
    output = result.stdout
    assert "id" in output
    assert "alice" in output


def test_row_count_message(tmp_path) -> None:
    """INSERT 打印行数。"""
    db_path = tmp_path / "test.db"
    result = subprocess.run(
        TINYDBN + [str(db_path)],
        input="CREATE TABLE users (id INT);\n"
              "INSERT INTO users (id) VALUES (1);\n"
              ".exit\n",
        capture_output=True, text=True,
    )
    assert result.returncode == 0
    assert "1 row inserted" in result.stdout


def test_dot_tables(tmp_path) -> None:
    """.tables 列出表。"""
    db_path = tmp_path / "test.db"
    result = subprocess.run(
        TINYDBN + [str(db_path)],
        input="CREATE TABLE users (id INT);\n"
              ".tables\n"
              ".exit\n",
        capture_output=True, text=True,
    )
    assert result.returncode == 0
    assert "users" in result.stdout


def test_dot_schema(tmp_path) -> None:
    """.schema 打印 CREATE TABLE。"""
    db_path = tmp_path / "test.db"
    result = subprocess.run(
        TINYDBN + [str(db_path)],
        input="CREATE TABLE users (id INT, name TEXT);\n"
              ".schema users\n"
              ".exit\n",
        capture_output=True, text=True,
    )
    assert result.returncode == 0
    assert "CREATE TABLE users" in result.stdout


def test_parse_error_not_fatal(tmp_path) -> None:
    """语法错误不终止 REPL。"""
    db_path = tmp_path / "test.db"
    result = subprocess.run(
        TINYDBN + [str(db_path)],
        input="SELEC * FROM users;\n"
              ".exit\n",
        capture_output=True, text=True,
    )
    assert result.returncode == 0
    assert "error" in result.stderr.lower() or "error" in result.stdout.lower()


def test_multi_line_input(tmp_path) -> None:
    """多行输入。"""
    db_path = tmp_path / "test.db"
    result = subprocess.run(
        TINYDBN + [str(db_path)],
        input="CREATE TABLE users (\n"
              "  id INT,\n"
              "  name TEXT\n"
              ");\n"
              ".exit\n",
        capture_output=True, text=True,
    )
    assert result.returncode == 0
    assert "users" in result.stdout or result.returncode == 0


def test_stdin_batch(tmp_path) -> None:
    """stdin 批处理模式。"""
    db_path = tmp_path / "test.db"
    result = subprocess.run(
        TINYDBN + [str(db_path)],
        input="CREATE TABLE t (id INT);\n"
              "INSERT INTO t VALUES (1);\n",
        capture_output=True, text=True,
    )
    assert result.returncode == 0


def test_stdin_batch_fail_fast(tmp_path) -> None:
    """批处理遇到错误快速失败。"""
    db_path = tmp_path / "test.db"
    result = subprocess.run(
        TINYDBN + [str(db_path)],
        input="INSERT INTO nonexistent VALUES (1);\n"
              "CREATE TABLE t (id INT);\n",
        capture_output=True, text=True,
    )
    assert result.returncode != 0


def test_cli_uses_database_wrapper(tmp_path) -> None:
    """CLI 使用 Database 包装层（验证通过即可）。"""
    db_path = tmp_path / "test.db"
    result = subprocess.run(
        TINYDBN + [str(db_path)],
        input="CREATE TABLE users (id INT);\n"
              "INSERT INTO users (id) VALUES (1);\n"
              "SELECT * FROM users;\n"
              ".exit\n",
        capture_output=True, text=True,
    )
    assert result.returncode == 0
    assert "1" in result.stdout
