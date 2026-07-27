# 执行合同：tinydb v0.2

## Intent Lock

- **变更名称**：tinydb v0.2
- **要解决的问题**：v0.1-redo 缺少多表 JOIN、并发控制、CLI 交互增强与执行计划可观测性，阻碍从教学原型走向可用嵌入式引擎。本次在 v0.1-redo 稳定基线上增量加入四项能力，文件格式与单连接语义向后兼容。
- **范围内**：join-query（INNER/LEFT 多表 JOIN，NLJ + Hash Join）、execution-plan（9 种计划节点、代价模型、EXPLAIN）、concurrency-control（RWLock + 快照读 + fcntl.flock、多事务 ID）、cli-enhanced（readline、pygments 高亮、.explain、.mode/.timer/.width/.nullvalue、--color）；仓库根 spec 合并；git worktree 隔离并行开发（W1/W2/W3 并行，W4 集成）。
- **范围外**：RIGHT/FULL OUTER JOIN、CROSS JOIN、USING 语法、子查询；基于直方图的复杂统计；网络/客户端-服务器；ALTER TABLE、视图、触发器、外键；多页堆、独立 NULL bitmap、WAL undo；Windows 锁实现的完整测试；双人 review 互检。

## Approved Behavior

- **已批准需求摘要**：
  - join-query：INNER/LEFT JOIN、多表链式、别名、`table.column` 限定列、条件运算符（=/>/</>=/<=/>、AND/OR）、WHERE/ORDER/LIMIT 组合、NLJ 默认 + 索引加速 + Hash Join 可选、类型兼容、空表 JOIN、Select/Column AST 向后兼容扩展（42 REQ 中 12 条）
  - execution-plan：9 种计划节点（TableScan/IndexScan/Filter/NLJ/HashJoin/Project/Sort/Limit/Aggregate）、索引 vs 代价决策、catalog 行数统计、JOIN 左深排序、EXPLAIN 语句、缩进树渲染、代价公式（9 REQ）
  - concurrency-control：连接级 RWLock（多读单写）、快照读、fcntl.flock 多进程互斥、锁超时 DatabaseBusy、close 可靠释放、多事务 ID 字典、catalog 缓存一致性、Database/TxManager 构造扩展兼容（9 REQ）
  - cli-enhanced：readline 行编辑与历史、多行 SQL 续行、pygments 语法高亮（可选懒加载降级）、.explain 命令、.mode(csv|json|table|color)/.timer/.width/.nullvalue dot-commands、--color 参数、默认输出向后兼容（12 REQ）
- **关键场景**：
  - `SELECT a.name, b.score FROM students a INNER JOIN scores b ON a.id = b.student_id WHERE b.score > 80 ORDER BY b.score DESC LIMIT 10` 返回正确多表结果
  - LEFT JOIN 右表无匹配填 NULL；无匹配 INNER JOIN 返回空
  - 歧义列（同名列无限定）抛 AmbiguousColumn；JOIN 列类型不匹配抛 TypeMismatch
  - `EXPLAIN SELECT ...` 与 `.explain SELECT ...` 输出计划树且不执行查询
  - 多线程并发读不阻塞、写互斥；多进程 flock 互斥；超时抛 DatabaseBusy
  - 读连接快照不受并发写影响；DDL 提交后新读者可见
  - pygments/readline 未安装时优雅降级；默认 CLI 输出格式与 v0.1 一致
- **验收检查**：
  - `pytest --cov=tinydb --cov-fail-under=80` 通过；整体覆盖率 ≥90%
  - `ruff check tinydb tests` 零错误；`mypy tinydb` 零错误
  - 并发测试连续 3 次无 flake
  - E2E 全部通过（JOIN + .explain REPL 驱动）
  - v0.1 数据库文件可由 v0.2 直接打开（向后兼容）
  - spec 合并完成（`specs/` 主基线含 12 个能力域）
  - 每个 Wave review receipt 为 `pass`

## Design Constraints

- **架构约束**：
  - 数据流保持 SQL → lexer → parser → AST → executor → storage/index/tx/types，层间通过类型化 Python 对象通信
  - 包布局按 D1/E3：`Select.joins` 默认 `()` 向后兼容；新增 `JoinClause`/`QualifiedColumn`/`Explain` 节点
  - 每文件 ≤ 400 行；新模块 `lock.py`、`join_parser.py`、`plan_nodes.py`、`join.py` 独立
  - 并发模型 E4/E5：RWLock + fcntl.flock + 读写锁互斥天然快照
  - 并行开发 E10：3 worktree（join+plan / concurrency / cli），W4 合入 main
- **接口约束**：
  - `Select(table, projections, joins=(), where, order_by, limit, offset, group_by)` — 单表 `joins=()`
  - `IndexPlanner.plan_select(table, joins, where, order_by, limit, offset, group_by, catalog) -> PlanNode`
  - `RWLock.acquire_read/write(timeout)` / `FileLock.shared/exclusive(timeout)` / `DatabaseBusy`
  - `TxManager(store, wal, lock_manager=None)` — `lock_manager=None` 保持 v0.1 行为
  - `Database(path, page_size=4096, wal_path=None, lock_timeout=5.0, readonly=False)`
  - `main(argv, stdin, stdout, stderr)` + `--color on|off|auto`
- **依赖约束**：
  - 运行时包仅依赖标准库（零第三方运行时依赖不变）
  - `pygments` 为可选 CLI 依赖（懒加载，未安装降级）；`readline` 标准库（Unix）
  - 标准库 `threading`、`fcntl`（Unix 文件锁）；Windows 锁文档化降级
- **数据约束**：
  - 不改变页头、WAL 记录、B+ Tree 节点、catalog 二进制布局
  - v0.1 数据库文件可直接由 v0.2 打开（无迁移）

## Execution Plan

full/hotfix 先运行 `ssf execution recommend`，按任务量和 wave 策略列出可用方式并推荐一种。W1/W2/W3 可并行（git worktree 隔离），W4 串行集成。批准后由 `ssf execution plan` 保存执行计划到 `<change>/.superpowers/sdd/execution-plan.json`。

## Execution Waves

每个 wave 必须有唯一 ID；只有依赖 wave 的 review receipt 为 `pass` 后，后续 wave 才可以开始。W1/W2/W3 策略 `parallel`（宿主支持并发派发时同时执行；不支持时须明确报告）。W4 策略 `serial`，依赖 W1/W2/W3。

### Wave W1 — JOIN + Execution Plan

- **Wave ID**：W1
- **任务**：Batch J1（JOIN AST + Parser）、J2（Plan nodes + Join exec + Planner）、J3（JOIN 集成 + EXPLAIN）
- **依赖 wave**：无
- **策略**：`parallel`（与 W2/W3 并发；wave 内 J1→J2→J3 serial）
- **目标**：多表 INNER/LEFT JOIN 解析与执行；9 种计划节点 + 真实代价模型；EXPLAIN 输出
- **输入**：v0.1-redo parser/executor/catalog 接口
- **输出**：`join_parser.py`、`plan_nodes.py`、`join.py`；扩展的 `ast.py`/`lexer.py`/`dml_parser.py`/`select.py`/`index_plan.py`/`__init__.py`；JOIN + EXPLAIN 测试绿
- **完成标准**：42 REQ 中 join-query + execution-plan（21 条）场景全绿；单表路径不变
- **Review gate**：review report 路径 `changes/tinydb-v0.2/.superpowers/sdd/reviews/w1-review.md`、base/head SHA、review receipt（`pass` | `fail`）

### Wave W2 — Concurrency Control

- **Wave ID**：W2
- **任务**：Batch C1（RWLock + FileLock + Database 集成）、C2（多事务 + 快照读 + catalog 一致性）
- **依赖 wave**：无
- **策略**：`parallel`（与 W1/W3 并发；wave 内 C1→C2 serial）
- **目标**：多线程读写锁 + 快照读 + 多进程文件锁 + 多事务 TxManager
- **输入**：v0.1-redo `database.py`/`tx.py`/`catalog.py` 接口
- **输出**：`lock.py`；扩展的 `database.py`/`tx.py`/`catalog.py`；并发测试绿
- **完成标准**：concurrency-control 9 条 REQ 场景全绿；单连接行为不变；并发测试连续 3 次无 flake
- **Review gate**：review report 路径 `changes/tinydb-v0.2/.superpowers/sdd/reviews/w2-review.md`、base/head SHA、review receipt（`pass` | `fail`）

### Wave W3 — CLI Enhanced

- **Wave ID**：W3
- **任务**：Batch CL1（readline + pygments + .explain + dot-commands + 多格式渲染）
- **依赖 wave**：无（.explain 消费 planner 接口，W4 集成时切换真实 planner）
- **策略**：`parallel`（与 W1/W2 并发）
- **目标**：行编辑、语法高亮、执行计划查看、新 dot-commands
- **输入**：`execution-plan` 的 EXPLAIN 接口（可先用 stub 占位）
- **输出**：扩展的 `cli.py`、可选依赖 `pygments` 声明；CLI 增强测试绿
- **完成标准**：cli-enhanced 12 条 REQ 场景全绿（含降级路径）；默认输出与 v0.1 一致
- **Review gate**：review report 路径 `changes/tinydb-v0.2/.superpowers/sdd/reviews/w3-review.md`、base/head SHA、review receipt（`pass` | `fail`）

### Wave W4 — 集成 + Spec 合并

- **Wave ID**：W4
- **任务**：Batch INT（三路合入 + 冲突解决 + .explain 接真实 planner + spec 合并 + 发布审计）
- **依赖 wave**：W1、W2、W3（三者 review receipt 均为 `pass`）
- **策略**：`serial`
- **目标**：三路 worktree 合入 main；完整回归；spec 合并入 `specs/` 主基线；v0.2 发布
- **输入**：W1/W2/W3 各自绿 test 分支
- **输出**：main 分支完整 v0.2；`specs/` 主基线（12 能力域）；更新 `roadmap.md`/`README.md`；`.spec-superflow.yaml` state=closing
- **完成标准**：全量测试绿（含 v0.1 回归 227+）；覆盖率 ≥80% 目标 ≥90%；ruff/mypy 零错误；`spec_merged: true`；DP-7 审计通过
- **Review gate**：review report 路径 `changes/tinydb-v0.2/.superpowers/sdd/reviews/w4-review.md`、base/head SHA、review receipt（`pass` | `fail`）

## Test Obligations

- **必须先从失败测试开始的行为**：
  - 每个 batch 的 TDD 5 步（Red → Green → Refactor → Verify → Commit）
  - JOIN 列歧义检测、类型不匹配、空表 JOIN
  - 索引等值查询必选 IndexScan；大表全扫选 TableScan
  - 并发读写锁互斥、超时 DatabaseBusy、close 释放
  - pygments/readline 缺失时降级
- **必需的边界情况**：
  - 无匹配 INNER JOIN 返回空；LEFT JOIN 填 NULL
  - 链式 3+ 表 JOIN；自 JOIN 别名
  - 锁超时；多进程 flock 互斥
  - 无 pygments/readline 降级路径
  - v0.1 数据库文件直接打开
- **回归敏感区域**：
  - 单表 SELECT 路径（JOIN 扩展不得破坏）
  - 单连接事务语义（lock_manager=None 路径）
  - 默认 CLI 输出格式
  - 文件格式兼容性

## Execution Mode

- **可用方式与推荐**：`sdd`（推荐，W1/W2/W3 可并行派发 subagent）、`inline`、`batch-inline`
- **用户确认的模式**：`sdd` | `inline` | `batch-inline`（待 DP-4 确认）
- **推荐理由 / 项目事实**：13 batches、4 waves、W1/W2/W3 可并行（git worktree 隔离）、跨 wave 依赖链 W1/W2/W3 → W4；`sdd` 可利用 subagent 并发处理三路
- **非推荐选择的风险确认**：`--acknowledge-recommendation`（若选 inline/batch-inline，三路变串行，丧失并行加速）
- **执行计划命令**：`sdd` 模式下由 `ssf execution plan` 生成
- **允许的修订**：保留/升级为 `sdd`；不允许降级
- **计划 revision / artifact hash**：待 `ssf execution plan` 执行后填入

## Verification Dimensions

| 维度 | 状态 | 发现 |
|------|------|------|
| Completeness | Pending | 待实现后验证：4 能力域 42 REQ + 10 修改需求全部覆盖（join-query 12 / execution-plan 9 / concurrency-control 9 / cli-enhanced 12） |
| Correctness | Pending | 待实现后验证：pytest 全绿 + E2E 全绿 + 并发连续 3 次无 flake |
| Coherence | Pending | 待实现后验证：层间类型化通信、模块 ≤400 行、向后兼容、文件格式兼容 |

**总体结论**：Pending

## Review Gates

- **强制审查点**：每个 Execution Wave（W1..W4）完成后记录 `ssf execution review` 的 review receipt；每个 wave review ≥30 行实质内容
- **阻塞类别**：依赖 wave review receipt 为 `fail`；缺失或过期 review receipt；spec 映射缺失；覆盖率 <80%；ruff/mypy 非零
- **收口条件**：所有当前 wave 都有 `pass` review receipt；W4 完成后 `.spec-superflow.yaml` 显示 `state: closing`

## Escalation Rules

- **何时回退到 `specifying`**：
  - proposal 范围变更（如新增 RIGHT/FULL OUTER JOIN、子查询、网络服务）
  - spec 的 SHALL/MUST 新增或修改
  - 用户决策变更（如移除 JOIN、改变并发模型）
- **何时回退到 `bridging`**：
  - wave 边界不再适配已批准设计（如 batch 依赖关系重大调整）
  - tasks.md 批次划分实质性变化
  - 接口契约（tasks.md Interfaces 块）需要变更
- **何时不得继续实现**：
  - 存在未映射的 spec 需求（当前 42 REQ + 10 修改需求全部已映射，无未映射项）
  - 用户未批准 DP-3
  - 前序 wave review receipt 非 `pass`
  - 出现未在 specs/ 中声明的新行为且未经 spec-writer 确认

## 需求覆盖矩阵（Requirement Coverage Matrix）

| Spec | 需求数 | 覆盖 batch | 覆盖 wave |
|---|---|---|---|
| join-query | 12 | J1, J2, J3 | W1 |
| execution-plan | 9 | J2, J3 | W1 |
| concurrency-control | 9 | C1, C2 | W2 |
| cli-enhanced | 12 | CL1 | W3 |

**未映射需求**：无。全部 42 条 REQ 均已映射到 batch 与 wave。
