"""CLI dot-commands 处理器（.mode / .timer / .width / .nullvalue / .explain）。"""

from __future__ import annotations

from typing import TYPE_CHECKING, TextIO

from tinydb import Database
from tinydb.cli_renderers import render_plan_node
from tinydb.errors import TinyDBError, format

if TYPE_CHECKING:
    from tinydb.cli import _ReplConfig


def handle_dot_command(
    line: str,
    db: Database,
    stdout: TextIO,
    stderr: TextIO,
    cfg: _ReplConfig,
) -> bool:
    """处理 dot-commands。返回 True 表示退出。"""
    parts = line.split()
    cmd = parts[0].lower()
    executor = db._executor
    if cmd in (".exit", ".quit"):
        return True
    if cmd == ".help":
        _print_help(stdout)
        return False
    if cmd == ".tables":
        if executor is not None:
            for table in executor.list_tables():
                print(table, file=stdout)
        return False
    if cmd == ".schema":
        return _handle_schema(parts[1:], db, stdout, stderr, executor)
    if cmd == ".mode":
        return _handle_mode(parts[1:], stdout, stderr, cfg)
    if cmd == ".timer":
        return _handle_timer(parts[1:], stdout, stderr, cfg)
    if cmd == ".width":
        return _handle_width(parts[1:], stdout, stderr, cfg)
    if cmd == ".nullvalue":
        return _handle_nullvalue(parts[1:], stdout, cfg)
    if cmd == ".explain":
        return _handle_explain(parts[1:], db, stdout, stderr)
    print(f"unknown command: {cmd}", file=stderr)
    return False


def _print_help(stdout: TextIO) -> None:
    """打印 dot-command 帮助。"""
    print(
        ".tables  - list tables\n"
        ".schema <t> - show CREATE TABLE\n"
        ".mode table|csv|json|color [on|off] - set output mode\n"
        ".timer on|off - show query wall-clock time\n"
        ".width <n> - max column width (default 30)\n"
        ".nullvalue <text> - display text for NULL\n"
        ".explain <SQL> - show query plan without executing\n"
        ".exit/.quit - exit\n"
        ".help - this message",
        file=stdout,
    )


def _handle_schema(
    args: list[str],
    db: Database,
    stdout: TextIO,
    stderr: TextIO,
    executor: object,
) -> bool:
    """处理 .schema 子命令。"""
    if not args:
        print("usage: .schema <table>", file=stderr)
        return False
    if executor is None:
        return False
    name = args[0]
    try:
        meta = executor.get_table(name)  # type: ignore[attr-defined]
        cols = ", ".join(f"{c} {t.value}" for c, t in meta.schema)
        print(f"CREATE TABLE {name} ({cols});", file=stdout)
    except TinyDBError as exc:
        print(format(exc), file=stderr)
    return False


def _handle_mode(
    args: list[str],
    stdout: TextIO,
    stderr: TextIO,
    cfg: _ReplConfig,
) -> bool:
    """处理 .mode 子命令。"""
    from tinydb.cli import _ensure_pygments

    if not args:
        print(f"current mode: {cfg.mode}", file=stdout)
        return False
    sub = args[0].lower()
    if sub == "color":
        if len(args) < 2:
            print(f"color: {'on' if cfg.color else 'off'}", file=stdout)
            return False
        arg = args[1].lower()
        if arg == "on":
            if not _ensure_pygments():
                print("pygments not installed: syntax coloring disabled", file=stderr)
                cfg.color = False
            else:
                cfg.color = True
                print("color on", file=stdout)
        elif arg == "off":
            cfg.color = False
            print("color off", file=stdout)
        else:
            print("usage: .mode color on|off", file=stderr)
        return False
    if sub in ("table", "csv", "json"):
        cfg.mode = sub
        print(f"mode: {sub}", file=stdout)
        return False
    print(f"invalid mode: {sub!r} (expected table|csv|json|color)", file=stderr)
    return False


def _handle_timer(
    args: list[str],
    stdout: TextIO,
    stderr: TextIO,
    cfg: _ReplConfig,
) -> bool:
    """处理 .timer 子命令。"""
    if not args:
        print("usage: .timer on|off", file=stderr)
        return False
    arg = args[0].lower()
    if arg == "on":
        cfg.timer = True
        print("timer on", file=stdout)
    elif arg == "off":
        cfg.timer = False
        print("timer off", file=stdout)
    else:
        print("usage: .timer on|off", file=stderr)
    return False


def _handle_width(
    args: list[str],
    stdout: TextIO,
    stderr: TextIO,
    cfg: _ReplConfig,
) -> bool:
    """处理 .width 子命令。"""
    if not args:
        print(f"width: {cfg.width}", file=stdout)
        return False
    try:
        n = int(args[0])
    except ValueError:
        print(f"invalid width: {args[0]!r}", file=stderr)
        return False
    if n < 1:
        print("width must be >= 1", file=stderr)
        return False
    cfg.width = n
    print(f"width: {n}", file=stdout)
    return False


def _handle_nullvalue(
    args: list[str],
    stdout: TextIO,
    cfg: _ReplConfig,
) -> bool:
    """处理 .nullvalue 子命令。"""
    cfg.nullvalue = " ".join(args)
    print(f"nullvalue: {cfg.nullvalue!r}", file=stdout)
    return False


def _handle_explain(
    args: list[str],
    db: Database,
    stdout: TextIO,
    stderr: TextIO,
) -> bool:
    """处理 .explain 子命令。"""
    if not args:
        print("usage: .explain <SQL>", file=stderr)
        return False
    sql = " ".join(args)
    executor = db._executor
    if executor is None:
        print("EXPLAIN not available yet: no executor", file=stderr)
        return False
    try:
        plan = executor.execute("EXPLAIN " + sql)
    except (AttributeError, TinyDBError, NotImplementedError) as exc:
        print(f"EXPLAIN not available yet: {exc}", file=stderr)
        return False
    if isinstance(plan, list) and plan:
        for node in plan:
            render_plan_node(node, stdout)
    else:
        print("no plan", file=stdout)
    return False


