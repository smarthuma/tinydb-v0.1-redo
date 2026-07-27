## Purpose

The Database capability (`tinydb/database.py`) is the public entry point for tinydb. It wraps the `Executor.open()` lifecycle (path / file handle / WAL reliable close), exposes `Database.execute(sql: str) -> list[dict]` as the main interface, and provides `Database.transaction()` as a context manager that auto-BEGINs on enter and COMMITs (no exception) or ROLLBACKs (on exception) on exit. `tinydb/__init__.py` re-exports `Database`, `TinyDBError`, and all exception subclasses, with `__all__`. This closes REWRITE-PENDING 3.8, 4.1, 4.2, 4.3, 4.6.

## ADDED Requirements

### Requirement: Database wraps the Executor lifecycle

`Database(path, page_size=4096, wal_path=None)` MUST open a single `.db` file (creating it if absent), allocate a header page on first create, and lazily construct the `Executor`, `FileStore`, `BufferPool`, and `WAL` objects. On `close()`, it MUST flush the WAL, flush all dirty buffer-pool pages, fsync, and close the file descriptor. `close()` MUST be idempotent (calling it twice MUST NOT raise).

#### Scenario: open and close a fresh database

- **WHEN** `db = Database(tmp_path / "a.db")` is constructed and then `db.close()` is called
- **THEN** the file `<path>.db` exists on disk with a valid header page, and no file descriptor is leaked.

#### Scenario: close is idempotent

- **WHEN** `db.close()` is called twice in a row
- **THEN** the second call completes without raising and the database remains closed.

### Requirement: Database.execute is the main SQL interface

`Database.execute(sql: str) -> list[dict]` MUST parse the SQL string, execute it through the executor, and return a normalized result:

- For `SELECT` (and `SELECT *`): a list of dicts, one per row, with column names as keys. An empty result returns `[]`.
- For `INSERT` / `UPDATE` / `DELETE`: `[{"rows_affected": n}]` where `n` is the number of rows modified.
- For `CREATE TABLE` / `DROP TABLE` / `CHECKPOINT`: `[{"status": "ok"}]`.
- For `BEGIN` / `COMMIT` / `ROLLBACK`: `[{"status": "ok"}]`.

`execute` MUST raise the appropriate `TinyDBError` subclass on failure; it MUST NOT swallow exceptions.

#### Scenario: SELECT returns list of dicts

- **WHEN** a table has rows `(1, 'alice')` and `(2, 'bob')` and `db.execute("SELECT id, name FROM t ORDER BY id;")` runs
- **THEN** the result is `[{"id": 1, "name": "alice"}, {"id": 2, "name": "bob"}]`.

#### Scenario: INSERT returns rows_affected

- **WHEN** `db.execute("INSERT INTO t VALUES (1, 'alice');")` runs on an empty table
- **THEN** the result is `[{"rows_affected": 1}]`.

#### Scenario: SELECT with no rows returns empty list

- **WHEN** `db.execute("SELECT * FROM t;")` runs on an empty table
- **THEN** the result is `[]`.

#### Scenario: error is raised, not swallowed

- **WHEN** `db.execute("SELECT * FROM nonexistent;")` runs
- **THEN** `TableNotFound` is raised and not caught inside `execute`.

### Requirement: Database.transaction() is a context manager

`Database.transaction()` MUST return a context manager that:

- On `__enter__`: executes `BEGIN` and returns `self` (so the user can call `db.execute(...)` inside the block).
- On `__exit__` with no exception: executes `COMMIT`.
- On `__exit__` with an exception: executes `ROLLBACK` and re-raises the original exception.

Nested `transaction()` calls MUST raise `TransactionAlreadyActive` (delegating to the underlying single-connection constraint).

#### Scenario: successful block auto-commits

- **WHEN** the user runs:
  ```python
  with db.transaction():
      db.execute("INSERT INTO t VALUES (1);")
  ```
- **THEN** after the block, a subsequent `db.execute("SELECT count(*) FROM t;")` returns the inserted row, even after `db.close()` and reopen.

#### Scenario: exception in block auto-rolls-back

- **WHEN** the user runs:
  ```python
  with db.transaction():
      db.execute("INSERT INTO t VALUES (1);")
      raise RuntimeError("boom")
  ```
- **THEN** the `RuntimeError` propagates out, the insert is rolled back, and a subsequent `SELECT count(*)` returns 0.

#### Scenario: nested transaction raises

- **WHEN** the user calls `with db.transaction(): with db.transaction(): ...`
- **THEN** the inner `__enter__` raises `TransactionAlreadyActive` and the outer transaction is unaffected.

### Requirement: Database is a context manager itself

The `Database` class MUST support the context manager protocol: `Database.__enter__` returns `self` and `Database.__exit__` calls `close()`. This allows `with Database(path) as db:`.

#### Scenario: with-statement closes on exit

- **WHEN** `with Database(path) as db: db.execute("CREATE TABLE t (id INT);")` runs
- **THEN** after the block the file descriptor is closed and the data is durable.

### Requirement: tinydb/__init__.py re-exports the public API

`tinydb/__init__.py` MUST import and re-export `Database` (from `tinydb.database`), `TinyDBError`, and all exception subclasses (`ParseError`, `TypeMismatch`, `UniqueViolation`, `NotNullViolation`, `TableNotFound`, `UnsafeDeleteWithoutWhere`, `IntegerOverflow`, `TransactionAlreadyActive`, `PageCorrupt`, `TransactionLogCorrupt`). It MUST declare `__all__` listing every re-exported name.

#### Scenario: top-level import works

- **WHEN** `from tinydb import Database, TinyDBError, TableNotFound` is executed
- **THEN** all three names are importable and `Database` is `tinydb.database.Database`.

#### Scenario: __all__ is complete

- **WHEN** `import tinydb; names = set(tinydb.__all__)` is executed
- **THEN** `names` contains `Database`, `TinyDBError`, and every exception subclass listed above.

### Requirement: Reliable close on exception paths

If an exception occurs during `Database.__init__` (e.g., the file cannot be opened), any partially-allocated resources (file handles, WAL handles) MUST be released. If an exception occurs during `execute`, the database MUST remain usable (no leaked file descriptors).

#### Scenario: init failure releases resources

- **WHEN** `Database("/nonexistent/path/to/db.db")` is constructed and the OS raises `FileNotFoundError`
- **THEN** no file descriptor is leaked and the exception propagates to the caller.

#### Scenario: execute failure keeps db usable

- **WHEN** `db.execute("BAD SQL;")` raises `ParseError`
- **THEN** a subsequent `db.execute("CREATE TABLE t (id INT);")` succeeds.
