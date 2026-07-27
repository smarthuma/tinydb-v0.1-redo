"""Batch CL1 — CLI 增强端到端测试（REPL 驱动，StringIO stdin/stdout）。

通过 main() 直接驱动，避免 subprocess 开销；覆盖 .mode/.timer/.width/.nullvalue
以及默认输出向后兼容。
"""

from __future__ import annotations

import io

from tinydb.cli import main


class _TtyStringIO(io.StringIO):
    """StringIO subclass that reports isatty() == True for REPL driving。"""

    def isatty(self) -> bool:  # type: ignore[override]
        return True


def _run_repl(lines: list[str], tmp_path, color: str = "off") -> tuple[str, str]:
    """运行 REPL 并返回 (stdout, stderr)。"""
    db_path = str(tmp_path / "test.db")
    stdin = _TtyStringIO("\n".join(lines) + "\n")
    stdout = io.StringIO()
    stderr = io.StringIO()
    main([db_path, "--color", color], stdin=stdin, stdout=stdout, stderr=stderr)
    return stdout.getvalue(), stderr.getvalue()


def test_default_output_unchanged(tmp_path) -> None:
    """默认输出格式与 v0.1 一致（ASCII 表）。"""
    out, _ = _run_repl(
        [
            "CREATE TABLE users (id INT, name TEXT);",
            "INSERT INTO users (id, name) VALUES (1, 'alice');",
            "SELECT * FROM users;",
            ".exit",
        ],
        tmp_path,
    )
    assert "id" in out
    assert "alice" in out
    assert " | " in out


def test_mode_csv_output(tmp_path) -> None:
    """.mode csv 输出 CSV 格式。"""
    out, _ = _run_repl(
        [
            "CREATE TABLE users (id INT, name TEXT);",
            "INSERT INTO users (id, name) VALUES (1, 'alice');",
            ".mode csv",
            "SELECT * FROM users;",
            ".exit",
        ],
        tmp_path,
    )
    assert "id,name" in out
    assert "1,alice" in out


def test_mode_json_output(tmp_path) -> None:
    """.mode json 输出 JSON lines。"""
    out, _ = _run_repl(
        [
            "CREATE TABLE users (id INT, name TEXT);",
            "INSERT INTO users (id, name) VALUES (1, 'alice');",
            ".mode json",
            "SELECT * FROM users;",
            ".exit",
        ],
        tmp_path,
    )
    assert '{"id": 1, "name": "alice"}' in out


def test_timer_on_shows_ms(tmp_path) -> None:
    """.timer on 在每条查询后打印耗时。"""
    out, _ = _run_repl(
        [
            "CREATE TABLE users (id INT);",
            ".timer on",
            "SELECT * FROM users;",
            ".exit",
        ],
        tmp_path,
    )
    assert "Time:" in out
    assert "ms" in out


def test_width_truncates(tmp_path) -> None:
    """.width 10 截断长值。"""
    out, _ = _run_repl(
        [
            "CREATE TABLE users (name TEXT);",
            "INSERT INTO users (name) VALUES ('abcdefghijklmnopqrstuvwxyz');",
            ".width 10",
            "SELECT * FROM users;",
            ".exit",
        ],
        tmp_path,
    )
    # 10 chars + "..."
    assert "abcdefghij..." in out


def test_nullvalue_shows_text(tmp_path) -> None:
    """.nullvalue NULL 显示 NULL 文本。"""
    out, _ = _run_repl(
        [
            "CREATE TABLE users (name TEXT);",
            "INSERT INTO users (name) VALUES (NULL);",
            ".nullvalue NULL",
            "SELECT name FROM users;",
            ".exit",
        ],
        tmp_path,
    )
    assert "NULL" in out


def test_mode_color_toggle(tmp_path) -> None:
    """.mode color on 切换高亮。"""
    out, err = _run_repl(
        [
            ".mode color on",
            ".mode color",
            ".exit",
        ],
        tmp_path,
    )
    combined = out + err
    # either "color on" ack, or pygments degradation notice
    assert "color" in combined.lower()


def test_dot_tables_still_works(tmp_path) -> None:
    """原有 .tables 命令仍工作。"""
    out, _ = _run_repl(
        [
            "CREATE TABLE accounts (id INT);",
            ".tables",
            ".exit",
        ],
        tmp_path,
    )
    assert "accounts" in out


def test_dot_schema_still_works(tmp_path) -> None:
    """原有 .schema 命令仍工作。"""
    out, _ = _run_repl(
        [
            "CREATE TABLE accounts (id INT, name TEXT);",
            ".schema accounts",
            ".exit",
        ],
        tmp_path,
    )
    assert "CREATE TABLE accounts" in out


def test_dot_exit_clean(tmp_path) -> None:
    """REPL 干净退出。"""
    db_path = str(tmp_path / "test.db")
    stdin = io.StringIO(".exit\n")
    stdout = io.StringIO()
    rc = main([db_path], stdin=stdin, stdout=stdout)
    assert rc == 0


def test_multiline_accumulates_one_history_entry(tmp_path) -> None:
    """多行输入累积为一条完整 SQL 执行。"""
    out, _ = _run_repl(
        [
            "CREATE TABLE users (",
            "  id INT,",
            "  name TEXT",
            ");",
            "INSERT INTO users (id, name) VALUES (1, 'alice');",
            "SELECT * FROM users;",
            ".exit",
        ],
        tmp_path,
    )
    assert "alice" in out
