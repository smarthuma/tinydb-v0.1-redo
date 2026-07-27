"""CLI / REPL 入口（REQ-CR-001..008 + v0.2 CLI Enhanced）。

新增：readline 行编辑、pygments 高亮、.explain、.mode/.timer/.width/.nullvalue、--color。
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from typing import TextIO

from tinydb import Database, __version__
from tinydb.cli_dotcommands import handle_dot_command
from tinydb.cli_renderers import print_csv, print_json, print_table
from tinydb.errors import ParseError, TinyDBError, format

# Optional deps — lazy / graceful degradation
try:
    import readline  # noqa: F401
    _readline_ok: bool = True
except ImportError:
    _readline_ok = False

_pygments_ok: bool = False


class _ReplConfig:
    """REPL 会话状态，由 _run_repl 持有，传递给 handle_dot_command / _execute_one。"""

    def __init__(self) -> None:
        self.mode: str = "table"
        self.timer: bool = False
        self.width: int = 30
        self.nullvalue: str = ""
        self.color: bool = False


__all__: list[str] = ["main"]


def main(
    argv: list[str] | None = None,
    stdin: TextIO = sys.stdin,
    stdout: TextIO = sys.stdout,
    stderr: TextIO = sys.stderr,
) -> int:
    """CLI 入口。"""
    parser = _build_parser()
    args = parser.parse_args(argv)
    if getattr(args, "version", False):
        print(f"tinydb {__version__}", file=stdout)
        return 0

    db = Database(args.path)
    try:
        if not stdin.isatty():
            return _run_batch(db, stdin, stdout, stderr)
        _run_repl(db, stdin, stdout, stderr, args.color)
        return 0
    finally:
        db.close()


def _build_parser() -> argparse.ArgumentParser:
    """构建 argparse 解析器。"""
    parser = argparse.ArgumentParser(
        prog="tinydb", description="TinyDB interactive SQL shell",
    )
    parser.add_argument(
        "path", nargs="?", default=None, help="path to .db file",
    )
    parser.add_argument(
        "--version", action="store_true", help="show version and exit",
    )
    parser.add_argument(
        "--color", choices=["on", "off", "auto"], default="auto",
        help="initial syntax highlighting mode (default: auto)",
    )
    return parser


def _resolve_initial_color(color_arg: str, stdout: TextIO) -> bool:
    """根据 --color 参数与 stdout tty 决定初始颜色模式。"""
    if color_arg == "off":
        return False
    if color_arg == "on":
        return _ensure_pygments()
    if hasattr(stdout, "isatty") and stdout.isatty():
        return _ensure_pygments()
    return False


def _ensure_pygments() -> bool:
    """懒加载 pygments；返回是否可用。"""
    global _pygments_ok
    if _pygments_ok:
        return True
    try:
        import pygments  # type: ignore[import-untyped]  # noqa: F401
        from pygments.formatters import (  # type: ignore[import-untyped]
            TerminalFormatter,  # noqa: F401
        )
        from pygments.lexers import SqlLexer  # type: ignore[import-untyped]  # noqa: F401

        _pygments_ok = True
        return True
    except ImportError:
        _pygments_ok = False
        return False


def _highlight_sql(sql: str) -> str:
    """高亮 SQL；pygments 不可用时返回原始 SQL。"""
    if not _pygments_ok:
        return sql
    from pygments import highlight  # type: ignore[import-untyped, unused-ignore]
    from pygments.formatters import (  # type: ignore[import-untyped, unused-ignore]
        TerminalFormatter,
    )
    from pygments.lexers import SqlLexer  # type: ignore[import-untyped, unused-ignore]

    result = highlight(sql, SqlLexer(), TerminalFormatter())
    return result if isinstance(result, str) else sql


def _maybe_warn_pygments(stderr: TextIO, warned: list[bool]) -> None:
    """一次性 pygments 不可用提示。"""
    if warned[0]:
        return
    warned[0] = True
    if not _pygments_ok:
        print("pygments not installed: syntax coloring disabled", file=stderr)


def _maybe_warn_readline(stderr: TextIO, warned: list[bool]) -> None:
    """一次性 readline 不可用提示。"""
    if warned[0]:
        return
    warned[0] = True
    if not _readline_ok:
        print("readline unavailable: line editing disabled", file=stderr)


def _setup_readline(history_path: str, warned: list[bool]) -> None:
    """配置 readline 与历史持久化；不可用时静默降级。"""
    _maybe_warn_readline(sys.stderr, warned)
    if not _readline_ok:
        return
    try:
        readline.read_history_file(history_path)
    except (FileNotFoundError, PermissionError, OSError):
        pass
    readline.set_history_length(1000)
    try:
        readline.set_completer(_completer)
        readline.parse_and_bind("tab: complete")
    except Exception:
        pass


def _completer(text: str, state: int) -> str | None:
    """简易 SQL 关键词补全。"""
    keywords = [
        "SELECT", "FROM", "WHERE", "INSERT", "INTO", "VALUES",
        "CREATE", "TABLE", "DROP", "DELETE", "UPDATE", "SET",
        "ORDER", "BY", "LIMIT", "OFFSET", "GROUP", "HAVING",
        "JOIN", "INNER", "LEFT", "ON", "AS", "AND", "OR", "NOT",
        "NULL", "IS", "IN", "BETWEEN", "LIKE", "EXPLAIN",
    ]
    matches = [k for k in keywords if k.lower().startswith(text.lower())]
    return matches[state] if state < len(matches) else None


def _save_history(history_path: str) -> None:
    """保存 readline 历史到文件。"""
    if not _readline_ok:
        return
    try:
        readline.write_history_file(history_path)
    except (PermissionError, OSError):
        pass


def _history_path() -> str:
    """历史文件路径。"""
    return os.path.expanduser("~/.tinydb_history")


def _run_batch(
    db: Database, stdin: TextIO, stdout: TextIO, stderr: TextIO,
) -> int:
    """批处理模式。"""
    buffer: list[str] = []
    has_error = False
    for raw_line in stdin:
        stripped = raw_line.strip()
        if not stripped:
            continue
        if stripped.startswith("."):
            cmd = stripped.split()[0].lower()
            if cmd in (".exit", ".quit"):
                break
            if cmd == ".tables" and db._executor is not None:
                for t in db._executor.list_tables():
                    print(t, file=stdout)
                continue
            if cmd == ".schema" and len(stripped.split()) >= 2 and db._executor is not None:
                name = stripped.split()[1]
                try:
                    meta = db._executor.get_table(name)
                    cols = ", ".join(f"{c} {t.value}" for c, t in meta.schema)
                    print(f"CREATE TABLE {name} ({cols});", file=stdout)
                except TinyDBError as exc:
                    print(format(exc), file=stderr)
                    has_error = True
                continue
            continue
        buffer.append(raw_line.rstrip("\n"))
        if stripped.endswith(";"):
            sql = " ".join(buffer).strip()
            buffer = []
            if sql:
                try:
                    _execute_one(db, sql, stdout)
                except ParseError as exc:
                    print(format(exc), file=stderr)
                except TinyDBError as exc:
                    print(format(exc), file=stderr)
                    has_error = True
    return 1 if has_error else 0


def _run_repl(
    db: Database,
    stdin: TextIO,
    stdout: TextIO,
    stderr: TextIO,
    color_arg: str = "auto",
) -> None:
    """REPL 循环。"""
    print(f"TinyDB {__version__}. Type .help for help.", file=stdout)
    cfg = _ReplConfig()
    cfg.color = _resolve_initial_color(color_arg, stdout)

    history_file = _history_path()
    readline_warned: list[bool] = [False]
    pygments_warned: list[bool] = [False]
    _setup_readline(history_file, readline_warned)

    buffer: list[str] = []
    try:
        while True:
            try:
                line = _read_line(cfg, pygments_warned, stdin, bool(buffer))
            except (EOFError, KeyboardInterrupt):
                print(file=stdout)
                return

            stripped = line.strip()
            if not stripped:
                continue

            if stripped.startswith("."):
                if handle_dot_command(stripped, db, stdout, stderr, cfg):
                    return
                continue

            buffer.append(line)
            if stripped.endswith(";"):
                sql = " ".join(buffer).strip()
                buffer = []
                if sql:
                    try:
                        _execute_one(db, sql, stdout, cfg)
                    except TinyDBError as exc:
                        print(format(exc), file=stderr)
    finally:
        _save_history(history_file)


def _read_line(
    cfg: _ReplConfig, warned: list[bool], stdin: TextIO, in_multiline: bool,
) -> str:
    """读取一行输入（带提示符）。"""
    _maybe_warn_pygments(sys.stderr, warned)
    prompt = "   ...> " if in_multiline else "tinydb> "
    try:
        if stdin.isatty():
            return input(prompt)
        # 非交互模式（管道/重定向）：按行读取
        raw = stdin.readline()
        if not raw:
            raise EOFError
        return raw.rstrip("\n")
    except EOFError:
        raise


def _execute_one(db: Database, sql: str, stdout: TextIO, cfg: _ReplConfig | None = None) -> None:
    """执行单条 SQL 并按 cfg.mode 分派渲染。"""
    cfg = cfg or _ReplConfig()
    start = time.monotonic() if cfg.timer else None
    result = db.execute(sql)

    def _emit_time() -> None:
        if cfg.timer and start is not None:
            elapsed_ms = (time.monotonic() - start) * 1000
            print(f"Time: {elapsed_ms:.1f} ms", file=stdout)

    if not result:
        _emit_time()
        return
    if isinstance(result, list) and result:
        first = result[0]
        if "status" in first:
            print("OK", file=stdout)
            _emit_time()
            return
        if "rows_affected" in first:
            n = first["rows_affected"]
            print(f"{n} row{'s' if n != 1 else ''} inserted", file=stdout)
            _emit_time()
            return
        if cfg.mode == "csv":
            print_csv(result, stdout, cfg.width, cfg.nullvalue)
        elif cfg.mode == "json":
            print_json(result, stdout)
        else:
            print_table(result, stdout, cfg.width, cfg.nullvalue)
    _emit_time()


# Module-level warning flags for tests
_readline_warned: list[bool] = [False]


def _emit_readline_warning_if_needed() -> None:
    """测试钩子：触发 readline 警告（仅一次）。"""
    if _readline_warned[0]:
        return
    _readline_warned[0] = True
    if not _readline_ok:
        print("readline unavailable: line editing disabled")


if __name__ == "__main__":
    sys.exit(main())
