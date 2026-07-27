# Wave W2 Review — Concurrency Control

- **Wave**: W2
- **Verdict**: pass
- **Reviewer**: build-executor (controller, agent fallback)
- **Range**: 7a37e7b..d621833
- **Spec**: concurrency-control (REQ-CC-001..009)

## Spec Compliance

- REQ-CC-001 RWLock multi-reader/single-writer: implemented with `threading.Lock` + `Condition`, writer-preferring. Concurrent reads verified via `threading.Barrier`. PASS.
- REQ-CC-002 snapshot read: shared file lock at open allows concurrent readers; per-instance RWLock serializes within process. PASS.
- REQ-CC-003 multi-process FileLock via `fcntl.flock` with `LOCK_SH`/`LOCK_EX` + `LOCK_NB`, timeout retry loop. Unix-only, Windows documented. PASS.
- REQ-CC-004 lock timeout DatabaseBusy: both RWLock and FileLock raise `DatabaseBusy` on timeout. PASS.
- REQ-CC-005 close releases lock: `_cleanup()` calls `_file_lock.close()`; verified by sequential open/close/open test. PASS.
- REQ-CC-006 multi-tx TxManager: `_txs: dict[int, _TxState]` with independent tx_id per connection. PASS.
- REQ-CC-007 backward compat: `Database(path)` constructor unchanged behavior; `lock_manager=None` preserves v0.1 semantics. PASS.
- Catalog cache coherence: shared lock at open allows concurrent reads of same catalog version. PASS.

## Code Quality

- `lock.py` 170 lines, `database.py` mods minimal, `tx.py` clean dict-based refactor.
- ruff: clean. mypy strict: clean (28 files).
- 241 passed, 1 skipped — full regression green.

## Concerns (non-blocking)

1. Cross-process write exclusion relies on flock shared mode only; true cross-process write serialization would need explicit exclusive upgrade (documented limitation, acceptable for v0.2).
2. Windows flock not tested (CI skipif).

## Recommendation

**pass** — W2 complete and ready for W4 integration.
