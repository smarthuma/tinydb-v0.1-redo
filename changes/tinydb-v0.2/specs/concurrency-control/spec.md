## Purpose

The Concurrency Control capability makes TinyDB safe to use from multiple threads and multiple processes. In v0.1-redo the `TxManager` is single-connection with no locking; this capability adds a connection-level read/write lock, snapshot reads for concurrent readers, and a cross-process file lock. It is ADDED in v0.2 and modifies `TxManager`, `Database`, and adds a new `lock.py` module.

## ADDED Requirements

### Requirement: connection-level read/write lock

Each `Database` instance MUST hold a connection-level lock that allows multiple concurrent readers OR a single writer. Read operations (SELECT) acquire the read lock; write operations (INSERT/UPDATE/DELETE/CREATE/DROP) acquire the write lock. The lock MUST be implemented using `threading.RLock` and `threading.Condition` or a dedicated `RWLock` class in `tinydb/lock.py`.

#### scenario: concurrent reads succeed

- **WHEN** two threads each open a `Database` on the same path and both execute SELECT
- **THEN** both reads proceed concurrently without blocking each other.

#### scenario: write blocks other readers and writers

- **WHEN** one thread holds the write lock (executing INSERT) and another thread attempts a SELECT or INSERT
- **THEN** the second thread blocks until the write lock is released.

### Requirement: snapshot read

A read connection MUST observe a consistent snapshot of the database at the time the read lock is acquired. Writes committed during the read transaction MUST NOT be visible to the in-progress read. The snapshot is defined by the buffer pool state and catalog version at lock-acquire time.

#### scenario: read sees snapshot, not concurrent write

- **WHEN** connection A begins a read (acquires read lock), then connection B inserts a row and commits, then connection A re-scans the same table
- **THEN** connection A does NOT see connection B's new row (snapshot isolation at the read level).

### Requirement: multi-process file lock

When opening a database, `Database` MUST acquire an advisory file lock on the `.db` file (Unix: `fcntl.flock`; Windows: documented fallback). An exclusive file lock is held while any writer connection is active; a shared file lock is held while only readers are active. A second process that cannot acquire the lock MUST raise `DatabaseBusy` after a configurable timeout.

#### scenario: second process blocked by writer

- **WHEN** process A opens the database with an active write transaction and process B attempts to open the same database
- **THEN** process B blocks until process A's write completes or the timeout elapses, then either succeeds or raises `DatabaseBusy`.

#### scenario: two reader processes coexist

- **WHEN** process A and process B both open the database in read-only mode
- **THEN** both hold a shared file lock and proceed concurrently.

### Requirement: lock timeout

A connection that cannot acquire the requested lock within a configurable timeout (default 5 seconds, configurable via `Database(path, lock_timeout=5.0)`) MUST raise `DatabaseBusy` with a message indicating which connection holds the lock. The timeout MUST be respected for both thread-level and file-level locks.

#### scenario: timeout raises DatabaseBusy

- **WHEN** connection A holds the write lock and connection B (with `lock_timeout=1.0`) attempts a write
- **THEN** after 1 second, connection B raises `DatabaseBusy`.

### Requirement: lock release on close

When `Database.close()` is called, ALL locks held by that connection (thread-level read/write lock, file-level lock) MUST be released reliably, even if an exception occurred during a query. The `Database` context manager (`with Database(...) as db:`) MUST guarantee lock release on `__exit__`.

#### scenario: close releases file lock for next process

- **WHEN** process A opens the database, acquires the file lock, then calls `db.close()`
- **THEN** the file lock is released and process B can subsequently open the database.

### Requirement: multi-transaction TxManager

The `TxManager` MUST support multiple concurrent transaction IDs (one per connection) rather than the v0.1 single `_tx` slot. Each connection's `BEGIN` returns a unique `tx_id`; `COMMIT`/`ROLLBACK` operate on that `tx_id`. The file-level single-writer invariant is preserved by the write lock (only one writer at a time), but the manager no longer raises `TransactionAlreadyActive` when a *different* connection begins a transaction.

#### scenario: two connections each begin independent transactions

- **WHEN** connection A calls `BEGIN` (returns tx_id=1) and connection B calls `BEGIN` (returns tx_id=2)
- **THEN** both transactions are active; connection A's `COMMIT` on tx_id=1 does not affect connection B's tx_id=2.

#### scenario: same connection nested begin still raises

- **WHEN** a single connection calls `BEGIN` twice without committing
- **THEN** `TransactionAlreadyActive` is raised (nested transactions are not supported).

### Requirement: catalog cache coherence

When a write connection commits a DDL change (CREATE/DROP TABLE, index change), the catalog cache MUST be invalidated so that subsequent reads by other connections see the updated schema. Read connections that began before the DDL MUST continue to see their snapshot's schema (no retroactive invalidation).

#### scenario: new table visible to readers after commit

- **WHEN** connection A creates table `foo` and commits, then connection B (which began after the commit) runs `.tables`
- **THEN** connection B sees `foo`.

#### scenario: pre-DDL reader retains old schema

- **WHEN** connection B began a read snapshot before connection A created `foo`
- **THEN** connection B's snapshot does NOT include `foo` (snapshot isolation).

## MODIFIED Requirements

### Requirement: Database constructor (modified)

The `Database.__init__` MUST retain its existing signature `(path, page_size=4096, wal_path=None)` and ADD optional parameters `lock_timeout: float = 5.0` and `readonly: bool = False`. Existing callers that omit these parameters MUST behave identically to v0.1.

#### scenario: existing constructor call unchanged

- **WHEN** calling `Database("test.db")` as in v0.1
- **THEN** the database opens with default lock_timeout=5.0 and readonly=False, identical to v0.1 behavior.

#### scenario: readonly connection acquires shared lock

- **WHEN** calling `Database("test.db", readonly=True)`
- **THEN** the connection acquires a shared file lock and refuses write operations with a read-only error.

### Requirement: TxManager constructor (modified)

`TxManager.__init__` MUST accept an optional `lock_manager` parameter. When provided, `begin`/`commit`/`checkpoint` coordinate with the lock manager. When `None` (default), behavior is identical to v0.1 (single-connection, no external locking), preserving backward compatibility.

#### scenario: TxManager without lock manager behaves as v0.1

- **WHEN** constructing `TxManager(store, wal)` without a lock manager
- **THEN** the manager functions exactly as in v0.1-redo (single transaction slot, no external locks).
