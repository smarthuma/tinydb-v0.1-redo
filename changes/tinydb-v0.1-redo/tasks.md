# 实现任务：tinydb v0.1-redo

## 文件结构（File Structure）

仓库根：`/home/wfj/新建文件夹/开发tinydb-重置版/`。下表列出全部新建（Create）文件；本次变更不修改任何既有文件（仓库根除 `changes/` 外无 Python 源码）。

| 路径 | 职责 | 状态 |
|---|---|---|
| `pyproject.toml` | 包元数据、pytest / ruff / mypy 配置、Python ≥3.10、`fail_under=80` | Create |
| `.gitignore` | 忽略 `*.db` / `*.db-wal` / `*.pyc` / `__pycache__/` / `.coverage` / `htmlcov/` / `.pytest_cache/` | Create |
| `README.md` | 快速开始、REPL 用法、范围、Database API 示例、设计指针 | Create |
| `docs/architecture.md` | 层映射 + spec→模块交叉引用 + 文件树（与实现一致） | Create |
| `docs/roadmap.md` | v0.2 延期项唯一真值源（链接自 CHANGELOG / architecture） | Create |
| `tinydb/__init__.py` | 重导出 `Database`、`TinyDBError` 及全部异常子类，`__all__` | Create |
| `tinydb/errors.py` | `format(exc) -> str` 单一错误格式化入口 + 异常子类集中定义 | Create |
| `tinydb/types.py` | `ColumnType` 枚举 + INT/FLOAT/TEXT/BOOL 编解码 + 强制规则 + `__all__` | Create |
| `tinydb/storage.py` | `Page`、`FileStore`（含 WAL replay 接入）、`BufferPool` LRU、`__all__` | Create |
| `tinydb/heap.py` | `Heap`：行追加 / 扫描 / 删除 / 原地更新（从 executor 拆出） | Create |
| `tinydb/row_layout.py` | `_encode_row` / `_decode_row`：行二进制布局（从 executor 拆出） | Create |
| `tinydb/catalog_codec.py` | `_pack_catalog` / `_unpack_catalog`：catalog 编解码（从 executor 拆出） | Create |
| `tinydb/index.py` | `B+ Tree`：internal/leaf codec、seek/range、insert/split、delete/merge/redistribute、INT/TEXT 排序、`__all__` | Create |
| `tinydb/wal.py` | `WalRecord` 编解码、append、truncate、`replay(store, pool)`、`__all__` | Create |
| `tinydb/tx.py` | `TxManager`：BEGIN/COMMIT/ROLLBACK/CHECKPOINT 状态机、单连接序列化、`__all__` | Create |
| `tinydb/parser/__init__.py` | 公共 `parse(sql: str) -> Statement` 入口、`__all__` | Create |
| `tinydb/parser/ast.py` | 全部 SQL 节点的 frozen dataclass（含 `Star`、`Checkpoint`） | Create |
| `tinydb/parser/lexer.py` | `tokenize(sql: str) -> list[Token]`，带 (line, col) | Create |
| `tinydb/parser/ddl_parser.py` | `_parse_create_table`、`_parse_drop_table`、`_parse_checkpoint` | Create |
| `tinydb/parser/dml_parser.py` | `_parse_insert`、`_parse_select`、`_parse_update`、`_parse_delete` | Create |
| `tinydb/parser/predicate.py` | 谓词解析：AND/OR 优先级、BETWEEN/IN/IS NULL、聚合识别 | Create |
| `tinydb/parser/tx_control.py` | `_parse_begin`、`_parse_commit`、`_parse_rollback` | Create |
| `tinydb/executor/__init__.py` | `Executor` 主类：编排 catalog/heap/index/tx、`execute(stmt)`、`__all__` | Create |
| `tinydb/executor/catalog.py` | `Catalog`：create_table / drop_table / get_table / list_tables | Create |
| `tinydb/executor/ddl.py` | DDL 执行：CREATE TABLE / DROP TABLE / CHECKPOINT | Create |
| `tinydb/executor/dml.py` | DML 执行：INSERT / UPDATE / DELETE（含约束校验、安全 DELETE） | Create |
| `tinydb/executor/select.py` | SELECT 执行：投影（含 `Star` 展开）、WHERE 求值、ORDER BY、LIMIT/OFFSET | Create |
| `tinydb/executor/aggregate.py` | 聚合执行：COUNT / SUM / AVG + GROUP BY | Create |
| `tinydb/executor/index_plan.py` | `IndexPlanner`：index_seek vs heap_scan 决策、`IndexScan` 执行 | Create |
| `tinydb/executor/checkpoint.py` | CHECKPOINT 执行：flush dirty pages + truncate WAL | Create |
| `tinydb/database.py` | `Database` 类：生命周期封装、`execute()`、`transaction()` 上下文管理器、`__all__` | Create |
| `tinydb/cli.py` | `tinydb <file.db>` 入口：argparse、REPL 循环、dot-commands、stdin 批处理、`__all__` | Create |
| `tests/__init__.py` | 空包标记 | Create |
| `tests/unit/__init__.py` | 空包标记 | Create |
| `tests/unit/test_types.py` | REQ-TS-001..009 场景 | Create |
| `tests/unit/test_errors.py` | `errors.format` 单一入口 + 异常子类字段 | Create |
| `tests/unit/test_storage.py` | REQ-SE-001..007 场景（含 WAL replay 接入） | Create |
| `tests/unit/test_heap.py` | Heap 追加/扫描/删除/更新 + 行编解码 | Create |
| `tests/unit/test_row_layout.py` | `_encode_row` / `_decode_row` 边界 | Create |
| `tests/unit/test_catalog_codec.py` | catalog 编解码 round-trip | Create |
| `tests/unit/test_index.py` | REQ-BT-001..009 场景（含 merge/redistribute + 5k oracle） | Create |
| `tests/unit/test_wal.py` | WAL 记录编解码 + 损坏 checksum + replay | Create |
| `tests/unit/test_tx.py` | REQ-TM-001..008 场景 | Create |
| `tests/unit/test_parser_lexer.py` | REQ-SP-001 场景 | Create |
| `tests/unit/test_parser_ddl.py` | REQ-SP-002 + CHECKPOINT 解析 | Create |
| `tests/unit/test_parser_dml.py` | REQ-SP-003 + `SELECT *` 解析 | Create |
| `tests/unit/test_parser_predicate.py` | REQ-SP-004 + 聚合 + 错误位置 | Create |
| `tests/unit/test_parser_tx.py` | REQ-TM-007 场景 | Create |
| `tests/unit/test_executor_ddl.py` | REQ-QE-001,002 | Create |
| `tests/unit/test_executor_dml.py` | REQ-QE-003,004,005,006 | Create |
| `tests/unit/test_executor_select.py` | REQ-QE-007,008 + `SELECT *` 展开 | Create |
| `tests/unit/test_executor_aggregate.py` | REQ-QE-009 | Create |
| `tests/unit/test_executor_index.py` | REQ-QE-010（索引路径） | Create |
| `tests/unit/test_executor_checkpoint.py` | REQ-TM-008 / REQ-QE-011 | Create |
| `tests/unit/test_database.py` | database-api REQ-DB-001..006 场景 | Create |
| `tests/e2e/__init__.py` | 空包标记 | Create |
| `tests/e2e/test_cli_repl.py` | REQ-CR-001..007 场景 | Create |
| `tests/e2e/test_crash_recovery.py` | kill -9 后 reopen 一致性（REQ-TM-005 端到端） | Create |
| `tests/bench/__init__.py` | 空包标记 | Create |
| `tests/bench/test_10k_rows.py` | 10k 行 insert + 100 次索引查找性能基准（非阻塞，`@pytest.mark.bench`） | Create |

总计：68 个新建文件，0 修改既有文件。

## 接口（Interfaces）

跨 batch 契约。每个接口被依赖它的 batch 消费。

```text
# ---- types.py ----
tinydb.types.ColumnType (enum: INT, FLOAT, TEXT, BOOL)
tinydb.types.encode(value: object, column_type: ColumnType) -> bytes
tinydb.types.decode(raw: bytes, column_type: ColumnType) -> object
tinydb.types.coerce_in(value: object, column_type: ColumnType) -> object
tinydb.types.compare(a: object, b: object, column_type: ColumnType) -> int

# ---- errors.py ----
tinydb.errors.TinyDBError (base)
tinydb.errors.ParseError, TypeMismatch, UniqueViolation, NotNullViolation,
tinydb.errors.TableNotFound, UnsafeDeleteWithoutWhere, IntegerOverflow,
tinydb.errors.TransactionAlreadyActive, PageCorrupt, TransactionLogCorrupt
tinydb.errors.format(exc: BaseException) -> str

# ---- storage.py ----
tinydb.storage.Page (page_id: int, page_type: int, body: bytes, lsn: int)
tinydb.storage.PAGE_INT, PAGE_TABLE, PAGE_INDEX, PAGE_OVERFLOW (constants)
tinydb.storage.FileStore.open(path: str, page_size: int = 4096) -> FileStore
tinydb.storage.FileStore.alloc_page(page_type: int) -> int
tinydb.storage.FileStore.free_page(page_id: int) -> None
tinydb.storage.FileStore.read_page(page_id: int) -> Page
tinydb.storage.FileStore.write_page(page_id: int, page: Page) -> None
tinydb.storage.FileStore.fsync() -> None
tinydb.storage.FileStore.close() -> None
tinydb.storage.BufferPool(capacity: int = 128)
tinydb.storage.BufferPool.get(page_id: int) -> Page
tinydb.storage.BufferPool.put(page: Page) -> None
tinydb.storage.BufferPool.flush_all() -> None

# ---- heap.py / row_layout.py ----
tinydb.row_layout.encode_row(values: tuple, schema: Schema) -> bytes
tinydb.row_layout.decode_row(raw: bytes, schema: Schema) -> tuple
tinydb.heap.Heap(store: FileStore, pool: BufferPool, root_page_id: int, schema: Schema)
tinydb.heap.Heap.append(values: tuple) -> rowid: int
tinydb.heap.Heap.scan() -> Iterator[(rowid, tuple)]
tinydb.heap.Heap.update(rowid: int, values: tuple) -> None
tinydb.heap.Heap.delete(rowid: int) -> None

# ---- catalog_codec.py ----
tinydb.catalog_codec.encode_catalog(entries: list[TableMeta]) -> bytes
tinydb.catalog_codec.decode_catalog(raw: bytes) -> list[TableMeta]

# ---- index.py ----
tinydb.index.BPlusTree.create(store: FileStore, pool: BufferPool, key_type: ColumnType, order: int = 64) -> BPlusTree
tinydb.index.BPlusTree.seek(key: object) -> list[int]
tinydb.index.BPlusTree.range(lo: object, hi: object, inclusive: bool) -> list[int]
tinydb.index.BPlusTree.insert(key: object, rowid: int) -> None
tinydb.index.BPlusTree.delete(key: object, rowid: int) -> None

# ---- wal.py ----
tinydb.wal.Wal.open(path: str) -> Wal
tinydb.wal.Wal.append(record_type: str, payload: bytes) -> int  # returns lsn
tinydb.wal.Wal.fsync() -> None
tinydb.wal.Wal.truncate() -> None
tinydb.wal.Wal.replay(store: FileStore, pool: BufferPool) -> None
tinydb.wal.Wal.close() -> None

# ---- tx.py ----
tinydb.tx.TxManager(store: FileStore, pool: BufferPool, wal: Wal)
tinydb.tx.TxManager.begin() -> int  # returns tx_id
tinydb.tx.TxManager.commit(tx_id: int) -> None
tinydb.tx.TxManager.rollback(tx_id: int) -> None
tinydb.tx.TxManager.checkpoint() -> None

# ---- parser ----
tinydb.parser.parse(sql: str) -> Statement
tinydb.parser.lexer.tokenize(sql: str) -> list[Token]
tinydb.parser.ast.Statement = CreateTable | DropTable | Insert | Select | Update | Delete | Begin | Commit | Rollback | Checkpoint
tinydb.parser.ast.Star  # for SELECT *

# ---- executor ----
tinydb.executor.Executor(store: FileStore, pool: BufferPool, wal: Wal)
tinydb.executor.Executor.execute(stmt: Statement) -> Result
tinydb.executor.Result = RowSet(rows: list[tuple], columns: list[str]) | Count(n: int) | Ok()
tinydb.executor.catalog.Catalog(store, pool, codec)
tinydb.executor.index_plan.IndexPlan = IndexSeek(tree, key) | HeapScan(table)

# ---- database.py ----
tinydb.database.Database(path: str, page_size: int = 4096, wal_path: str | None = None)
tinydb.database.Database.execute(sql: str) -> list[dict]
tinydb.database.Database.transaction() -> TransactionContext
tinydb.database.Database.close() -> None

# ---- cli.py ----
tinydb.cli.main(argv: list[str], stdin: Readable, stdout: Writable, stderr: Writable) -> int
```

## 任务（Tasks）

按 Batch 1..12 组织。每个任务含精确文件路径、Interfaces 块、5 步 TDD 计划、显式 Depends on。每步 2–5 分钟。无占位符。

---

### Batch 1：项目骨架 + 仓库卫生（DP-0 落地）

#### T-1.1 pyproject.toml + .gitignore + 仓库根脚手架

- **Files**: `Create: pyproject.toml`, `Create: .gitignore`
- **Interfaces**:
  - Consumes: none
  - Produces: `pyproject.toml`（`name="tinydb"`, `requires-python=">=3.10"`, `[project.optional-dependencies] dev = ["pytest", "pytest-cov", "ruff", "mypy"]`, `[tool.pytest.ini_options] testpaths=["tests"]`, `[tool.ruff] target-version="py310" line-length=100 select=["E","F","W","I","B","UP"]`, `[tool.mypy] strict=true`）；`.gitignore`（含 `*.db`, `*.db-wal`, `*.db-shm`, `*.db-journal`, `.coverage`, `htmlcov/`, `.pytest_cache/`, `__pycache__/`, `*.pyc`）
- **Steps**:
  1. Red — `ls pyproject.toml .gitignore` 失败（文件不存在）。
  2. Green — 写入两个文件。
  3. Refactor — 确认 `.gitignore` 覆盖 5.1 要求。
  4. Verify — `pip install -e ".[dev]"` 成功；`pytest --collect-only` 找到 0 测试。
  5. Commit — `chore(B1): project skeleton + .gitignore (DP-0, REWRITE-PENDING 5.1,5.2,6.1,6.2)`。
- **Depends on**: none.

#### T-1.2 包目录 + 空 `__init__.py`

- **Files**: `Create: tinydb/__init__.py`（临时空文件，Batch 11 填充重导出）, `Create: tinydb/parser/__init__.py`（临时空）, `Create: tinydb/executor/__init__.py`（临时空）, `Create: tests/__init__.py`, `Create: tests/unit/__init__.py`, `Create: tests/e2e/__init__.py`, `Create: tests/bench/__init__.py`
- **Interfaces**:
  - Consumes: none
  - Produces: 包目录结构可被 pytest 发现
- **Steps**:
  1. Red — `pytest --collect-only` 失败（包不存在）。
  2. Green — 创建目录与空 `__init__.py`。
  3. Refactor — 无。
  4. Verify — `pytest --collect-only` 成功，0 测试。
  5. Commit — `chore(B1): package scaffold`。
- **Depends on**: T-1.1.

---

### Batch 2：Type System + errors.format（基础）

#### T-2.1 异常子类 + `errors.format`

- **Files**: `Create: tinydb/errors.py`, `Create: tests/unit/test_errors.py`
- **Interfaces**:
  - Consumes: none
  - Produces: `TinyDBError` 基类 + 10 个异常子类 + `format(exc) -> str`
- **Steps**:
  1. Red — `test_format_type_mismatch_contains_fields`、`test_format_parse_error_contains_position`、`test_base_catches_all`；均失败。
  2. Green — 实现异常类（带结构化字段）+ `format` 分派表。
  3. Refactor — 把异常类字段对齐 spec。
  4. Verify — 3 测试通过。
  5. Commit — `feat(B2): exception hierarchy + errors.format (REQ-TS-008,009 + REWRITE-PENDING 2.5)`。
- **Depends on**: T-1.2.

#### T-2.2 ColumnType + INT 编解码

- **Files**: `Create: tinydb/types.py`, `Create: tests/unit/test_types.py`
- **Interfaces**:
  - Consumes: none
  - Produces: `ColumnType` 枚举 + `encode_int` / `decode_int`
- **Steps**:
  1. Red — `test_int_roundtrip_negative`、`test_int_overflow_raises`；失败。
  2. Green — `int.to_bytes(8, 'little', signed=True)` + 溢出检查。
  3. Refactor — 提取 `_checked_i64`。
  4. Verify — 2 测试通过。
  5. Commit — `feat(B2): INT encode/decode + overflow (REQ-TS-001)`。
- **Depends on**: T-2.1.

#### T-2.3 FLOAT / TEXT / BOOL 编解码

- **Files**: `Modify: tinydb/types.py`, `Modify: tests/unit/test_types.py`
- **Interfaces**:
  - Consumes: `encode_int` / `decode_int`
  - Produces: `encode_float` / `decode_float`、`encode_text` / `decode_text`、`encode_bool` / `decode_bool`
- **Steps**:
  1. Red — round-trip 测试 `3.14`、`'你好, tinydb 🚀'`、`True`、`False`；失败。
  2. Green — float 用 `struct.pack('<d')`，text 用 `len u32 + utf-8`，bool 用单字节。
  3. Refactor — 统一为 `encode(value, column_type)` / `decode(raw, column_type)` 分派。
  4. Verify — 4 测试通过。
  5. Commit — `feat(B2): FLOAT/TEXT/BOOL encode/decode (REQ-TS-002,003,004)`。
- **Depends on**: T-2.2.

#### T-2.4 强制规则 + NULL + 比较语义 + `__all__`

- **Files**: `Modify: tinydb/types.py`, `Modify: tests/unit/test_types.py`
- **Interfaces**:
  - Consumes: 编解码分派
  - Produces: `coerce_in`、`None` round-trip、`compare`、`__all__`
- **Steps**:
  1. Red — `test_bool_to_int_coerces`、`test_int_into_text_rejected`、`test_null_roundtrip`、`test_null_excluded_from_where`；失败。
  2. Green — 实现 REQ-TS-005/006/007。
  3. Refactor — 在模块顶声明 `__all__`。
  4. Verify — 4 测试通过。
  5. Commit — `feat(B2): coerce_in + NULL + compare + __all__ (REQ-TS-005,006,007 + REWRITE-PENDING 3.9)`。
- **Depends on**: T-2.3.

---

### Batch 3：Storage Engine + WAL replay 接入

#### T-3.1 Page 头部编解码

- **Files**: `Create: tinydb/storage.py`, `Create: tests/unit/test_storage.py`
- **Interfaces**:
  - Consumes: none
  - Produces: `Page` dataclass + `_pack_header` / `_unpack_header` + 页类型常量
- **Steps**:
  1. Red — `test_page_header_roundtrip`；失败。
  2. Green — `struct.pack('<I B I', ...)`。
  3. Refactor — 命名常量 `HEADER_SIZE=9`。
  4. Verify — round-trip 通过。
  5. Commit — `feat(B3): page header codec (REQ-SE-003)`。
- **Depends on**: T-1.2.

#### T-3.2 FileStore open/close + 页读写

- **Files**: `Modify: tinydb/storage.py`, `Modify: tests/unit/test_storage.py`
- **Interfaces**:
  - Consumes: `Page`、头部编解码
  - Produces: `FileStore.open`、`read_page`、`write_page`、`close`
- **Steps**:
  1. Red — `test_open_creates_header_page`、`test_write_then_read_roundtrip`；失败。
  2. Green — open 分配首页（新文件），read/write 用 `os.pread`/`pwrite`。
  3. Refactor — fd 用小上下文管理器封装。
  4. Verify — 2 测试通过。
  5. Commit — `feat(B3): FileStore open/read/write (REQ-SE-001,002)`。
- **Depends on**: T-3.1.

#### T-3.3 BufferPool LRU

- **Files**: `Modify: tinydb/storage.py`, `Modify: tests/unit/test_storage.py`
- **Interfaces**:
  - Consumes: `FileStore`
  - Produces: `BufferPool(capacity)`、`.get(id)`、`.put(page)`、`.flush_all()`
- **Steps**:
  1. Red — `test_lru_evicts_unpinned`、`test_pinned_pages_never_evicted`、`test_dirty_pages_flushed_on_evict`；失败。
  2. Green — `OrderedDict` 实现 LRU；驱逐时写回脏页。
  3. Refactor — 提取 `_touch_lru`、`_is_dirty`。
  4. Verify — 3 测试通过 + 1000 页压力测试。
  5. Commit — `feat(B3): BufferPool LRU (REQ-SE-004)`。
- **Depends on**: T-3.2.

#### T-3.4 页分配/释放 + fsync

- **Files**: `Modify: tinydb/storage.py`, `Modify: tests/unit/test_storage.py`
- **Interfaces**:
  - Consumes: `FileStore`、`BufferPool`
  - Produces: `alloc_page(type)`、`free_page(id)`、`fsync()`
- **Steps**:
  1. Red — `test_alloc_returns_distinct_ids`、`test_free_then_alloc_reuses_id`、`test_fsync_persists`；失败。
  2. Green — 首页字节 9..12 存空闲链头（u32），LIFO 复用。
  3. Refactor — 无。
  4. Verify — 3 测试通过。
  5. Commit — `feat(B3): alloc/free/fsync (REQ-SE-005,006)`。
- **Depends on**: T-3.3.

#### T-3.5 WAL replay 接入 FileStore.open

- **Files**: `Modify: tinydb/storage.py`, `Modify: tests/unit/test_storage.py`
- **Interfaces**:
  - Consumes: `Wal.replay`（Batch 4 提供）
  - Produces: `FileStore.open` 在打开后调用 `Wal.replay(store, pool)` 当 `<path>-wal` 存在
- **Steps**:
  1. Red — `test_replay_runs_on_open_when_wal_exists`、`test_no_wal_is_noop`；失败。
  2. Green — 在 `FileStore.open` 末尾检测 WAL 文件并调用 replay。
  3. Refactor — 提取 `_maybe_replay_wal`。
  4. Verify — 2 测试通过。
  5. Commit — `feat(B3): wire Wal.replay into FileStore.open (REQ-SE-007 + REWRITE-PENDING 3.1)`。
- **Depends on**: T-3.2, T-4.3（Wal.replay 实现）。

---

### Batch 4：WAL + Transaction Manager

#### T-4.1 WAL 记录编解码

- **Files**: `Create: tinydb/wal.py`, `Create: tests/unit/test_wal.py`
- **Interfaces**:
  - Consumes: `FileStore`
  - Produces: `_WalRecord` + `encode(record) -> bytes` + `decode(raw) -> _WalRecord`
- **Steps**:
  1. Red — `test_record_roundtrip_mutation`、`test_record_roundtrip_commit`、`test_corrupted_checksum_raises`；失败。
  2. Green — 按 D4 实现 + CRC32 checksum。
  3. Refactor — 提取 `_pack_with_checksum`。
  4. Verify — 3 测试通过。
  5. Commit — `feat(B4): WAL record codec (Decision D4)`。
- **Depends on**: T-3.2.

#### T-4.2 WAL append + fsync

- **Files**: `Modify: tinydb/wal.py`, `Modify: tests/unit/test_wal.py`
- **Interfaces**:
  - Consumes: `_WalRecord`
  - Produces: `Wal.open(path)`、`append(record_type, payload) -> lsn`、`fsync()`、`close()`
- **Steps**:
  1. Red — `test_wal_appends_in_order`、`test_wal_fsync_persists`；失败。
  2. Green — 追加写 `<path>-wal`，`os.fsync`。
  3. Refactor — wal fd 用小上下文管理器封装。
  4. Verify — 2 测试通过。
  5. Commit — `feat(B4): WAL append + fsync (REQ-TM-004)`。
- **Depends on**: T-4.1.

#### T-4.3 WAL replay + truncate

- **Files**: `Modify: tinydb/wal.py`, `Modify: tests/unit/test_wal.py`
- **Interfaces**:
  - Consumes: `FileStore`、`BufferPool`
  - Produces: `Wal.replay(store, pool)`、`Wal.truncate()`
- **Steps**:
  1. Red — `test_replay_redoes_committed`、`test_replay_ignores_uncommitted`、`test_truncate_zeros_wal`；失败。
  2. Green — 前向扫描：收集 committed tx_id 集合，重放 committed 的 MUTATE。
  3. Refactor — 拆 `_scan_commits` / `_apply_mutation`。
  4. Verify — 3 测试通过。
  5. Commit — `feat(B4): WAL replay + truncate (REQ-TM-005)`。
- **Depends on**: T-4.2.

#### T-4.4 TxManager BEGIN/COMMIT/ROLLBACK/CHECKPOINT

- **Files**: `Create: tinydb/tx.py`, `Create: tests/unit/test_tx.py`
- **Interfaces**:
  - Consumes: `Wal`、`FileStore`、`BufferPool`
  - Produces: `TxManager(store, pool, wal)`、`begin() -> tx_id`、`commit(tx_id)`、`rollback(tx_id)`、`checkpoint()`
- **Steps**:
  1. Red — REQ-TM-001/002/003/006/008 场景；失败。
  2. Green — 单槽位 `_TxState`；COMMIT 先 fsync WAL 再刷页；CHECKPOINT 调 `pool.flush_all()` + `wal.truncate()`。
  3. Refactor — 引入 `_TxState` dataclass。
  4. Verify — 5 测试通过。
  5. Commit — `feat(B4): TxManager state machine + CHECKPOINT (REQ-TM-001,002,003,006,008 + REWRITE-PENDING 3.3)`。
- **Depends on**: T-4.3.

---

### Batch 5：Heap + Row Layout + Catalog Codec

#### T-5.1 行编解码

- **Files**: `Create: tinydb/row_layout.py`, `Create: tests/unit/test_row_layout.py`
- **Interfaces**:
  - Consumes: `types.encode` / `decode`
  - Produces: `encode_row(values, schema) -> bytes`、`decode_row(raw, schema) -> tuple`
- **Steps**:
  1. Red — `test_encode_decode_roundtrip_mixed_types`；失败。
  2. Green — `[len u32 | rowid u64 | values...]` 布局。
  3. Refactor — 提取 `_value_offsets(schema)`。
  4. Verify — round-trip 通过。
  5. Commit — `feat(B5): row encode/decode (REWRITE-PENDING 2.2)`。
- **Depends on**: T-2.4.

#### T-5.2 Heap 追加/扫描/删除/更新

- **Files**: `Create: tinydb/heap.py`, `Create: tests/unit/test_heap.py`
- **Interfaces**:
  - Consumes: `FileStore`、`BufferPool`、`row_layout`
  - Produces: `Heap(store, pool, root_page_id, schema)`、`append(values) -> rowid`、`scan() -> Iterator[(rowid, tuple)]`、`update(rowid, values)`、`delete(rowid)`
- **Steps**:
  1. Red — `test_append_and_scan_returns_rows_in_order`、`test_delete_removes_row`、`test_update_changes_row`；失败。
  2. Green — 单页或多页 TABLE 类型堆。
  3. Refactor — 提取 `_encode_row` / `_decode_row` 委托给 row_layout。
  4. Verify — 3 测试通过 + 10k 行扫描 < 1s。
  5. Commit — `feat(B5): Heap append/scan/delete/update (REQ-QE-004 + REWRITE-PENDING 2.2)`。
- **Depends on**: T-5.1, T-3.4.

#### T-5.3 Catalog 编解码

- **Files**: `Create: tinydb/catalog_codec.py`, `Create: tests/unit/test_catalog_codec.py`
- **Interfaces**:
  - Consumes: none
  - Produces: `encode_catalog(entries) -> bytes`、`decode_catalog(raw) -> list[TableMeta]`
- **Steps**:
  1. Red — `test_catalog_roundtrip_multiple_tables`；失败。
  2. Green — JSON 或紧凑二进制编码（字节格式与归档版兼容）。
  3. Refactor — 无。
  4. Verify — round-trip 通过。
  5. Commit — `feat(B5): catalog codec (REWRITE-PENDING 2.4)`。
- **Depends on**: T-2.4.

---

### Batch 6：B+ Tree Index（含 merge/redistribute）

#### T-6.1 Leaf 节点编解码

- **Files**: `Create: tinydb/index.py`, `Create: tests/unit/test_index.py`
- **Interfaces**:
  - Consumes: `types.encode` / `decode`
  - Produces: `_pack_leaf(keys, rowids) -> bytes`、`_unpack_leaf(raw) -> tuple`
- **Steps**:
  1. Red — `test_leaf_roundtrip_3_keys`；失败。
  2. Green — `len u16 + keys + rowids`。
  3. Refactor — 共享 `key_codec`。
  4. Verify — round-trip + 排序测试通过。
  5. Commit — `feat(B6): leaf node codec (REQ-BT-001)`。
- **Depends on**: T-2.3, T-3.4.

#### T-6.2 Internal 节点编解码 + 单叶 seek/range

- **Files**: `Modify: tinydb/index.py`, `Modify: tests/unit/test_index.py`
- **Interfaces**:
  - Consumes: leaf codec
  - Produces: internal codec、`BPlusTree.create`、`seek`、`range`
- **Steps**:
  1. Red — `test_seek_on_single_leaf`、`test_range_inclusive`；失败。
  2. Green — internal `[child_ids..., separator_keys...]`；单叶退化扫描。
  3. Refactor — 封装 `tree_state = (root_page_id, key_type)`。
  4. Verify — 2 测试通过。
  5. Commit — `feat(B6): internal codec + seek/range (REQ-BT-002,003)`。
- **Depends on**: T-6.1.

#### T-6.3 Insert + leaf split

- **Files**: `Modify: tinydb/index.py`, `Modify: tests/unit/test_index.py`
- **Interfaces**:
  - Consumes: leaf/internal codec
  - Produces: `insert`、leaf split 返回 `(new_page_id, separator_key)`
- **Steps**:
  1. Red — `test_insert_into_full_leaf_triggers_split`、`test_seek_after_split_finds_all`；失败。
  2. Green — insert + overflow 检查 + split-and-promote。
  3. Refactor — 拆 `_split_leaf`。
  4. Verify — 2 测试通过 + 1000 key 压力。
  5. Commit — `feat(B6): insert + leaf split (REQ-BT-005)`。
- **Depends on**: T-6.2.

#### T-6.4 Root 提升 + 递归 internal split

- **Files**: `Modify: tinydb/index.py`, `Modify: tests/unit/test_index.py`
- **Interfaces**:
  - Consumes: leaf split
  - Produces：完整 insert（含 root 提升、internal split）
- **Steps**:
  1. Red — `test_root_promotion_creates_internal_root`、`test_randomized_5000_keys_match_sorted_dict`；失败。
  2. Green — 递归 insert 向上传播 `(new_page_id, sep_key)`。
  3. Refactor — 共享 `_handle_overflow(page_id)`。
  4. Verify — 2 测试通过。
  5. Commit — `feat(B6): root promotion + internal splits (REQ-BT-005 e2e)`。
- **Depends on**: T-6.3.

#### T-6.5 Delete + merge / redistribute

- **Files**: `Modify: tinydb/index.py`, `Modify: tests/unit/test_index.py`
- **Interfaces**:
  - Consumes: full insert
  - Produces: `delete`、underflow 处理（merge 或 redistribute）
- **Steps**:
  1. Red — `test_delete_underflow_triggers_merge`、`test_delete_underflow_triggers_redistribute`；失败。
  2. Green — delete + `try_rebalance` 后处理。
  3. Refactor — 提取 `_is_underflow`、`_merge_or_redistribute`。
  4. Verify — 2 测试通过 + insert-all-delete-all-reinsert-all 随机测试。
  5. Commit — `feat(B6): delete + merge/redistribute (REQ-BT-006 + REWRITE-PENDING 3.2)`。
- **Depends on**: T-6.4.

#### T-6.6 专用索引页 + TEXT 排序

- **Files**: `Modify: tinydb/index.py`, `Modify: tests/unit/test_index.py`
- **Interfaces**:
  - Consumes: full insert/delete
  - Produces: `BPlusTree` 始终分配 `page_type=INDEX` 页；TEXT 排序 seek
- **Steps**:
  1. Red — `test_index_pages_have_correct_type`、`test_text_index_orders_utf8`、`test_text_index_handles_cjk`；失败。
  2. Green — `alloc_page(INDEX)`；key_type 传入 codec。
  3. Refactor — tree state 存 key_type。
  4. Verify — 3 测试通过。
  5. Commit — `feat(B6): dedicated index pages + TEXT ordering (REQ-BT-007,008 + REWRITE-PENDING 3.6)`。
- **Depends on**: T-6.5.

---

### Batch 7：SQL Parser（拆分）

#### T-7.1 Lexer

- **Files**: `Modify: tinydb/parser/lexer.py`（由 T-1.2 空文件填充）, `Create: tests/unit/test_parser_lexer.py`
- **Interfaces**:
  - Consumes: none
  - Produces: `tokenize(sql: str) -> list[Token]`
- **Steps**:
  1. Red — `test_tokenize_keywords_and_idents`、`test_tokenize_string_with_doubled_quote`、`test_tokenize_position_tracking`；失败。
  2. Green — 状态机 lexer；关键词 frozenset；字符串 `'...''...'` 规则。
  3. Refactor — 拆 `_lex_number`、`_lex_string`、`_lex_ident_or_keyword`。
  4. Verify — 3 测试通过 + 行尾注释跳过。
  5. Commit — `feat(B7): lexer with positions (REQ-SP-001)`。
- **Depends on**: T-1.2.

#### T-7.2 AST dataclasses（含 Star、Checkpoint）

- **Files**: `Create: tinydb/parser/ast.py`
- **Interfaces**:
  - Consumes: none
  - Produces: 全部 Statement / Expr / Predicate frozen dataclass + `Star` + `Checkpoint`
- **Steps**:
  1. Red — `test_ast_equality_via_dataclass`；失败。
  2. Green — `@dataclass(frozen=True)` 定义所有节点。
  3. Refactor — 谓词归到 `Expr` Union。
  4. Verify — equality 通过；所有 dataclass 可 import。
  5. Commit — `feat(B7): AST dataclasses incl Star/Checkpoint (Decision D7)`。
- **Depends on**: T-1.2.

#### T-7.3 DDL 解析（CREATE/DROP/CHECKPOINT）

- **Files**: `Modify: tinydb/parser/ddl_parser.py`, `Create: tests/unit/test_parser_ddl.py`
- **Interfaces**:
  - Consumes: `tokenize`、AST
  - Produces: `_parse_create_table`、`_parse_drop_table`、`_parse_checkpoint`
- **Steps**:
  1. Red — `test_parse_create_table_with_pk_and_not_null`、`test_parse_drop_table_if_exists`、`test_parse_checkpoint`；失败。
  2. Green — 实现三个解析方法。
  3. Refactor — 提取 `_expect_keyword`、`_parse_ident`、`_parse_type_token`。
  4. Verify — 3 测试通过。
  5. Commit — `feat(B7): parse CREATE/DROP/CHECKPOINT (REQ-SP-002 + REWRITE-PENDING 3.3)`。
- **Depends on**: T-7.1, T-7.2.

#### T-7.4 DML 解析（INSERT/SELECT/UPDATE/DELETE）

- **Files**: `Modify: tinydb/parser/dml_parser.py`, `Create: tests/unit/test_parser_dml.py`
- **Interfaces**:
  - Consumes: AST
  - Produces: `_parse_insert`、`_parse_select`、`_parse_update`、`_parse_delete`
- **Steps**:
  1. Red — REQ-SP-003 子场景 + `SELECT *` 解析；失败。
  2. Green — 实现 DML 方法；`*` → `Star()`。
  3. Refactor — 共享 `_parse_where_clause`、`_parse_order_by`、`_parse_limit_offset`。
  4. Verify — 4 测试通过。
  5. Commit — `feat(B7): parse INSERT/SELECT/UPDATE/DELETE + Star (REQ-SP-003 + REWRITE-PENDING 3.5)`。
- **Depends on**: T-7.3.

#### T-7.5 谓词 / 聚合 / 错误位置

- **Files**: `Modify: tinydb/parser/predicate.py`, `Create: tests/unit/test_parser_predicate.py`
- **Interfaces**:
  - Consumes: AST
  - Produces: 谓词语法（AND/OR 优先级、BETWEEN、IN、IS NULL）、聚合识别、`ParseError`
- **Steps**:
  1. Red — AND-binds-tighter、BETWEEN-as-AND、COUNT(*)+GROUP BY、parse-error-position；失败。
  2. Green — 优先级爬升谓词解析器 + 聚合识别。
  3. Refactor — 提取 `_parse_atom_predicate`。
  4. Verify — 4 测试通过。
  5. Commit — `feat(B7): predicates + aggregates + error positions (REQ-SP-004,005,006)`。
- **Depends on**: T-7.4.

#### T-7.6 事务控制解析

- **Files**: `Modify: tinydb/parser/tx_control.py`, `Create: tests/unit/test_parser_tx.py`
- **Interfaces**:
  - Consumes: AST
  - Produces: `_parse_begin`、`_parse_commit`、`_parse_rollback`
- **Steps**:
  1. Red — `test_parse_begin`、`test_parse_commit`、`test_parse_rollback`；失败。
  2. Green — 三个解析方法。
  3. Refactor — 合到 `_parse_tx_control` 分派。
  4. Verify — 3 测试通过。
  5. Commit — `feat(B7): parse BEGIN/COMMIT/ROLLBACK (REQ-TM-007)`。
- **Depends on**: T-7.3.

#### T-7.7 Parser 公共入口 + 纯度测试

- **Files**: `Modify: tinydb/parser/__init__.py`, `Modify: tests/unit/test_parser_predicate.py`（追加纯度测试）
- **Interfaces**:
  - Consumes: 各子解析器
  - Produces: `parse(sql: str) -> Statement`、`__all__`
- **Steps**:
  1. Red — `test_parser_pure_function`；失败。
  2. Green — `parse` 分派到各子解析器；声明 `__all__`。
  3. Refactor — 无。
  4. Verify — 纯度测试通过。
  5. Commit — `feat(B7): parser public entry + purity (REQ-SP-007 + REWRITE-PENDING 2.3)`。
- **Depends on**: T-7.5, T-7.6.

---

### Batch 8：Query Executor（拆分）

#### T-8.1 Catalog 执行

- **Files**: `Modify: tinydb/executor/catalog.py`, `Create: tests/unit/test_executor_ddl.py`
- **Interfaces**:
  - Consumes: `FileStore`、`BufferPool`、`catalog_codec`
  - Produces: `Catalog`：`create_table`、`drop_table`、`get_table`、`list_tables`
- **Steps**:
  1. Red — `test_catalog_create_then_get`、`test_catalog_drop_removes_table`；失败。
  2. Green — catalog 首页备份；用 `catalog_codec` 编解码。
  3. Refactor — 无。
  4. Verify — 2 测试通过。
  5. Commit — `feat(B8): Catalog (Decision D5, REQ-QE-001,002)`。
- **Depends on**: T-5.3, T-3.4.

#### T-8.2 DDL 执行（CREATE/DROP/CHECKPOINT）

- **Files**: `Modify: tinydb/executor/ddl.py`, `Modify: tests/unit/test_executor_ddl.py`
- **Interfaces**:
  - Consumes: `Catalog`、`Heap`、`BPlusTree`、`TxManager`
  - Produces: `exec_create_table`、`exec_drop_table`、`exec_checkpoint`
- **Steps**:
  1. Red — `test_create_table_creates_heap_and_catalog`、`test_drop_table_frees_pages`、`test_checkpoint_truncates_wal`；失败。
  2. Green — 实现三个 DDL 执行方法；DROP 释放数据 + 索引页。
  3. Refactor — 提取 `_free_table_pages(table_meta)`。
  4. Verify — 3 测试通过。
  5. Commit — `feat(B8): DDL execution incl CHECKPOINT (REQ-QE-001,002,011 + REWRITE-PENDING 3.3)`。
- **Depends on**: T-8.1, T-5.2, T-6.6, T-4.4.

#### T-8.3 DML 执行（INSERT/UPDATE/DELETE + 约束）

- **Files**: `Modify: tinydb/executor/dml.py`, `Create: tests/unit/test_executor_dml.py`
- **Interfaces**:
  - Consumes: `Heap`、`Catalog`、`types`
  - Produces: `exec_insert`、`exec_update`、`exec_delete`（含安全 DELETE）
- **Steps**:
  1. Red — REQ-QE-003 类型/NOT NULL/PK 场景 + REQ-QE-006 UPDATE/DELETE 场景；失败。
  2. Green — 实现约束校验 + 安全 DELETE 拒绝。
  3. Refactor — 提取 `_validate_row_against_schema`。
  4. Verify — 6 测试通过。
  5. Commit — `feat(B8): DML execution + constraints (REQ-QE-003,006)`。
- **Depends on**: T-8.1, T-5.2.

#### T-8.4 SELECT 执行（投影 + Star 展开 + WHERE + ORDER BY + LIMIT/OFFSET）

- **Files**: `Modify: tinydb/executor/select.py`, `Create: tests/unit/test_executor_select.py`
- **Interfaces**:
  - Consumes: `Heap`、`Catalog`、`types`
  - Produces: `exec_select`：投影（含 `Star` 展开）、WHERE 求值、ORDER BY、LIMIT/OFFSET
- **Steps**:
  1. Red — REQ-QE-004/005/007/008 场景 + `SELECT *` 展开；失败。
  2. Green — 递归谓词求值；`Star` → schema 全列；排序 + 切片。
  3. Refactor — 拆 `_sort_rows`、`_slice_rows`。
  4. Verify — 5 测试通过。
  5. Commit — `feat(B8): SELECT execution incl Star expansion (REQ-QE-004,005,007,008 + REWRITE-PENDING 3.5)`。
- **Depends on**: T-8.3.

#### T-8.5 聚合执行

- **Files**: `Modify: tinydb/executor/aggregate.py`, `Create: tests/unit/test_executor_aggregate.py`
- **Interfaces**:
  - Consumes: 过滤后行
  - Produces: `exec_aggregate`：COUNT / SUM / AVG + GROUP BY
- **Steps**:
  1. Red — REQ-QE-009 COUNT(*) 与 GROUP-BY-SUM 场景；失败。
  2. Green — 投影分组行；AVG = SUM / COUNT。
  3. Refactor — 提取 `_group_by(rows, keys)`。
  4. Verify — 2 测试通过。
  5. Commit — `feat(B8): aggregates + GROUP BY (REQ-QE-009)`。
- **Depends on**: T-8.4.

#### T-8.6 索引路径（IndexPlanner + IndexScan）

- **Files**: `Modify: tinydb/executor/index_plan.py`, `Create: tests/unit/test_executor_index.py`
- **Interfaces**:
  - Consumes: `BPlusTree`、`Catalog`
  - Produces: `IndexPlanner.plan(where, table) -> IndexPlan`、`exec_index_seek`、`exec_heap_scan`
- **Steps**:
  1. Red — REQ-QE-010 indexed-equality 与 unindexed-fallback 场景；失败。
  2. Green — 实现 `_plan_where` 查阅表索引；`Plan` 用 `IndexSeek` / `HeapScan` dataclass。
  3. Refactor — 无。
  4. Verify — 2 测试通过 + 注入计数器验证 index seek 仅读 1 行。
  5. Commit — `feat(B8): index-aware executor (REQ-QE-010 + REWRITE-PENDING 3.4)`。
- **Depends on**: T-6.6, T-8.4.

#### T-8.7 Executor 主类编排 + `__all__` + `dataclass.replace`

- **Files**: `Modify: tinydb/executor/__init__.py`
- **Interfaces**:
  - Consumes: 各 executor 子模块
  - Produces: `Executor(store, pool, wal)`、`execute(stmt) -> Result`、`__all__`
- **Steps**:
  1. Red — `test_executor_routes_each_statement_type`；失败。
  2. Green — `execute` 分派到各子模块；catalog flush 用 `dataclasses.replace`（2.9 关闭）。
  3. Refactor — 声明 `__all__`。
  4. Verify — 路由测试通过；确认无 `object.__setattr__` 用法。
  5. Commit — `feat(B8): Executor orchestration + __all__ + dataclass.replace (REWRITE-PENDING 2.1,2.9,3.9)`。
- **Depends on**: T-8.2, T-8.3, T-8.4, T-8.5, T-8.6.

---

### Batch 9：Database 包装层

#### T-9.1 Database 类（生命周期 + execute + transaction + context manager）

- **Files**: `Create: tinydb/database.py`, `Create: tests/unit/test_database.py`
- **Interfaces**:
  - Consumes: `Executor`、`FileStore`、`BufferPool`、`Wal`、`parser.parse`
  - Produces: `Database(path, page_size, wal_path)`、`execute(sql) -> list[dict]`、`transaction()`、`close()`、`__all__`
- **Steps**:
  1. Red — REQ-DB-001..006 场景；失败。
  2. Green — 构造 4 个底层对象；`execute` 解析 + 执行 + 归一化返回；`transaction()` 上下文管理器；`close()` 逆序释放。
  3. Refactor — 归一化返回提取 `_normalize_result(result)`。
  4. Verify — 6 测试通过。
  5. Commit — `feat(B9): Database wrapper + transaction() (REQ-DB-001..006 + REWRITE-PENDING 3.8)`。
- **Depends on**: T-8.7, T-4.4, T-3.5, T-7.7.

#### T-9.2 `__init__.py` 重导出

- **Files**: `Modify: tinydb/__init__.py`
- **Interfaces**:
  - Consumes: `Database`、`errors` 异常类
  - Produces: 重导出 + `__all__`
- **Steps**:
  1. Red — `test_top_level_import_database`、`test_all_is_complete`；失败。
  2. Green — 导入并重导出所有公共名；声明 `__all__`。
  3. Refactor — 无。
  4. Verify — 2 测试通过。
  5. Commit — `feat(B9): __init__.py re-exports + __all__ (REQ-DB-005 + REWRITE-PENDING 4.3,4.6)`。
- **Depends on**: T-9.1, T-2.1.

---

### Batch 10：CLI / REPL

#### T-10.1 CLI 入口 + `--help` / `--version`

- **Files**: `Create: tinydb/cli.py`, `Create: tests/e2e/test_cli_repl.py`
- **Interfaces**:
  - Consumes: `Database`、`parser`
  - Produces: `main(argv, stdin, stdout, stderr) -> int`
- **Steps**:
  1. Red — `test_help_exits_zero`、`test_version_exits_zero`；失败。
  2. Green — `argparse` 入口；`--version` 读 `tinydb.__version__`。
  3. Refactor — 提取 `_build_parser()`。
  4. Verify — 2 测试通过（subprocess）。
  5. Commit — `feat(B10): CLI --help/--version (REQ-CR-006)`。
- **Depends on**: T-9.1.

#### T-10.2 REPL 循环 + 单语句执行

- **Files**: `Modify: tinydb/cli.py`, `Modify: tests/e2e/test_cli_repl.py`
- **Interfaces**:
  - Consumes: `Database`、parser、REPL 打印辅助
  - Produces: REPL 读一行、解析、执行、打印结果
- **Steps**:
  1. Red — ASCII 表渲染 + `1 row inserted` 场景；失败。
  2. Green — REPL 循环 + `_print_result` + ASCII 表构建。
  3. Refactor — 提取 `_render_table(rows, columns)`。
  4. Verify — 2 测试通过（subprocess）。
  5. Commit — `feat(B10): REPL single-statement (REQ-CR-002)`。
- **Depends on**: T-10.1.

#### T-10.3 Dot-commands

- **Files**: `Modify: tinydb/cli.py`, `Modify: tests/e2e/test_cli_repl.py`
- **Interfaces**:
  - Consumes: `Database`、Catalog
  - Produces: `.tables`、`.schema`、`.exit`、`.quit`、`.help`、EOF 处理
- **Steps**:
  1. Red — `.tables`、`.schema`、EOF 场景；失败。
  2. Green — `_handle_dot_command(line)`；`EOFError` 捕获。
  3. Refactor — 小分派表 `.foo` → handler。
  4. Verify — 3 测试通过。
  5. Commit — `feat(B10): dot-commands (REQ-CR-003)`。
- **Depends on**: T-10.2.

#### T-10.4 多行输入 + 非致命错误（经 errors.format）

- **Files**: `Modify: tinydb/cli.py`, `Modify: tests/e2e/test_cli_repl.py`
- **Interfaces**:
  - Consumes: REPL 循环、`errors.format`
  - Produces: 续行缓冲至 `；`；错误走 `format` 打印到 stderr
- **Steps**:
  1. Red — 多行 INSERT + typo-does-not-kill-REPL 场景；失败。
  2. Green — 缓冲续行；异常走 `format` 打印到 stderr。
  3. Refactor — 提取 `_read_statement(stdin, prompt)`。
  4. Verify — 2 测试通过；确认 `cli.py` 无独立错误格式化路径（2.5 关闭）。
  5. Commit — `feat(B10): multi-line + non-fatal errors via format (REQ-CR-004,005 + REWRITE-PENDING 2.5)`。
- **Depends on**: T-10.3.

#### T-10.5 stdin 批处理模式

- **Files**: `Modify: tinydb/cli.py`, `Modify: tests/e2e/test_cli_repl.py`
- **Interfaces**:
  - Consumes: `main(argv, stdin, stdout, stderr)`
  - Produces: 检测非 tty stdin → 批处理模式
- **Steps**:
  1. Red — 成功批处理 + fail-fast 场景；失败。
  2. Green — `stdin.isatty()` 检测；`_run_batch(stdin)`。
  3. Refactor — `_run_batch` 复用 `_execute_one(sql)`。
  4. Verify — 2 测试通过（subprocess pipe）。
  5. Commit — `feat(B10): stdin batch mode (REQ-CR-007)`。
- **Depends on**: T-10.4.

#### T-10.6 CLI 使用 Database 包装层

- **Files**: `Modify: tinydb/cli.py`, `Modify: tests/e2e/test_cli_repl.py`
- **Interfaces**:
  - Consumes: `Database`
  - Produces: CLI 通过 `Database(path)` 打开，`db.execute(sql)` 执行，`db.close()` 关闭
- **Steps**:
  1. Red — `test_cli_uses_database_wrapper`（mock Database 验证调用）；失败。
  2. Green — CLI 构造 `Database` 而非 `Executor.open`。
  3. Refactor — 无。
  4. Verify — 测试通过。
  5. Commit — `feat(B10): CLI uses Database wrapper (REQ-CR-008)`。
- **Depends on**: T-10.2, T-9.1.

---

### Batch 11：E2E 测试 + 质量门禁

#### T-11.1 E2E：SQL 全流程（REPL 子进程）

- **Files**: `Modify: tests/e2e/test_cli_repl.py`
- **Interfaces**:
  - Consumes: 完整 CLI
  - Produces: 单 subprocess 测试跑 CREATE → INSERT×N → SELECT(WHERE/ORDER BY/LIMIT) → UPDATE → DELETE → DROP
- **Steps**:
  1. Red — 写全流程测试；失败。
  2. Green — 修复暴露的接线 bug。
  3. Refactor — 参数化 pytest + 辅助脚本。
  4. Verify — 测试通过。
  5. Commit — `test(B11): full SQL tour through REPL`。
- **Depends on**: T-10.6.

#### T-11.2 E2E：crash recovery 子进程

- **Files**: `Create: tests/e2e/test_crash_recovery.py`
- **Interfaces**:
  - Consumes: TxManager、WAL
  - Produces: subprocess 跑 BEGIN → INSERT → kill -9 → reopen → 断言一致
- **Steps**:
  1. Red — 写测试；失败。
  2. Green — 修复暴露的 bug。
  3. Refactor — 提取 `_kill_and_reopen(proc, db_path)`。
  4. Verify — 测试连续 3 次通过（无 flake）。
  5. Commit — `test(B11): crash-recovery subprocess E2E (REQ-TM-005 + REWRITE-PENDING 3.1)`。
- **Depends on**: T-4.4, T-3.5.

#### T-11.3 覆盖率 ≥90% 目标（补 missing lines 测试）

- **Files**: `Modify: tests/unit/*.py`（按需追加）
- **Interfaces**:
  - Consumes: pytest-cov
  - Produces: `pytest --cov=tinydb --cov-fail-under=80` 通过；整体覆盖率 ≥90%
- **Steps**:
  1. Red — 跑覆盖率；观察缺口。
  2. Green — 为未覆盖分支补测试（重点 executor 110 missing lines，2.7 关闭）。
  3. Refactor — 删除发现的死代码。
  4. Verify — `pytest --cov=tinydb --cov-fail-under=80` 通过；报告 ≥90%。
  5. Commit — `test(B11): coverage ≥90% target (REWRITE-PENDING 2.7,6.4)`。
- **Depends on**: T-11.2.

#### T-11.4 ruff + mypy 零错误

- **Files**: `Modify: tinydb/**/*.py`（按需修复）
- **Interfaces**:
  - Consumes: ruff、mypy
  - Produces: 零 lint 错误、零 mypy 错误
- **Steps**:
  1. Red — `ruff check tinydb tests`、`mypy tinydb`；观察问题。
  2. Green — 修复（主要是 missing type hints、unused imports）。
  3. Refactor — 为 `tests/` 加 `[[tool.mypy.overrides]]` 允许 untyped defs。
  4. Verify — 两项通过。
  5. Commit — `chore(B11): ruff + mypy clean (REWRITE-PENDING 1.2,6.1,6.2)`。
- **Depends on**: T-11.3.

---

### Batch 12：性能基准 + 文档 + 发布

#### T-12.1 10k 行性能基准（非阻塞）

- **Files**: `Create: tests/bench/test_10k_rows.py`
- **Interfaces**:
  - Consumes: B+ Tree、Executor
  - Produces: 10k 行 insert + 100 次索引查找，断言正确且平均 < 1ms
- **Steps**:
  1. Red — 写测试；失败（首次可能 split bug）。
  2. Green — 修复暴露的 bug。
  3. Refactor — 提取工作负载到辅助模块。
  4. Verify — 测试通过；标记 `@pytest.mark.bench` 不阻塞默认 `pytest` 运行。
  5. Commit — `test(B12): 10k-row index benchmark (REWRITE-PENDING 3.7)`。
- **Depends on**: T-8.6, T-6.6.

#### T-12.2 README 快速开始 + Database API 示例

- **Files**: `Create: README.md`
- **Interfaces**:
  - Consumes: CLI、Database、design.md
  - Produces：5 分钟快速开始；Database API 示例；显式 Out-of-Scope 列表
- **Steps**:
  1. Red — 写 README 骨架。
  2. Green — 安装说明；Database 示例；REPL 示例；链接到 `docs/architecture.md`。
  3. Refactor — 确保 README 与实现一致（4.1 关闭）。
  4. Verify — `cat README.md` 渲染正常；无死链。
  5. Commit — `docs(B12): README quickstart + Database API (DP-0 traceability + REWRITE-PENDING 4.1)`。
- **Depends on**: T-11.4.

#### T-12.3 architecture.md + roadmap.md

- **Files**: `Create: docs/architecture.md`, `Create: docs/roadmap.md`
- **Interfaces**:
  - Consumes: design.md、specs/
  - Produces: 层映射 + spec→模块交叉引用表 + 文件树（与实现一致）；v0.2 延期项唯一真值源
- **Steps**:
  1. Red — 写 architecture.md 文件树。
  2. Green — 交叉引用表覆盖全部 8 个 spec；roadmap.md 汇总 v0.2 延期项。
  3. Refactor — 文件树与 `tinydb/` 实际结构对齐（4.2 关闭）。
  4. Verify — 无漂移。
  5. Commit — `docs(B12): architecture + roadmap (REWRITE-PENDING 4.2,4.4)`。
- **Depends on**: T-12.2.

#### T-12.4 最终 DP-7 审计 + review 留痕

- **Files**: `.spec-superflow.yaml`（由 ssf 工具更新）
- **Interfaces**:
  - Consumes: 完整状态机
  - Produces: 全部 7 DP 字段齐；每个 wave ≥30 行实质 review（1.1 关闭）
- **Steps**:
  1. Red — `ssf validate` 显示缺字段。
  2. Green — 跑 `ssf validate` 与 `ssf state check` 全部通过。
  3. Refactor — 无。
  4. Verify — 验证报告列出全部 DP + wave review。
  5. Commit — `chore(B12): DP-7 audit + review receipts (REWRITE-PENDING 1.1,1.5,7.1,7.2)`。
- **Depends on**: T-12.3.

---

## 跨批次验收门（Cross-cutting Acceptance Gates）

- [ ] Batch 1..12 全部完成；commit 在 DP-0 约束可追溯。
- [ ] `pytest --cov=tinydb --cov-fail-under=80` 通过；整体覆盖率 ≥90%。
- [ ] `ruff check tinydb tests` 零错误；`mypy tinydb` 零错误。
- [ ] E2E 测试在 `tests/e2e/` 全部通过（含 crash recovery 3 次无 flake）。
- [ ] 10k 基准测试通过（`@pytest.mark.bench`，非阻塞）。
- [ ] REPL 烟雾测试：CREATE → INSERT → SELECT → BEGIN → COMMIT → reopen → SELECT。
- [ ] 批处理模式测试（StringIO stdin）。
- [ ] `ssf validate changes/tinydb-v0.1-redo` 通过。
- [ ] `ssf state check changes/tinydb-v0.1-redo` 通过。
- [ ] `.spec-superflow.yaml` 显示 `state: closing`、`batches_completed: 12`、`test_result: pass`。
- [ ] 33 项 REWRITE-PENDING 每条都有对应 commit 或显式"范围外"记录。
