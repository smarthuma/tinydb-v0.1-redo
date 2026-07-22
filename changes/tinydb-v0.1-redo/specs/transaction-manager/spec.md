## Purpose

The Transaction Manager capability provides ACID guarantees via a write-ahead log (WAL). It owns BEGIN/COMMIT/ROLLBACK semantics, WAL flush ordering, CHECKPOINT truncation, and crash recovery on database open. In v0.1-redo it closes REWRITE-PENDING 3.1 (Wal.replay wired into FileStore.open) and 3.3 (CHECKPOINT SQL).

## ADDED Requirements

### Requirement: BEGIN opens a transaction

The executor MUST support an explicit `BEGIN` (or `BEGIN TRANSACTION`) statement that opens a new transaction on the current connection. Auto-commit mode is the default; inside a transaction, writes MUST be buffered until COMMIT or ROLLBACK.

#### Scenario: BEGIN succeeds and subsequent writes are buffered

- **WHEN** `BEGIN; INSERT INTO t VALUES (1);` runs and no COMMIT has been issued
- **THEN** the row is visible to the current transaction but NOT visible to a fresh transaction opened on the same database.

### Requirement: COMMIT persists writes durably

On `COMMIT`, all writes performed within the transaction MUST become visible to subsequent transactions AND MUST survive a power loss after the call returns.

#### Scenario: COMMIT makes writes visible

- **WHEN** `BEGIN; INSERT INTO t VALUES (1); COMMIT;` runs
- **THEN** a subsequent `SELECT * FROM t;` returns the row, even after reopening the database file.

### Requirement: ROLLBACK discards uncommitted writes

On `ROLLBACK`, all writes performed within the transaction MUST be discarded and MUST NOT become visible to any subsequent transaction.

#### Scenario: ROLLBACK removes buffered writes

- **WHEN** `BEGIN; INSERT INTO t VALUES (1); ROLLBACK;` runs
- **THEN** a subsequent `SELECT * FROM t;` returns zero rows and no disk state from the discarded write remains.

### Requirement: Write-Ahead Log records before- and after-images

Every page mutation MUST be preceded by a WAL record that includes enough information to undo (before-image) and redo (after-image) the change. The WAL record MUST be flushed to disk before the modified page is written back.

#### Scenario: WAL flushed before page write

- **WHEN** a transaction modifies page P and then commits
- **THEN** the on-disk WAL contains the corresponding record at an earlier position than the new contents of P.

### Requirement: Recovery on open replays committed transactions

On database open, if a WAL exists, the engine MUST replay it: undo uncommitted transactions and redo committed ones, so the final on-disk state equals "all committed transactions applied, none else". This MUST be invoked from `FileStore.open` (REWRITE-PENDING 3.1).

#### Scenario: crash recovery replays WAL

- **WHEN** the process is killed between WAL flush and page flush and the file is then reopened
- **THEN** the resulting table state equals the state that would have been observed had the process completed all committed transactions and no others.

#### Scenario: kill -9 between WAL flush and page flush is recovered

- **WHEN** a subprocess performs `BEGIN; INSERT;` (WAL flushed), then is killed via `SIGKILL` before the page flush, and the file is reopened
- **THEN** the inserted row is present after reopen (committed) or absent (rolled back), never half-written.

### Requirement: Single-connection transaction serialization

The engine MUST support exactly one active transaction at a time per database file. Attempting to BEGIN while a transaction is already open MUST raise `TransactionAlreadyActive`.

#### Scenario: nested BEGIN is rejected

- **WHEN** `BEGIN; BEGIN;` runs
- **THEN** the second `BEGIN` raises `TransactionAlreadyActive` and the first transaction is unaffected.

### Requirement: BEGIN, COMMIT, ROLLBACK are first-class SQL statements

The parser MUST accept `BEGIN`, `BEGIN TRANSACTION`, `COMMIT`, `END`, and `ROLLBACK` as transaction-control statements, and the executor MUST route them to the transaction manager rather than treating them as table operations.

#### Scenario: COMMIT is not parsed as a table name

- **WHEN** the parser receives `COMMIT;`
- **THEN** it produces a `Commit` AST node and does not raise a parse error for missing table.

### Requirement: CHECKPOINT truncates the WAL

The executor MUST support a `CHECKPOINT` statement that flushes all dirty pages to the `.db` file and then truncates the WAL to zero length. After a successful CHECKPOINT, a subsequent open MUST NOT replay any WAL records (because the WAL is empty). This closes REWRITE-PENDING 3.3.

#### Scenario: CHECKPOINT truncates WAL after flush

- **WHEN** `BEGIN; INSERT INTO t VALUES (1); COMMIT; CHECKPOINT;` runs
- **THEN** the WAL file size is 0 (or the WAL file is removed) and the row is still present after reopening the database.

#### Scenario: CHECKPOINT without an open transaction is safe

- **WHEN** `CHECKPOINT;` is executed with no open transaction
- **THEN** it flushes all dirty pages and truncates the WAL without error.
