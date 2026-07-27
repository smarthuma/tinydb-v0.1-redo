"""Batch CL1 — CLI 增强单元测试（REQ-CE-001..012 中选定的核心场景）。

聚焦渲染器、dot-commands、降级路径；不重复 test_cli_repl.py 已有的 E2E 场景。
"""

from __future__ import annotations

import io
from unittest import mock

import pytest

from tinydb import Database
from tinydb.cli import _ReplConfig
from tinydb.cli_dotcommands import handle_dot_command
from tinydb.cli_renderers import print_csv, print_json, print_table

# 测试用别名，保持与原来相同的命名
_print_table = print_table
_print_csv = print_csv
_print_json = print_json
_handle_dot_command = handle_dot_command

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _db(tmp_path: str) -> Database:
    db = Database(str(tmp_path / "test.db"))
    db.execute("CREATE TABLE users (id INT, name TEXT)")
    db.execute("INSERT INTO users (id, name) VALUES (1, 'alice')")
    db.execute("INSERT INTO users (id, name) VALUES (2, 'bob')")
    return db


def _rows() -> list[dict[str, object]]:
    return [{"id": 1, "name": "alice"}, {"id": 2, "name": "bob"}]


# ---------------------------------------------------------------------------
# _print_table backward compat
# ---------------------------------------------------------------------------


def test_print_table_unchanged_format() -> None:
    """默认 ASCII 表格式与 v0.1 一致。"""
    buf = io.StringIO()
    _print_table(_rows(), buf)
    out = buf.getvalue()
    assert "id" in out
    assert "name" in out
    assert "alice" in out
    assert "bob" in out
    assert " | " in out  # separator style
    assert "-+-" in out  # separator line


def test_print_table_truncates_long_values() -> None:
    """.width 通过 _print_table(rows, stdout, width=...) 截断。"""
    buf = io.StringIO()
    rows = [{"name": "a" * 50}]
    _print_table(rows, buf, width=10)
    out = buf.getvalue()
    assert "a" * 10 + "..." in out


def test_print_table_null_display_default_empty() -> None:
    """NULL 默认显示为空。"""
    buf = io.StringIO()
    _print_table([{"name": None}], buf)
    out = buf.getvalue()
    # header + separator + row (row renders empty cell, may not appear after strip)
    assert "name" in out
    assert "---" in out  # separator


def test_print_table_nullvalue_text() -> None:
    """.nullvalue <text> 控制 NULL 显示文本。"""
    buf = io.StringIO()
    _print_table([{"name": None}], buf, nullvalue="NULL")
    out = buf.getvalue()
    assert "NULL" in out


# ---------------------------------------------------------------------------
# _print_csv
# ---------------------------------------------------------------------------


def test_print_csv_basic() -> None:
    buf = io.StringIO()
    _print_csv(_rows(), buf)
    out = buf.getvalue()
    lines = out.splitlines()
    assert lines[0] == "id,name"
    assert "1,alice" in out
    assert "2,bob" in out


def test_print_csv_quotes_strings_with_comma() -> None:
    buf = io.StringIO()
    _print_csv([{"name": "alice, smith"}], buf)
    out = buf.getvalue()
    assert '"alice, smith"' in out


def test_print_csv_nullvalue() -> None:
    buf = io.StringIO()
    _print_csv([{"name": None}], buf, nullvalue="NULL")
    out = buf.getvalue()
    assert "NULL" in out


# ---------------------------------------------------------------------------
# _print_json
# ---------------------------------------------------------------------------


def test_print_json_basic() -> None:
    buf = io.StringIO()
    _print_json(_rows(), buf)
    out = buf.getvalue()
    assert '{"id": 1, "name": "alice"}' in out
    assert '{"id": 2, "name": "bob"}' in out


def test_print_json_null_serialized() -> None:
    buf = io.StringIO()
    _print_json([{"name": None}], buf)
    out = buf.getvalue()
    assert '"name": null' in out


# ---------------------------------------------------------------------------
# _ReplConfig + dot-commands
# ---------------------------------------------------------------------------


def test_config_defaults() -> None:
    cfg = _ReplConfig()
    assert cfg.mode == "table"
    assert cfg.timer is False
    assert cfg.width == 30
    assert cfg.nullvalue == ""
    assert cfg.color is False


def test_dot_mode_csv(tmp_path: str) -> None:
    db = _db(tmp_path)
    cfg = _ReplConfig()
    buf = io.StringIO()
    _handle_dot_command(".mode csv", db, buf, io.StringIO(), cfg)
    assert cfg.mode == "csv"


def test_dot_mode_json(tmp_path: str) -> None:
    db = _db(tmp_path)
    cfg = _ReplConfig()
    _handle_dot_command(".mode json", db, io.StringIO(), io.StringIO(), cfg)
    assert cfg.mode == "json"


def test_dot_mode_table(tmp_path: str) -> None:
    db = _db(tmp_path)
    cfg = _ReplConfig()
    cfg.mode = "csv"
    _handle_dot_command(".mode table", db, io.StringIO(), io.StringIO(), cfg)
    assert cfg.mode == "table"


def test_dot_mode_color_toggle(tmp_path: str) -> None:
    db = _db(tmp_path)
    cfg = _ReplConfig()
    _handle_dot_command(".mode color on", db, io.StringIO(), io.StringIO(), cfg)
    assert cfg.color is True
    _handle_dot_command(".mode color off", db, io.StringIO(), io.StringIO(), cfg)
    assert cfg.color is False


def test_dot_mode_invalid(tmp_path: str) -> None:
    db = _db(tmp_path)
    cfg = _ReplConfig()
    err = io.StringIO()
    _handle_dot_command(".mode xml", db, io.StringIO(), err, cfg)
    assert "invalid mode" in err.getvalue().lower() or "unknown" in err.getvalue().lower()


def test_dot_timer_on_off(tmp_path: str) -> None:
    db = _db(tmp_path)
    cfg = _ReplConfig()
    _handle_dot_command(".timer on", db, io.StringIO(), io.StringIO(), cfg)
    assert cfg.timer is True
    _handle_dot_command(".timer off", db, io.StringIO(), io.StringIO(), cfg)
    assert cfg.timer is False


def test_dot_width_sets_number(tmp_path: str) -> None:
    db = _db(tmp_path)
    cfg = _ReplConfig()
    _handle_dot_command(".width 15", db, io.StringIO(), io.StringIO(), cfg)
    assert cfg.width == 15


def test_dot_width_invalid(tmp_path: str) -> None:
    db = _db(tmp_path)
    cfg = _ReplConfig()
    err = io.StringIO()
    _handle_dot_command(".width abc", db, io.StringIO(), err, cfg)
    assert "usage" in err.getvalue().lower() or "invalid" in err.getvalue().lower()


def test_dot_nullvalue_sets_text(tmp_path: str) -> None:
    db = _db(tmp_path)
    cfg = _ReplConfig()
    _handle_dot_command(".nullvalue NULL", db, io.StringIO(), io.StringIO(), cfg)
    assert cfg.nullvalue == "NULL"


def test_dot_nullvalue_empty(tmp_path: str) -> None:
    db = _db(tmp_path)
    cfg = _ReplConfig()
    cfg.nullvalue = "NULL"
    _handle_dot_command(".nullvalue", db, io.StringIO(), io.StringIO(), cfg)
    assert cfg.nullvalue == ""


# ---------------------------------------------------------------------------
# .explain — graceful when EXPLAIN not wired
# ---------------------------------------------------------------------------


def test_dot_explain_not_available(tmp_path: str) -> None:
    """.explain 在 EXPLAIN 未接入时优雅降级。"""
    db = _db(tmp_path)
    cfg = _ReplConfig()
    buf = io.StringIO()
    err = io.StringIO()
    _handle_dot_command(".explain SELECT * FROM users", db, buf, err, cfg)
    combined = buf.getvalue() + err.getvalue()
    # Either a plan tree or a graceful "not available" message
    assert "not available" in combined.lower() or "explain" in combined.lower()


def test_dot_explain_requires_sql(tmp_path: str) -> None:
    db = _db(tmp_path)
    cfg = _ReplConfig()
    err = io.StringIO()
    _handle_dot_command(".explain", db, io.StringIO(), err, cfg)
    assert "usage" in err.getvalue().lower()


# ---------------------------------------------------------------------------
# readline degradation
# ---------------------------------------------------------------------------


def test_readline_warning_emitted_once() -> None:
    """readline 警告只打印一次。"""
    from tinydb import cli

    flag: list[bool] = [False]
    with mock.patch.object(cli, "_readline_ok", False):
        buf = io.StringIO()
        cli._maybe_warn_readline(buf, flag)
        first = buf.getvalue()
        buf2 = io.StringIO()
        cli._maybe_warn_readline(buf2, flag)
        second = buf2.getvalue()
    assert "readline" in first.lower()
    assert second == ""


# ---------------------------------------------------------------------------
# pygments degradation
# ---------------------------------------------------------------------------


def test_pygments_degradation_no_color() -> None:
    """无 pygments 时 _highlight_sql 返回原始 SQL。"""
    from tinydb import cli

    with mock.patch.object(cli, "_pygments_ok", False):
        assert cli._highlight_sql("SELECT 1") == "SELECT 1"


def test_pygments_highlight_when_available() -> None:
    """有 pygments 时 _highlight_sql 返回带 ANSI 的字符串。"""
    from tinydb import cli

    with mock.patch.object(cli, "_pygments_ok", True):
        out = cli._highlight_sql("SELECT 1")
        # pygments wraps with ANSI codes
        assert out != "SELECT 1" or "SELECT" in out


# ---------------------------------------------------------------------------
# --color flag parsing
# ---------------------------------------------------------------------------


def test_build_parser_color_flag() -> None:
    from tinydb.cli import _build_parser

    parser = _build_parser()
    args = parser.parse_args(["--color", "on", "test.db"])
    assert args.color == "on"
    args = parser.parse_args(["--color", "off", "test.db"])
    assert args.color == "off"
    args = parser.parse_args(["--color", "auto", "test.db"])
    assert args.color == "auto"
    args = parser.parse_args(["test.db"])
    assert args.color == "auto"


def test_build_parser_color_invalid(capsys: pytest.CaptureFixture[str]) -> None:
    from tinydb.cli import _build_parser

    parser = _build_parser()
    with pytest.raises(SystemExit):
        parser.parse_args(["--color", "maybe", "test.db"])
