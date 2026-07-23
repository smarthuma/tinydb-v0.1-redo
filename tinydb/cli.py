"""CLI / REPL 入口（REQ-CR-001..008）。"""

from __future__ import annotations

import argparse
import sys
from typing import TextIO

from tinydb import Database, __version__
from tinydb.errors import ParseError, TinyDBError, format

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
        _run_repl(db, stdin, stdout, stderr)
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
    return parser


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
        # dot-commands in batch mode
        if stripped.startswith("."):
            cmd = stripped.split()[0].lower()
            if cmd in (".exit", ".quit"):
                break
            if cmd == ".tables":
                if db._executor is not None:
                    for t in db._executor.list_tables():
                        print(t, file=stdout)
                continue
            if cmd == ".schema" and len(stripped.split()) >= 2:
                name = stripped.split()[1]
                if db._executor is None:
                    continue
                try:
                    meta = db._executor.get_table(name)
                    cols = ", ".join(f"{c} {t.value}" for c, t in meta.schema)
                    print(f"CREATE TABLE {name} ({cols});", file=stdout)
                except TinyDBError as exc:
                    print(format(exc), file=stderr)
                    has_error = True
                continue
            if cmd == ".help":
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
                    # 解析错误非致命，继续执行
                    print(format(exc), file=stderr)
                except TinyDBError as exc:
                    print(format(exc), file=stderr)
                    has_error = True
    return 1 if has_error else 0


def _run_repl(
    db: Database, stdin: TextIO, stdout: TextIO, stderr: TextIO,
) -> None:
    """REPL 循环。"""
    print(f"TinyDB {__version__}. Type .help for help.", file=stdout)
    buffer: list[str] = []
    while True:
        prompt = "tinydb> " if not buffer else "   ...> "
        try:
            line = input(prompt)
        except (EOFError, KeyboardInterrupt):
            print(file=stdout)
            return

        stripped = line.strip()
        if not stripped:
            continue

        # dot-commands
        if stripped.startswith("."):
            if _handle_dot_command(stripped, db, stdout, stderr):
                return
            continue

        buffer.append(line)
        if stripped.endswith(";"):
            sql = " ".join(buffer).strip()
            buffer = []
            try:
                _execute_one(db, sql, stdout)
            except TinyDBError as exc:
                print(format(exc), file=stderr)


def _handle_dot_command(
    line: str, db: Database, stdout: TextIO, stderr: TextIO,
) -> bool:
    """处理 dot-commands。返回 True 表示退出。"""
    parts = line.split()
    cmd = parts[0].lower()
    executor = db._executor
    if cmd in (".exit", ".quit"):
        return True
    if cmd == ".help":
        print(
            ".tables  - list tables\n"
            ".schema <t> - show CREATE TABLE\n"
            ".exit/.quit - exit\n"
            ".help - this message",
            file=stdout,
        )
        return False
    if cmd == ".tables":
        if executor is not None:
            for table in executor.list_tables():
                print(table, file=stdout)
        return False
    if cmd == ".schema":
        if len(parts) < 2:
            print("usage: .schema <table>", file=stderr)
            return False
        if executor is None:
            return False
        name = parts[1]
        try:
            meta = executor.get_table(name)
            cols = ", ".join(
                f"{c} {t.value}" for c, t in meta.schema
            )
            print(f"CREATE TABLE {name} ({cols});", file=stdout)
        except TinyDBError as exc:
            print(format(exc), file=stderr)
        return False
    print(f"unknown command: {cmd}", file=stderr)
    return False


def _execute_one(db: Database, sql: str, stdout: TextIO) -> None:
    """执行单条 SQL 并打印结果。"""
    result = db.execute(sql)
    if not result:
        return
    if isinstance(result, list) and result:
        first = result[0]
        if "status" in first:
            print("OK", file=stdout)
            return
        if "rows_affected" in first:
            n = first["rows_affected"]
            print(f"{n} row{'s' if n != 1 else ''} inserted", file=stdout)
            return
        _print_table(result, stdout)


def _print_table(rows: list[dict[str, object]], stdout: TextIO) -> None:
    """渲染 ASCII 表。"""
    if not rows:
        return
    columns = list(rows[0].keys())
    widths = [
        max(len(str(c)), max((len(str(r.get(c, ""))) for r in rows), default=0))
        for c in columns
    ]
    header = " | ".join(c.ljust(w) for c, w in zip(columns, widths, strict=False))
    sep = "-+-".join("-" * w for w in widths)
    print(header, file=stdout)
    print(sep, file=stdout)
    for row in rows:
        line = " | ".join(
            str(row.get(c, "")).ljust(w) for c, w in zip(columns, widths, strict=False)
        )
        print(line, file=stdout)


if __name__ == "__main__":
    sys.exit(main())
