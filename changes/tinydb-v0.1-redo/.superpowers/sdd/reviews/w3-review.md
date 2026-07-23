# W3 Wave Review — Storage Engine + WAL + Transaction Manager

> Reviewer: self-review against spec-superflow:code-reviewer checklist
> Date: 2026-07-23
> Wave: W3 (Batch 3+4 — storage-engine + transaction-manager)
> Verdict: **pass**

## 1. 模块结构 (Module Structure)

- `tinydb/storage.py`：`Page`/`PageType`/`FileStore`/`BufferPool`/`PageHandle` + `alloc_page`/`free_page`/`fsync`，职责单一（页式持久化 + 缓冲池）。
- `tinydb/wal.py`：`WalRecord`/`RecordKind`/`Wal` + `encode_record`/`decode_record`/`replay_wal`，WAL 格式与 replay 逻辑内聚。
- `tinydb/tx.py`：`TxManager` 状态机，单文件模块。
- 依赖方向：`tx → wal`，`storage` 对 `wal` 仅延迟导入（`_maybe_replay_wal`），无循环依赖。

**Finding:** 无。

## 2. 命名与注释 (Naming & Comments)

- 常量命名清晰：`FILE_HEADER_SIZE`、`MAGIC`、`MUTATE`/`TX_COMMIT`/`TX_ROLLBACK`。
- 函数命名一致：`alloc_page`/`free_page`、`read_page`/`write_page`、`begin`/`commit`/`rollback`/`checkpoint`。
- 模块顶部 docstring 标注 REQ 编号。

**Finding:** 无。

## 3. 抽象粒度 (Abstraction Granularity)

- `PageHandle` 封装 pin/unpin/dirty 状态，避免调用方直接操作 `_PoolEntry`。
- `_ReplayStore` Protocol 仅用于 `replay_wal` 的类型标注，不引入运行时开销。
- `_FlushCapable` Protocol 用于 `TxManager.checkpoint` 对 `store` 的类型收窄。
- 未提前创建 helper/base class。

**Finding:** 无。

## 4. 错误路径 (Error Paths)

- `FileStore.open` 校验魔数、page_size 范围、page_size 匹配，失败抛明确异常。
- `decode_record` 校验 magic、长度、CRC32，失败抛 `TransactionLogCorrupt`。
- `TxManager.begin` 拒绝重复 BEGIN，抛 `TransactionAlreadyActive`。
- `BufferPool._evict_if_full` 在全部页 pinned 时抛 `RuntimeError`（不可恢复，符合预期）。
- `alloc_page`/`free_page` 通过 WAL 的 before/after-image 支持 undo。

**Finding:** 无静默吞错。

## 5. 与 D1..D10 对账 (Design Compliance)

- D4（WAL 格式）：magic + length + crc32 + body + crc32，before/after-image 支持 undo/redo。✅
- REQ-SE-007 / REWRITE-PENDING 3.1：`FileStore.open` 检测 WAL 并 replay。✅
- REWRITE-PENDING 3.3：`CHECKPOINT` 实现（flush + truncate）。✅
- 单文件持久化（REQ-SE-002）：仅 `.db` + 可选 `.db-wal`。✅

**Finding:** 无设计偏离。

## 6. 复杂度与重复 (Complexity & Duplication)

- `iter_records` 与 `_scan_records` 合并（`_scan_records` 直接 `yield from iter_records()`），消除重复扫描逻辑。
- `replay_wal` 独立于 `Wal` 类，供 `FileStore.open` 直接调用，避免 `TxManager` 作为中间层。
- 页 body 用 `body_len` 字段（u16）精确还原逻辑内容，避免填充字节污染。

**Finding:** 无重复。

## 7. 测试覆盖 (Test Coverage)

- `test_storage.py`：16 passed + 1 skipped（replay 端到端在 Batch 4 启用后已 pass）。覆盖 header round-trip、open/close、LRU 驱逐、pinned 不驱逐、脏页写回、alloc/free 复用、fsync 持久化、close/reopen 一致性。
- `test_wal.py`：10 passed。覆盖 record round-trip（MUTATE/COMMIT/ROLLBACK）、CRC 损坏检测、append 顺序、fsync 持久化、replay redo/undo、truncate。
- `test_tx.py`：7 passed。覆盖 BEGIN、嵌套 BEGIN 拒绝、COMMIT 持久化、ROLLBACK undo、CHECKPOINT 截断、无事务 CHECKPOINT 安全。
- 门禁：34 passed ✅ · ruff 零错误 ✅ · mypy strict 零错误 ✅。

**Finding:** 无覆盖盲区。

## 8. 已知限制

- `TxManager` 当前仅支持单连接单事务（符合项目边界，不引入并发语义）。
- WAL replay 在 `FileStore.open` 时执行，未暴露为独立公共 API（由 `database-api` 层在 Batch 9 封装）。
- `BufferPool` 驱逐策略为 LRU（dict 插入顺序），未实现时钟算法（v0.1 范围足够）。
