## Purpose

The Query Executor capability executes parsed SQL ASTs against the storage engine, indexes, type system, and transaction manager. It owns DDL/DML execution, WHERE / ORDER BY / LIMIT / OFFSET pipelines, aggregation, CHECKPOINT, and the index-or-scan decision. In v0.1-redo it is split into `tinydb/executor/` submodules (REWRITE-PENDING 2.1), with heap/row concerns moved to `heap.py` / `row_layout.py` (2.2) and catalog codec moved to `catalog_codec.py` (2.4). It also closes REWRITE-PENDING 3.4 (index path), 3.5 (SELECT *), and 3.9 (`__all__`).

## ADDED Requirements

### Requirement: CREATE TABLE creates catalog and first data page

The executor MUST create a catalog entry (mapping table name to schema) and allocate the first data page on `CREATE TABLE`.

#### Scenario: catalog lists the new table

- **WHEN** `CREATE TABLE users (id INT PRIMARY KEY, name TEXT);` is executed
- **THEN** an internal catalog query (or `SHOW TABLES`) lists `users` and the stored schema is `[(id, INT, PK), (name, TEXT)]`.

### Requirement: DROP TABLE removes catalog and pages

The executor MUST remove the catalog entry and free all data and index pages owned by the table on `DROP TABLE`.

#### Scenario: dropped table is gone

- **WHEN** `DROP TABLE users;` runs after `users` exists
- **THEN** `SELECT * FROM users;` raises `TableNotFound` and the catalog no longer lists `users`.

### Requirement: INSERT validates types and constraints

The executor MUST validate each inserted value against the column's declared type and constraints, persisting the row only if all checks pass.

#### Scenario: type mismatch rejected

- **WHEN** column `age` is declared `INT` and the inserted value is the string `'alice'`
- **THEN** the executor raises `TypeMismatch(column='age', expected='INT', got='TEXT')` and the row is NOT inserted.

#### Scenario: NOT NULL violation rejected

- **WHEN** column `name` is declared `NOT NULL` and the inserted value is `NULL`
- **THEN** the executor raises `NotNullViolation(column='name')` and the row is NOT inserted.

#### Scenario: PRIMARY KEY uniqueness enforced

- **WHEN** a row with `id=1` already exists and another row with `id=1` is inserted
- **THEN** the executor raises `UniqueViolation(constraint='PRIMARY KEY', key=(1,))`.

### Requirement: SELECT returns rows in storage order by default

Without `ORDER BY`, the executor MUST return rows in the storage order of the table heap (typically the order in which rows were inserted).

#### Scenario: unindexed SELECT preserves heap order

- **WHEN** rows R1, R2, R3 are inserted in that order and `SELECT * FROM t;` runs without WHERE or ORDER BY
- **THEN** the result order is R1, R2, R3.

### Requirement: SELECT * expands to full column list

When the parser produces a `Star()` projection, the executor MUST expand it to the table's full column list using the catalog schema before evaluating the SELECT. This closes REWRITE-PENDING 3.5.

#### Scenario: SELECT * returns all columns

- **WHEN** the table `users` has columns `(id, name, age)` and `SELECT * FROM users;` runs
- **THEN** the result rows contain values for `id`, `name`, and `age` in schema order.

### Requirement: WHERE filter

The executor MUST evaluate the predicate tree against each candidate row and return only matching rows.

#### Scenario: compound predicate

- **WHEN** rows have `(age, name)` values `(15, A), (20, B), (25, C)` and the query is `SELECT * FROM t WHERE age >= 18 AND name = 'B';`
- **THEN** only the row `(20, B)` is returned.

### Requirement: UPDATE and DELETE apply WHERE

The executor MUST apply the WHERE clause to UPDATE and DELETE just like SELECT, mutating only matching rows.

#### Scenario: UPDATE modifies only matching rows

- **WHEN** rows are `(1, A), (2, B), (3, A)` and `UPDATE t SET name='X' WHERE name='A';` runs
- **THEN** the table becomes `(1, X), (2, B), (3, X)` and the change count returned is 2.

#### Scenario: DELETE without WHERE is rejected

- **WHEN** `DELETE FROM t;` runs without WHERE
- **THEN** the executor raises `UnsafeDeleteWithoutWhere()` and zero rows are removed.

### Requirement: ORDER BY sorts the result set

The executor MUST support `ORDER BY <col> [ASC|DESC]` on a single column. The default direction MUST be `ASC`.

#### Scenario: ORDER BY DESC reorders result

- **WHEN** rows have `id` values `1, 3, 2` and the query is `SELECT * FROM t ORDER BY id DESC;`
- **THEN** the result order is `3, 2, 1`.

### Requirement: LIMIT and OFFSET paginate

The executor MUST support `LIMIT <n>` (max rows returned) and `OFFSET <k>` (skip first k rows). `LIMIT 0` MUST return zero rows.

#### Scenario: LIMIT/OFFSET pagination

- **WHEN** rows have `id` values `1..10` and the query is `SELECT * FROM t ORDER BY id LIMIT 3 OFFSET 2;`
- **THEN** rows `3, 4, 5` are returned in that order.

### Requirement: Aggregate COUNT, SUM, AVG with optional GROUP BY

The executor MUST compute `COUNT`, `SUM`, and `AVG` over the filtered rows. With `GROUP BY`, each distinct group MUST produce exactly one output row.

#### Scenario: COUNT(*) without GROUP BY

- **WHEN** 7 rows exist in the table and `SELECT COUNT(*) FROM t;` runs
- **THEN** the result is a single row containing the value 7.

#### Scenario: GROUP BY with SUM

- **WHEN** rows are `[(A, 1), (B, 2), (A, 3)]` and `SELECT dept, SUM(amount) FROM t GROUP BY dept;` runs
- **THEN** the result is `[(A, 4), (B, 2)]` in deterministic order (by group key).

### Requirement: Use index when available

If a B-tree index exists on the WHERE column(s), the executor MUST use it for equality and range predicates; otherwise it MUST fall back to a full table scan. This closes REWRITE-PENDING 3.4.

#### Scenario: indexed equality uses index

- **WHEN** an index on `users.id` exists and the query is `SELECT * FROM users WHERE id = 42;`
- **THEN** the executor performs an index seek and reads at most one heap row, not a full scan.

#### Scenario: unindexed column falls back to scan

- **WHEN** no index exists on `users.email` and the query is `SELECT * FROM users WHERE email = 'a@b';`
- **THEN** the executor performs a full table scan and returns the correct rows.

### Requirement: CHECKPOINT flushes and truncates WAL

The executor MUST route the `Checkpoint` AST to the transaction manager, which flushes all dirty pages and truncates the WAL. See REQ-TM-008 for the transaction-level contract.

#### Scenario: CHECKPOINT is wired end-to-end

- **WHEN** `CHECKPOINT;` is executed after a committed transaction
- **THEN** the WAL file is empty afterwards and the data is still present after reopen.

### Requirement: Schema mutation uses dataclass.replace

When the executor needs to update a frozen schema or catalog entry, it MUST use `dataclasses.replace(...)` or an equivalent copy-and-update; it MUST NOT use `object.__setattr__(...)` to bypass immutability. This closes REWRITE-PENDING 2.9.

#### Scenario: catalog flush does not mutate in place

- **WHEN** the executor updates the catalog after `CREATE TABLE`
- **THEN** the original schema/catalog dataclass instance is unchanged and a new instance is stored.

### Requirement: Public API carries __all__

Every public module in `tinydb/` (including each `executor/` submodule) MUST declare `__all__` listing its public names. This closes REWRITE-PENDING 3.9.

#### Scenario: executor submodules export only public names

- **WHING** `from tinydb.executor.dml import *` is executed
- **THEN** only names listed in `tinydb/executor/dml.py`'s `__all__` are imported.
