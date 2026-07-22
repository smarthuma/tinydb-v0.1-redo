# 执行合同：tinydb v0.1-redo

## Intent Lock

- **变更名称**：tinydb v0.1-redo
- **要解决的问题**：原 v0.1 实现存在 33 项 REWRITE-PENDING 未完成事项（流程纪律缺失、模块边界模糊、设计延期项未落地、文档漂移），且缺少用户决策纳入的 Database 包装层。本次从零重建，补齐全部 33 项、新增 database-api 能力、按 D1..D10 拆分模块，并把流程纪律落到交付链中。
- **范围内**：33 项 REWRITE-PENDING 全部纳入；新增 database-api 能力（Database 类 + transaction() 上下文管理器 + `__init__.py` 重导出）；仓库根基础设施（pyproject.toml / .gitignore / README.md / docs/architecture.md / docs/roadmap.md）；8 项能力（type-system / storage-engine / sql-parser / btree-index / transaction-manager / query-executor / cli-repl / database-api）从零实现；覆盖率 ≥80% 硬门 / ≥90% 目标；ruff + mypy 零错误。
- **范围外**：多表 JOIN；并发控制（多线程/多进程）；ALTER TABLE / 视图 / 触发器 / 外键；网络服务；第三方运行时依赖；双人 review 互检（仅记录建议）；重新生成 decision-point-audit.md（决策：删除，仅保留 .spec-superflow.yaml）；推送/打标签（仅记录决策）；改变页头/WAL/B+Tree/catalog 二进制布局。

## Approved Behavior

- **已批准需求摘要**：
  - type-system：INT/FLOAT/TEXT/BOOL 编解码 + NULL + 强制规则 + 比较语义 + 异常层次 + `errors.format` 单一入口（REQ-TS-001..009）
  - storage-engine：4096 字节定长页 + 单文件持久化 + LRU 缓冲池 + 页分配释放 + fsync + WAL replay 接入 open（REQ-SE-001..007）
  - btree-index：internal/leaf 节点 + seek/range + INSERT/UPDATE/DELETE 维护 + split + merge/redistribute + 专用索引页 + INT/TEXT 排序 + 5k oracle（REQ-BT-001..009）
  - transaction-manager：BEGIN/COMMIT/ROLLBACK + WAL 前/后镜像 + 恢复重放 + 单连接序列化 + 事务控制 SQL + CHECKPOINT（REQ-TM-001..008）
  - sql-parser：词法分析 + DDL/DML 解析 + 谓词/聚合 + CHECKPOINT + 带位置 ParseError + 纯函数（REQ-SP-001..007）
  - query-executor：CREATE/DROP TABLE + INSERT 约束校验 + SELECT（含 Star 展开、WHERE、ORDER BY、LIMIT/OFFSET）+ 聚合 + 索引路径 + CHECKPOINT + dataclass.replace + `__all__`（REQ-QE-001..011）
  - cli-repl：REPL 单语句 + dot-commands + 非致命错误经 format + 多行输入 + --help/--version + stdin 批处理 + 使用 Database 包装层（REQ-CR-001..008）
  - database-api：Database 生命周期封装 + execute() + transaction() 上下文管理器 + 自身上下文管理器 + `__init__.py` 重导出 + 异常路径可靠关闭（REQ-DB-001..006）
- **关键场景**：
  - 10k 行 insert + 索引查找正确且平均 < 1ms
  - kill -9 后 reopen 数据一致（已提交事务已应用，未提交已回滚）
  - SELECT * 展开为 schema 全列
  - DELETE 无 WHERE 被拒绝（UnsafeDeleteWithoutWhere）
  - 嵌套 BEGIN 抛 TransactionAlreadyActive
  - 所有 CLI 错误经 errors.format 单一路由
  - Database.close() 幂等；init 失败释放资源
- **验收检查**：
  - `pytest --cov=tinydb --cov-fail-under=80` 通过；整体覆盖率 ≥90%
  - `ruff check tinydb tests` 零错误；`mypy tinydb` 零错误
  - E2E 全部通过（含 crash recovery 连续 3 次无 flake）
  - 10k 基准通过（`@pytest.mark.bench`，非阻塞）
  - REPL 烟雾测试：CREATE → INSERT → SELECT → BEGIN → COMMIT → reopen → SELECT
  - `ssf validate` 与 `ssf state check` 通过
  - 33 项 REWRITE-PENDING 每条都有对应 commit 或显式"范围外"记录

## Design Constraints

- **架构约束**：
  - 数据流保持 SQL → lexer → parser → AST → executor → storage/index/tx/types，层间通过类型化 Python 对象通信，不退化为字符串字典或全局状态
  - 包布局按 D1：扁平 `tinydb/` 树，parser/ 与 executor/ 为子包，每文件 ≤ 400 行
  - AST 用 frozen dataclass（D7）；错误为小异常层次 + `errors.format` 单一入口（D8）
  - Database 包装层封装 Executor 生命周期，不重复实现 WAL/bufferpool/catalog 逻辑（D9）
- **接口约束**：
  - 跨 batch 契约以 tasks.md 的 Interfaces 块为准；被依赖 batch 消费
  - `Database.execute(sql: str) -> list[dict]`；SELECT 返回行列表，DML 返回 `[{"rows_affected": n}]`，DDL 返回 `[{"status": "ok"}]`
  - `Database.transaction()` 上下文管理器：`__enter__` → BEGIN，`__exit__` 无异常 → COMMIT，有异常 → ROLLBACK
  - `Wal.replay(store, pool)` 必须在 `FileStore.open` 末尾被调用（当 WAL 存在时）
- **依赖约束**：
  - Python 3.10+；运行时仅依赖标准库（零第三方运行时依赖）
  - 开发依赖：pytest、pytest-cov、ruff、mypy
  - 单文件持久化：一个 `.db` 文件持有数据/catalog/索引；WAL 为兄弟文件 `<path>-wal`
- **数据约束**：
  - 页格式 4096 字节默认、8 字节头部 `[page_id u32 | page_type u8 | lsn u32]`，小端
  - B+ Tree 默认 order 64
  - catalog 在首页（page id 1）
  - 本次不改变页头/WAL/B+Tree/catalog 二进制布局（catalog 编解码拆文件但字节格式不变）

## Execution Plan

full/hotfix 先运行 `ssf execution recommend`，按任务量和 wave 策略列出可用方式并推荐一种，同时保存匹配当前 wave 的 recommendation receipt。Agent 展示候选项和理由，`plan` 和 `revise` 均只接受仍匹配 artifact、contract 和 wave 的凭据；用户通过 `--confirm` 明确确认；选择非推荐方式时还必须记录 `--acknowledge-recommendation`。Batch Inline 是串行模式，不得描述为并行。批准后，`ssf execution plan` 会把当前执行计划保存到 `<change>/.superpowers/sdd/execution-plan.json`；该 JSON 是计划的持久化控制面，不是本 execution contract 的一部分。

## Execution Waves

每个 wave 必须有唯一 ID；只有依赖 wave 的 review receipt 为 `pass` 后，后续 wave 才可以开始。`parallel` 只表示允许在宿主支持并发派发时同时执行；不支持并发时必须明确报告该能力不可用，而不能把 `parallel` 计划悄然改写成串行执行。

### Wave W1 — 项目骨架

- **Wave ID**：W1
- **任务**：Batch 1（T-1.1 pyproject.toml + .gitignore + 仓库根脚手架；T-1.2 包目录 + 空 `__init__.py`）
- **依赖 wave**：无
- **策略**：serial
- **目标**：建立可 pip install -e ".[dev]" 的项目骨架与包目录结构
- **输入**：无
- **输出**：`pyproject.toml`、`.gitignore`、`tinydb/__init__.py`（临时空）、`tinydb/parser/__init__.py`（临时空）、`tinydb/executor/__init__.py`（临时空）、`tests/{unit,e2e,bench}/__init__.py`
- **完成标准**：`pip install -e ".[dev]"` 成功；`pytest --collect-only` 找到 0 测试；`.gitignore` 覆盖 5.1 要求
- **Review gate**：review report 路径 `changes/tinydb-v0.1-redo/.superpowers/reviews/w1-review.md`、base/head SHA、review receipt（`pass` | `fail`）

### Wave W2 — 类型系统与错误基础设施

- **Wave ID**：W2
- **任务**：Batch 2（T-2.1 异常子类 + errors.format；T-2.2 ColumnType + INT 编解码；T-2.3 FLOAT/TEXT/BOOL 编解码；T-2.4 强制规则 + NULL + 比较语义 + `__all__`）
- **依赖 wave**：W1
- **策略**：serial
- **目标**：提供被存储/索引/executor 消费的类型原语与错误基础设施
- **输入**：包目录结构（W1）
- **输出**：`tinydb/types.py`、`tinydb/errors.py`、`tests/unit/test_types.py`、`tests/unit/test_errors.py`
- **完成标准**：REQ-TS-001..009 全部场景通过；`errors.format` 单一入口覆盖全部异常子类；`__all__` 声明完整
- **Review gate**：review report 路径 `changes/tinydb-v0.1-redo/.superpowers/reviews/w2-review.md`、base/head SHA、review receipt（`pass` | `fail`）

### Wave W3 — 存储引擎 + WAL + 事务管理器

- **Wave ID**：W3
- **任务**：Batch 3（T-3.1 Page 头部编解码；T-3.2 FileStore open/close + 页读写；T-3.3 BufferPool LRU；T-3.4 页分配/释放 + fsync；T-3.5 WAL replay 接入 FileStore.open）+ Batch 4（T-4.1 WAL 记录编解码；T-4.2 WAL append + fsync；T-4.3 WAL replay + truncate；T-4.4 TxManager BEGIN/COMMIT/ROLLBACK/CHECKPOINT）
- **依赖 wave**：W2（T-4.1 消费 FileStore，来自 W3 内 T-3.2）
- **策略**：serial（B3 与 B4 因 T-3.5 ↔ T-4.3 耦合必须串行）
- **目标**：提供页存储、缓冲池、WAL 与事务状态机，关闭 REWRITE-PENDING 3.1 / 3.3
- **输入**：类型系统（W2）
- **输出**：`tinydb/storage.py`、`tinydb/wal.py`、`tinydb/tx.py`、`tests/unit/test_storage.py`、`tests/unit/test_wal.py`、`tests/unit/test_tx.py`
- **完成标准**：REQ-SE-001..007 + REQ-TM-001..008 全部场景通过；`FileStore.open` 自动调用 `Wal.replay`；CHECKPOINT 刷页 + truncate WAL
- **Review gate**：review report 路径 `changes/tinydb-v0.1-redo/.superpowers/reviews/w3-review.md`、base/head SHA、review receipt（`pass` | `fail`）

### Wave W4 — 堆/行编解码/catalog + B+ Tree + Parser（并行子 wave）

- **Wave ID**：W4
- **任务**：Batch 5（T-5.1 行编解码；T-5.2 Heap 追加/扫描/删除/更新；T-5.3 Catalog 编解码）+ Batch 6（T-6.1 Leaf 节点编解码；T-6.2 Internal 节点编解码 + 单叶 seek/range；T-6.3 Insert + leaf split；T-6.4 Root 提升 + 递归 internal split；T-6.5 Delete + merge/redistribute；T-6.6 专用索引页 + TEXT 排序）+ Batch 7（T-7.1 Lexer；T-7.2 AST dataclasses；T-7.3 DDL 解析；T-7.4 DML 解析；T-7.5 谓词/聚合/错误位置；T-7.6 事务控制解析；T-7.7 Parser 公共入口 + 纯度测试）
- **依赖 wave**：W2（类型）、W3（存储）
- **策略**：parallel（B5 / B6 / B7 三者无跨 batch 依赖，可并发派发；宿主不支持并发时须明确报告）
- **目标**：提供堆访问、B+ Tree 索引、SQL 解析三项独立能力，关闭 REWRITE-PENDING 2.2 / 2.3 / 2.4 / 3.2 / 3.5 / 3.6
- **输入**：类型系统（W2）、存储引擎（W3）
- **输出**：`tinydb/heap.py`、`tinydb/row_layout.py`、`tinydb/catalog_codec.py`、`tinydb/index.py`、`tinydb/parser/{__init__,ast,lexer,ddl_parser,dml_parser,predicate,tx_control}.py` + 对应测试文件
- **完成标准**：REQ-BT-001..009 + REQ-SP-001..007 全部场景通过；5k oracle 通过；merge/redistribute 场景通过；TEXT 排序含 CJK；parser 纯度测试通过；`SELECT *` 解析为 `Star()`
- **Review gate**：review report 路径 `changes/tinydb-v0.1-redo/.superpowers/reviews/w4-review.md`、base/head SHA、review receipt（`pass` | `fail`）

### Wave W5 — Query Executor

- **Wave ID**：W5
- **任务**：Batch 8（T-8.1 Catalog 执行；T-8.2 DDL 执行；T-8.3 DML 执行 + 约束；T-8.4 SELECT 执行；T-8.5 聚合执行；T-8.6 索引路径；T-8.7 Executor 主类编排 + `__all__` + dataclass.replace）
- **依赖 wave**：W3（catalog/heap/index/tx）、W4（B+ Tree、parser 由 executor 消费）
- **策略**：serial
- **目标**：编排 catalog/heap/index/tx 完成全部 DDL/DML/SELECT/聚合/索引路径，关闭 REWRITE-PENDING 2.1 / 2.9 / 3.4 / 3.5 / 3.9
- **输入**：Catalog/Heap/B+Tree/Tx（W3、W4）
- **输出**：`tinydb/executor/{__init__,catalog,ddl,dml,select,aggregate,index_plan,checkpoint}.py` + 对应测试文件
- **完成标准**：REQ-QE-001..011 全部场景通过；索引路径仅读 1 行（注入计数器验证）；`dataclass.replace` 替代 `object.__setattr__`；executor 子模块 `__all__` 完整
- **Review gate**：review report 路径 `changes/tinydb-v0.1-redo/.superpowers/reviews/w5-review.md`、base/head SHA、review receipt（`pass` | `fail`）

### Wave W6 — Database 包装层 + CLI/REPL

- **Wave ID**：W6
- **任务**：Batch 9（T-9.1 Database 类；T-9.2 `__init__.py` 重导出）+ Batch 10（T-10.1 CLI 入口 + --help/--version；T-10.2 REPL 循环；T-10.3 Dot-commands；T-10.4 多行输入 + 非致命错误；T-10.5 stdin 批处理；T-10.6 CLI 使用 Database 包装层）
- **依赖 wave**：W5（executor）
- **策略**：serial（B10 依赖 B9 的 Database 类）
- **目标**：提供公共 API 入口与 CLI/REPL 交互，关闭 REWRITE-PENDING 2.5 / 3.8 / 4.3 / 4.6
- **输入**：Executor（W5）
- **输出**：`tinydb/database.py`、`tinydb/__init__.py`（重导出）、`tinydb/cli.py`、`tests/unit/test_database.py`、`tests/e2e/test_cli_repl.py`
- **完成标准**：REQ-DB-001..006 + REQ-CR-001..008 全部场景通过；Database.close() 幂等；init 失败释放资源；CLI 无独立错误格式化路径；CLI 通过 Database 包装层打开
- **Review gate**：review report 路径 `changes/tinydb-v0.1-redo/.superpowers/reviews/w6-review.md`、base/head SHA、review receipt（`pass` | `fail`）

### Wave W7 — E2E + 质量门禁

- **Wave ID**：W7
- **任务**：Batch 11（T-11.1 E2E SQL 全流程；T-11.2 E2E crash recovery 子进程；T-11.3 覆盖率 ≥90% 目标；T-11.4 ruff + mypy 零错误）
- **依赖 wave**：W6（完整 CLI）
- **策略**：serial
- **目标**：端到端验证 + 静态质量门禁，关闭 REWRITE-PENDING 1.2 / 2.7 / 3.1(e2e) / 6.1 / 6.2 / 6.4
- **输入**：完整 CLI/REPL（W6）、TxManager + WAL（W3）
- **输出**：`tests/e2e/test_crash_recovery.py`、覆盖率 ≥90%、ruff/mypy 零错误
- **完成标准**：E2E 全流程通过；crash recovery 连续 3 次无 flake；`pytest --cov=tinydb --cov-fail-under=80` 通过且整体 ≥90%；`ruff check tinydb tests` 零错误；`mypy tinydb` 零错误
- **Review gate**：review report 路径 `changes/tinydb-v0.1-redo/.superpowers/reviews/w7-review.md`、base/head SHA、review receipt（`pass` | `fail`）

### Wave W8 — 性能基准 + 文档 + 发布审计

- **Wave ID**：W8
- **任务**：Batch 12（T-12.1 10k 行性能基准；T-12.2 README；T-12.3 architecture.md + roadmap.md；T-12.4 最终 DP-7 审计 + review 留痕）
- **依赖 wave**：W7
- **策略**：serial
- **目标**：性能基准、文档同步、DP-7 收尾，关闭 REWRITE-PENDING 1.1 / 1.5 / 3.7 / 4.1 / 4.2 / 4.4 / 7.1 / 7.2
- **输入**：完整实现（W1..W7）
- **输出**：`tests/bench/test_10k_rows.py`、`README.md`、`docs/architecture.md`、`docs/roadmap.md`、`.spec-superflow.yaml`（state=closing）
- **完成标准**：10k 基准通过（`@pytest.mark.bench` 非阻塞）；README 与实现一致；architecture.md 文件树与 `tinydb/` 实际结构对齐；roadmap.md 为 v0.2 延期项唯一真值源；`ssf validate` 与 `ssf state check` 通过；`.spec-superflow.yaml` 显示 `state: closing`、`batches_completed: 12`、`test_result: pass`；每个 wave ≥30 行实质 review
- **Review gate**：review report 路径 `changes/tinydb-v0.1-redo/.superpowers/reviews/w8-review.md`、base/head SHA、review receipt（`pass` | `fail`）

## Test Obligations

- **必须先从失败测试开始的行为**：
  - 每个 batch 的 TDD 5 步（Red → Green → Refactor → Verify → Commit）
  - 类型编解码 round-trip、溢出拒绝
  - 页头 round-trip、LRU 驱逐、脏页写回
  - WAL 损坏 checksum 检测、replay 已提交/未提交
  - B+ Tree split/merge/redistribute、5k oracle
  - parser 纯度、带位置 ParseError
  - executor 约束校验、安全 DELETE、Star 展开、索引路径
  - Database 幂等 close、init 失败释放、transaction 自动回滚
  - CLI 非致命错误经 format、stdin 批处理 fail-fast
- **必需的边界情况**：
  - INT 溢出、BOOL 拒绝 0/1、NULL round-trip、NULL 被 WHERE 排除
  - 空字符串 TEXT、非 ASCII / CJK TEXT
  - 空数据库 open、空结果 SELECT
  - 无 WAL 时 replay 为 noop
  - DELETE 无 WHERE、嵌套 BEGIN
  - 多行 SQL 续行、EOF 退出
  - crash recovery 连续 3 次
- **回归敏感区域**：
  - B+ Tree split/merge/redistribute（R2）
  - WAL replay 与 page flush 顺序（R1）
  - Database 包装层资源释放（R9）
  - parser 纯函数语义（R4）
  - CLI 错误格式化单一路由（R6）

## Execution Mode

- **可用方式与推荐**：`ssf execution recommend changes/tinydb-v0.1-redo --wave W1:serial:T-1.1,T-1.2 --wave W2:serial:T-2.1,T-2.2,T-2.3,T-2.4 --wave W3:serial:T-3.1,T-3.2,T-3.3,T-3.4,T-3.5,T-4.1,T-4.2,T-4.3,T-4.4 --wave W4:parallel:T-5.1,T-5.2,T-5.3,T-6.1,T-6.2,T-6.3,T-6.4,T-6.5,T-6.6,T-7.1,T-7.2,T-7.3,T-7.4,T-7.5,T-7.6,T-7.7 --wave W5:serial:T-8.1,T-8.2,T-8.3,T-8.4,T-8.5,T-8.6,T-8.7 --wave W6:serial:T-9.1,T-9.2,T-10.1,T-10.2,T-10.3,T-10.4,T-10.5,T-10.6 --wave W7:serial:T-11.1,T-11.2,T-11.3,T-11.4 --wave W8:serial:T-12.1,T-12.2,T-12.3,T-12.4`
- **用户确认的模式**：`sdd` | `inline` | `batch-inline`（待用户确认）
- **推荐理由 / 项目事实**：68 个新建文件、8 个 wave、跨 wave 串行依赖链长（W1→W2→W3→W4→W5→W6→W7→W8），W4 内部可并行；推荐 `sdd` 以利用 subagent 并发处理 W4 的 B5/B6/B7
- **非推荐选择的风险确认**：`--acknowledge-recommendation`（若适用）
- **执行计划命令**：`sdd` 模式下由 `ssf execution plan` 生成；`inline` / `batch-inline` 模式待用户确认后执行
- **允许的修订**：将已有计划保留/升级为 `sdd`；先重新 recommend，并以 `--confirm` 生成新 revision 和清除旧 receipt；不允许降级：`ssf execution revise changes/tinydb-v0.1-redo --mode sdd --confirm --reason <text> --wave ...`
- **计划 revision / artifact hash**：待 `ssf execution plan` 执行后填入

## Verification Dimensions

| 维度 | 状态 | 发现 |
|------|------|------|
| Completeness | Pending | 待实现后验证：8 项能力全部 14 个 spec 的 SHALL/MUST 均有对应 batch 覆盖（REQ-TS-001..009 / REQ-SE-001..007 / REQ-BT-001..009 / REQ-TM-001..008 / REQ-SP-001..007 / REQ-QE-001..011 / REQ-CR-001..008 / REQ-DB-001..006） |
| Correctness | Pending | 待实现后验证：pytest 全绿 + E2E 全绿 + 10k 基准通过 |
| Coherence | Pending | 待实现后验证：层间类型化通信、模块 ≤400 行、`__all__` 完整、无 `object.__setattr__` |

**总体结论**：Pending

## Review Gates

- **强制审查点**：每个 Execution Wave（W1..W8）完成后记录 `ssf execution review` 的 review receipt；每个 wave review ≥30 行实质内容（关闭 REWRITE-PENDING 1.1）
- **阻塞类别**：依赖 wave review receipt 为 `fail`；缺失或过期 review receipt；spec 映射缺失；覆盖率 <80%；ruff / mypy 非零
- **收口条件**：所有当前 wave 都有 `pass` review receipt；W8 完成后 `.spec-superflow.yaml` 显示 `state: closing`

## Escalation Rules

- **何时回退到 `specifying`**：
  - proposal 范围变更（如新增 JOIN / 并发 / 网络服务）
  - spec 的 SHALL/MUST 新增或修改
  - 用户决策变更（如 Database 包装层移除、模块拆分策略变化）
  - 持久化格式（页头/WAL/B+Tree/catalog 二进制布局）需要变更
- **何时回退到 `bridging`**：
  - wave 边界不再适配已批准设计（如 batch 依赖关系重大调整）
  - tasks.md 批次划分实质性变化
  - 接口契约（tasks.md Interfaces 块）需要变更
- **何时不得继续实现**：
  - 存在未映射的 spec 需求（当前 8 项能力 14 个 spec 全部已映射，无未映射项）
  - 用户未批准 DP-3
  - 前序 wave review receipt 非 `pass`
  - 出现未在 specs/ 中声明的新行为且未经 spec-writer 确认

## 需求覆盖矩阵（Requirement Coverage Matrix）

| Spec | 需求 | 覆盖 batch | 覆盖 wave |
|---|---|---|---|
| type-system | REQ-TS-001..009 | B2 | W2 |
| storage-engine | REQ-SE-001..007 | B3 | W3 |
| btree-index | REQ-BT-001..009 | B6 | W4 |
| transaction-manager | REQ-TM-001..008 | B4 | W3 |
| sql-parser | REQ-SP-001..007 | B7 | W4 |
| query-executor | REQ-QE-001..011 | B8 | W5 |
| cli-repl | REQ-CR-001..008 | B10 | W6 |
| database-api | REQ-DB-001..006 | B9 | W6 |

**未映射需求**：无。全部 8 项能力 63 条 REQ 均已映射到 batch 与 wave。

## REWRITE-PENDING 关闭矩阵

| 类别 | 项 | 关闭 batch |
|---|---|---|
| 流程 5 项 | 1.1 实质 review / 1.2 lint+mypy / 1.3 audit 对齐 / 1.4 review 模板 / 1.5 self-review 留痕 | B11(T-11.4) / B12(T-12.4) |
| 代码质量 9 项 | 2.1 executor 拆分 / 2.2 heap 拆分 / 2.3 parser 拆分 / 2.4 catalog_codec 拆分 / 2.5 errors.format / 2.6 `__all__` / 2.7 补 missing lines / 2.8 测试合并 / 2.9 dataclass.replace | B8 / B5 / B7 / B5 / B2 / B8 / B11 / B1..B12 / B8 |
| 设计 9 项 | 3.1 Wal.replay / 3.2 leaf merge / 3.3 CHECKPOINT / 3.4 索引路径 / 3.5 SELECT \* / 3.6 TEXT 排序 / 3.7 10k 基准 / 3.8 Database 包装层 / 3.9 公共 API `__all__` | B3 / B6 / B4 / B8 / B7+B8 / B6 / B12 / B9 / B8+B9 |
| 文档 6 项 | 4.1 README / 4.2 architecture.md / 4.3 `__init__.py` / 4.4 roadmap.md / 4.5 design.md 偏离 / 4.6 空文件清理 | B12 / B12 / B9 / B12 / design.md / B1+B9 |
| 仓库 4 项 | 5.1 .gitignore / 5.2 维持忽略 / 5.3 清 .pyc / 5.4 master ahead | B1 / B1 / B1 / 仅记录 |
| 静态门 4 项 | 6.1 ruff / 6.2 mypy / 6.3 覆盖率 ≥80% / 6.4 覆盖率 ≥90% | B11 / B11 / B11 / B11 |
| DP 3 项 | 7.1 audit 对齐 / 7.2 走 DP-0..DP-7 / 7.3 review 互检 | B12 / B1..B12 / 仅记录建议 |
