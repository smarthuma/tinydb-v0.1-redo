# 变更提案：tinydb v0.1-redo

## 背景（Why）

`tinydb` 最初的 v0.1 实现虽然跑通了 194 个测试、覆盖率 83.82%，但事后自查（`REWRITE-PENDING.md`）发现 33 项未完成事项，集中在 4 类问题：

1. **流程纪律缺失**：b2..b9 共 8 份 wave review 是 12 行占位文本，零 finding；`ruff` / `mypy` 未安装也未跑；`decision-point-audit.md` 与 `.spec-superflow.yaml` 不一致（5/8 vs 8/8）。
2. **代码质量与模块边界模糊**：`executor.py` 单文件 720 行，揉进了 catalog 编解码、`_Heap` 130+ 行、predicate/aggregate；`parser/parser.py` 489 行词法/语法/谓词/tx-control 不分；错误信息在 executor / cli / wal 多处手工拼串。
3. **设计延期项未落地**：`Wal.replay()` 未接入 `FileStore.open`；B+ Tree 缺 leaf merge/redistribute；`CHECKPOINT` 未解析；索引路径未接入 executor；`SELECT *` 未展开。
4. **文档与仓库卫生**：README 提到不存在的 `db.transaction()`；`docs/architecture.md` 文件树描述 `__init__.py` 会导出 `Database` 但当前为空；`.gitignore` 缺 `*.db` / `*.db-wal`。

与此同时，用户已明确做出新决策：**Database 包装层 + `db.transaction()` 纳入 v0.1-redo（推荐）**。这意味着需要新增 `tinydb/database.py` 提供 `Database` 类，封装 `Executor.open()` 生命周期、提供 `Database.execute(sql: str) -> list[dict]` 主接口、以及 `Database.transaction()` 上下文管理器（`with db.transaction():` → 自动 BEGIN/COMMIT/ROLLBACK）；`tinydb/__init__.py` 重导出 `Database`、`TinyDBError` 及异常子类，并带 `__all__`。

综合以上，本次 v0.1-redo 的目标不是"推倒重来"，而是：**在原有 7 项能力基础上，补齐 33 项 REWRITE-PENDING、新增 `database-api` 能力、按 REWRITE-PENDING 2.1/2.2/2.3/2.4 拆分模块，并把流程纪律（实质 review、lint/mypy 门禁、覆盖率 ≥90%）落到交付链中。**

## 变更内容（What Changes）

### 新增能力

- `database-api`：`tinydb/database.py` 提供 `Database` 类，封装 `Executor.open()` 生命周期（路径 / 文件句柄 / WAL 可靠关闭），`Database.execute(sql: str) -> list[dict]` 主接口，`Database.transaction()` 上下文管理器。
- `tinydb/__init__.py` 重导出 `Database`、`TinyDBError` 及全部异常子类，带 `__all__`。

### 重构能力（行为不变，模块边界变化）

- `query-executor`：`executor.py` 按 D1 拆分为 `tinydb/executor/` 子包（`catalog.py`、`dml.py`、`ddl.py`、`select.py`、`aggregate.py`、`index_plan.py`、`checkpoint.py`、`__init__.py`），每文件 ≤ 400 行。
- `heap-row-layout`：`_Heap` 从 `executor.py` 拆出到 `tinydb/heap.py`，行编解码独立到 `tinydb/row_layout.py`。
- `catalog-codec`：catalog 编解码从 `executor.py` 拆出到 `tinydb/catalog_codec.py`。
- `sql-parser`：`parser/parser.py` 拆分为 `parser/lexer.py`、`parser/ast.py`、`parser/ddl_parser.py`、`parser/dml_parser.py`、`parser/predicate.py`、`parser/tx_control.py`、`parser/__init__.py`。

### 行为变化（解决 REWRITE-PENDING 设计延期项）

- `Wal.replay()` 接入 `FileStore.open`（REQ-TM-005 端到端）。
- B+ Tree leaf delete 触发 merge / redistribute（REQ-BT-006）。
- 新增 `CHECKPOINT` SQL 语句（parser + executor）。
- 索引路径接入 executor（`IndexPlanner` / `IndexScan`，REQ-QE-010）。
- `SELECT *` 投影展开（parser 或 executor 顶层展开为 schema 全列）。

### 仓库与质量基础设施

- 仓库根新建 `pyproject.toml`（含 ruff / mypy / pytest-cov 配置）、`.gitignore`（含 `*.db` / `*.db-wal` / `*.db-shm` / `*.db-journal` / `.coverage` / `htmlcov/` / `.pytest_cache/` / `__pycache__/` / `*.pyc`）、`README.md`、`docs/architecture.md`、`docs/roadmap.md`。
- 覆盖率硬门槛维持 ≥80%（`pyproject.toml` `fail_under=80`），但 v0.1-redo 目标 ≥90%（通过补测试覆盖 `executor.py` 110 missing lines 等）。
- 新增 `tests/bench/test_10k_rows.py` 作为非阻塞性能基准测试。

## 能力（Capabilities）

### 新增能力

- `database-api` — `Database` 包装层 + `db.transaction()` 上下文管理器。

### 修改能力

- `sql-parser` — 模块拆分（lexer / ast / ddl_parser / dml_parser / predicate / tx_control），纯函数语义不变。
- `query-executor` — 模块拆分（catalog / dml / ddl / select / aggregate / index_plan / checkpoint），新增索引路径与 `SELECT *` 展开。
- `btree-index` — 新增 leaf merge / redistribute。
- `transaction-manager` — `Wal.replay()` 接入 `FileStore.open`；新增 `CHECKPOINT`。
- `type-system` — 新增 `tinydb.errors.format(e) -> str` 单一错误格式化入口（从 types 或独立 `errors.py` 提供）。
- `storage-engine` — 接入 WAL replay。
- `cli-repl` — 通过 `Database` 包装层暴露事务语义（REPL 仍 autocommit，但底层走 `Database.transaction()`）。

### 保留能力（仅模块搬运，对外行为不变）

- `heap-row-layout` — 从 executor 拆出的堆与行编解码。
- `catalog-codec` — 从 executor 拆出的 catalog 编解码。

## 范围（Scope）

### 范围内（In Scope）

1. **33 项 REWRITE-PENDING 全部纳入**：
   - 流程 5 项（1.1 实质 review、1.2 lint/mypy、1.3 audit 对齐、1.4 review 模板、1.5 self-review 留痕）
   - 代码质量 9 项（2.1 executor 拆分、2.2 heap 拆分、2.3 parser 拆分、2.4 catalog_codec 拆分、2.5 errors.format、2.6 `__all__`、2.7 补 missing lines 测试、2.8 测试文件合并/重命名、2.9 `object.__setattr__` → `dataclass.replace`）
   - 设计 9 项（3.1 Wal.replay 接入、3.2 leaf merge/redistribute、3.3 CHECKPOINT、3.4 索引路径、3.5 SELECT * 展开、3.6 TEXT B+ Tree ordering 测试、3.7 10k 性能基准、3.8 Database 包装层、3.9 公共 API `__all__`）
   - 文档 6 项（4.1 README 一致性、4.2 architecture.md 同步、4.3 `__init__.py` 重导出、4.4 roadmap.md 唯一真值、4.5 design.md 偏离记录、4.6 空文件清理）
   - 仓库 4 项（5.1 .gitignore *.db/*.db-wal、5.2 维持现有忽略、5.3 清 .pyc、5.4 master ahead 决策）
   - 静态门 4 项（6.1 ruff 安装通过、6.2 mypy 安装通过、6.3 覆盖率 ≥80% 维持、6.4 覆盖率 ≥90% 目标）
   - DP 3 项（7.1 audit 对齐、7.2 走完整 DP-0..DP-7、7.3 review 互检建议）
2. **新增 `database-api` 能力**（`Database` 类 + `transaction()` 上下文管理器 + `__init__.py` 重导出）。
3. **仓库根基础设施**：`pyproject.toml` / `.gitignore` / `README.md` / `docs/architecture.md` / `docs/roadmap.md`。
4. **测试与质量门禁**：单元测试覆盖 33 项 REWRITE-PENDING 对应场景；E2E 覆盖 crash recovery、CLI/REPL、10k 基准；ruff + mypy 零错误；覆盖率 ≥80% 硬门 / ≥90% 目标。

### 范围外（Out of Scope）

- 多表 JOIN 查询。
- 并发控制（多线程 / 多进程安全）。
- `ALTER TABLE`、视图、触发器、外键。
- 网络 / 客户端-服务器模式。
- 第三方运行时依赖。
- 双人 review 互检（7.3 仅作为建议记录，不强制实施）。
- `decision-point-audit.md` 重新生成（1.3 决策：删除该文件，仅保留 `.spec-superflow.yaml` 为真值）。
- 推送 / 打标签（5.4 仅记录决策，不执行推送）。

## 影响（Impact）

- **影响的代码区域**：`tinydb/` 全部模块（parser、executor、storage、index、tx、wal、types、cli、database、\_\_init\_\_），以及新增的 `heap.py`、`row_layout.py`、`catalog_codec.py`、`errors.py`。
- **影响的 API 或接口**：
  - 新增公共入口 `from tinydb import Database, TinyDBError`。
  - `Database(path, page_size=4096, wal_path=None)` 构造。
  - `Database.execute(sql: str) -> list[dict]`（SELECT 返回行列表，DML 返回 `[{"rows_affected": n}]`，DDL 返回 `[{"status": "ok"}]`）。
  - `Database.transaction()` 上下文管理器（`__enter__` → BEGIN，`__exit__` 无异常 → COMMIT，有异常 → ROLLBACK）。
  - `Database.close()` 可靠关闭（WAL flush → 文件句柄 close）。
  - 底层 `Executor.open()` / `Executor.execute()` 仍保留，供高级用户直接使用。
- **依赖或涉及的外部系统**：无新增运行时依赖；开发依赖新增 `ruff`、`mypy`、`pytest-cov`（已在 `pyproject.toml` 声明）。
- **持久化格式兼容**：本次不改变页头、WAL 记录、B+ Tree 节点、catalog 的二进制布局（catalog 编解码拆文件但字节格式不变），因此无需迁移测试。
- **教学可读性**：每文件 ≤ 400 行，模块与能力一一对应，便于逐模块阅读。
