# 技术设计：tinydb v0.2

## 上下文（Context）

### 当前状态

- 仓库在 v0.1-redo 基线上稳定运行（227 passed, coverage 87.85%, ruff+mypy 零错误）。
- 模块布局（D1）：扁平 `tinydb/` 树，parser/ 与 executor/ 为子包，每文件 ≤ 400 行。
- 数据流：`SQL → lexer → parser → AST → executor → storage/index/tx/types`。
- 已知扩展点：`Select.table` 为单表字符串、`IndexPlanner` 为 stub（始终 `heap_scan`）、`TxManager` 单事务槽、`Database` 单连接、`cli.py` 用裸 `input()`。

### 约束条件（来自 DP-0 与 v0.1 继承）

- **Python 3.10+** 运行时；运行时包仅依赖标准库。
- **单文件持久化**：`.db` 文件持有数据/catalog/索引；WAL 为 `<path>-wal`。
- **v0.1 数据库文件可直接由 v0.2 打开**（不改变页头/WAL/B+Tree/catalog 二进制布局）。
- **单表查询、单连接事务语义向后兼容**。
- **覆盖率 ≥80% 硬门**（v0.2 目标 ≥90%）。
- **ruff + mypy 零错误**门禁。
- **git worktree 隔离并行开发**：JOIN / 并发 / CLI 三路分支。

### 利益相关者

- **应用开发者**：需要多表查询与多线程安全。
- **教学读者**：把代码当教材，可读性优先。
- **spec-superflow agent**：需要每个决策显式、可发现。

## 目标（Goals）

1. **多表查询**：INNER/LEFT JOIN 正确、可组合 WHERE/ORDER/LIMIT、别名与限定列。
2. **并发安全**：多线程读写锁 + 快照读 + 多进程文件锁，单连接行为不变。
3. **CLI 交互升级**：行编辑、语法高亮、执行计划可见、新 dot-commands。
4. **执行计划可观测**：真实 IndexPlanner 代价估算 + EXPLAIN 输出。
5. **向后兼容**：文件格式、单表查询、单连接事务、默认 CLI 输出格式均不变。
6. **教学可读性**：每文件 ≤ 400 行，每概念一命名良好的类/函数。
7. **v0.2 发布时完整 spec 合并**：增量 spec 合并入主基线。

## 非目标（Non-Goals）

- RIGHT/FULL OUTER JOIN、CROSS JOIN、USING 语法、子查询（v0.3）。
- 基于直方图的复杂统计信息；仅行数估算。
- 网络/客户端-服务器模式。
- ALTER TABLE、视图、触发器、外键。
- 多页堆、独立 NULL bitmap、WAL undo（v0.1 已知限制，独立变更）。
- Windows 锁实现的完整测试（文档化 + CI 条件跳过）。

## 决策（Decisions）

### 决策 E1：JOIN 执行算法 — Nested Loop Join 默认 + Hash Join 可选

- **选择**：默认 Nested Loop Join（外表逐行扫描 + 内表匹配）。等值连接且内表有索引时用索引加速（Index Nested Loop Join）；当Planner 估算 Hash Join 更代价时可选 Hash Join（内表较小时构建哈希表）。
- **理由**：NLJ 实现简单、内存占用恒定、对索引友好；Hash Join 在等值大表连接时有优势但需额外内存。两者覆盖教学场景。
- **考虑的替代方案**：
  - Sort-Merge Join — 拒绝，需排序阶段，对已索引列冗余。
  - 仅 NLJ — 可接受但 Hash Join 是合理的教学扩展，保留为可选路径。

### 决策 E2：JOIN 排序 — 左深树，小表优先（仅 INNER）

- **选择**：多表 INNER JOIN 按表行数升序排列（小表驱动），生成左深计划树。LEFT JOIN 保持书写顺序（左表必须为驱动表以保留语义）。
- **理由**：左深树是教学标准；小表优先最小化中间结果。LEFT JOIN 顺序敏感，不可重排。
- **考虑的替代方案**：
  - bushy tree — 拒绝，复杂度高，教学收益低。
  - 固定书写顺序 — 拒绝，对 INNER 非最优。

### 决策 E3：AST 扩展方式 — 新增 JoinClause + QualifiedColumn

- **选择**：
  - `Select` 新增 `joins: tuple[JoinClause, ...]` 字段，默认 `()`（向后兼容）。
  - 新增 `JoinClause(kind: JoinType, table: str, alias: str | None, on: expr)`。
  - 新增 `JoinType` 枚举 `INNER | LEFT`。
  - 新增 `QualifiedColumn(table: str | None, name: str)`；现有 `Column(name)` 保留为无限定形式。
- **理由**：最小侵入现有 AST；单表查询 `joins=()` 路径不变；`QualifiedColumn` 显式区分限定/无限定列，消除歧义。
- **考虑的替代方案**：
  - 扩展 `Column` 加 `table` 字段 — 拒绝，破坏大量现有 `Column(name)` 构造点。
  - 用 `from_tables` 列表 — 拒绝，丢失 JOIN 类型与 ON 条件的结构化信息。

### 决策 E4：并发模型 — 连接级 RWLock + fcntl.flock

- **选择**：新增 `tinydb/lock.py` 实现 `RWLock`（基于 `threading.Lock` + `threading.Condition`，多读单写）。`Database` 实例持有 `RWLock`；读操作获读锁，写操作获写锁。多进程通过 `fcntl.flock` 在 `.db` 文件上协调。
- **理由**：RWLock 是嵌入式 DB 标准做法（如 SQLite 的读写锁）；`fcntl.flock` 是 Unix 标准，Python 标准库支持。实现 ≤ 200 行。
- **考虑的替代方案**：
  - 仅 `threading.Lock`（互斥）— 拒绝，丧失并发读。
  - 完整 MVCC — 拒绝，需多版本页存储，复杂化 WAL 与存储。
  - `filelock` 第三方库 — 拒绝，坚持 stdlib。

### 决策 E5：快照读实现 — 读锁 + 缓冲池快照

- **选择**：读连接获读锁时记录当前 `buffer_pool` 的脏页集合与 catalog 版本号。读操作期间，写连接可提交（刷脏页、更新 catalog），但读连接看到的缓冲池页版本不变（通过 copy-on-read：读连接读取页时若页已被写连接修改，使用读锁获取时的快照副本）。简化实现：读锁阻止写锁，因此读期间无写提交，天然快照。
- **理由**：读写锁互斥已保证读期间无写提交，无需多版本页。实现最简。
- **考虑的替代方案**：
  - 真正多版本页 — 拒绝，复杂化缓冲池与页格式。
  - 读不阻塞写（MVCC）— 拒绝，超出 v0.2 范围。

### 决策 E6：TxManager 扩展 — 多事务 ID 字典

- **选择**：`TxManager` 将 `_tx: _TxState | None` 改为 `_txs: dict[int, _TxState]`。`begin()` 分配新 tx_id 并插入字典；`commit(tx_id)` / `rollback(tx_id)` 按键移除。同连接嵌套 BEGIN（同一 tx_id 重复 begin）仍抛 `TransactionAlreadyActive`。可选 `lock_manager` 参数，默认 None 保持 v0.1 行为。
- **理由**：最小改动支持多连接并发事务；保留嵌套 BEGIN 的报错语义；向后兼容。
- **考虑的替代方案**：
  - 独立 `Transaction` 对象 — 拒绝，需重构 Database/Executor 接口。
  - 移除嵌套 BEGIN 限制（保存点）— 拒绝，超出范围。

### 决策 E7：IndexPlanner 扩展 — 真实代价模型

- **选择**：`IndexPlanner` 从 stub 重写为 `plan_select(...) -> PlanNode` 返回完整计划树。新增 `tinydb/executor/plan_nodes.py` 定义 9 种节点 frozen dataclass。代价公式：TableScan = 数据页数；IndexScan = 索引高 + 1；NLJ = outer_rows × inner_cost；HashJoin = outer_rows + inner_rows。统计信息来自 catalog 的 `row_count`。
- **理由**：为 EXPLAIN 与 JOIN 排序提供决策基础；代价公式简化但可教学。
- **考虑的替代方案**：
  - 保留 `IndexPlan` 枚举 — 拒绝，不足以表达 JOIN 计划树。
  - 直方图统计 — 拒绝，超出范围。

### 决策 E8：EXPLAIN 输出格式 — 缩进树 + 节点属性

- **选择**：`EXPLAIN` 返回 `list[dict]`（每节点一 dict：`node`、`table`、`column`、`estimated_rows`、`estimated_cost`、`children`）。CLI 渲染为缩进树（2 空格/层）。结构化 dict 便于测试，CLI 渲染便于阅读。
- **理由**：分离数据（结构化）与呈现（CLI），测试可直接断言 dict。
- **考虑的替代方案**：
  - 仅文本输出 — 拒绝，难以断言。
  - JSON 输出 — 作为 `.mode json` 的可选格式，但默认缩进树更友好。

### 决策 E9：CLI 可选依赖 — pygments/readline 懒加载

- **选择**：`cli.py` 顶层尝试 `import readline` / `import pygments`，失败则设标志 `_readline_ok=False` / `_pygments_ok=False` 并降级。`pygments` 在 `pyproject.toml` 中声明为可选依赖（`[project.optional-dependencies]` 或仅文档化）。运行时 `tinydb` 包不 import CLI，故无运行时依赖。
- **理由**：保持运行时零第三方；CLI 增强仅在交互时使用；懒加载避免 import 失败阻断核心功能。
- **考虑的替代方案**：
  - 强制依赖 pygments — 拒绝，违反 stdlib 约束。
  - 内嵌迷你 SQL 高亮 — 拒绝，重复造轮子。

### 决策 E10：并行开发策略 — git worktree 三路分支

- **选择**：从 v0.1-redo 的 `main` 创建 3 个 worktree：
  - `worktree/join` 分支 `feature/v0.2-join`（join-query + execution-plan）
  - `worktree/concurrency` 分支 `feature/v0.2-concurrency`（concurrency-control）
  - `worktree/cli` 分支 `feature/v0.2-cli`（cli-enhanced）
  - 共享 `main` 作为集成分支，三路绿 test 后合入。
- **理由**：JOIN 与 execution-plan 耦合（planner 服务 JOIN），并发与 CLI 相对独立。三路隔离避免互相阻塞。
- **考虑的替代方案**：
  - 串行开发 — 拒绝，用户明确要求并行。
  - 4 个 worktree（execution-plan 独立）— 可接受，但 execution-plan 被 JOIN 和 CLI 共同消费，独立开发易产生接口不一致，故与 JOIN 合并。

## 风险与权衡（Risks And Trade-Offs）

- **风险 X1**：JOIN 列歧义（同名列多表）处理不当导致错误列引用。**缓解**：解析/规划阶段严格校验，歧义列立即抛 `AmbiguousColumn`。**权衡**：要求用户写 `table.column`，略增输入量。

- **风险 X2**：RWLock 写饥饿（持续读者阻止写者）。**缓解**：`RWLock` 实现采用写者优先或公平队列；锁超时机制防止无限阻塞。**权衡**：写者优先增加实现复杂度。

- **风险 X3**：`fcntl.flock` 在 NFS 或 Windows 上行为异常。**缓解**：文档化 Unix 限定；CI 条件跳过 Windows 锁测试；Windows 路径用 `msvcrt.locking` 或仅文档化降级。**权衡**：Windows 并发安全较弱。

- **风险 X4**：IndexPlanner 代价公式粗糙导致计划质量差。**缓解**：v0.2 仅做简化行数估算，文档化限制；计划正确性由测试保证（索引列等值查询必选 IndexScan）。**权衡**：复杂查询计划可能非最优，但教学可接受。

- **风险 X5**：REPL 可选依赖导致环境差异（开发机有 pygments，CI 无）。**缓解**：所有 CLI 测试在无 pygments 路径下运行（降级路径）；可选高亮路径用 monkeypatch 测试。**权衡**：测试矩阵略增。

- **风险 X6**：多事务 TxManager 与 v0.1 单事务代码路径冲突。**保留**：`lock_manager=None` 默认路径保持 v0.1 行为；新路径仅在显式启用时激活。**权衡**：两套路径增加测试面。

- **风险 X7**：worktree 三路合并冲突（尤其 AST/Executor 修改重叠）。**缓解**：JOIN+planner 合并一路减少冲突面；合并前各分支 rebase 到最新 main。**权衡**：合并成本。

## 迁移计划（Migration Plan）

- **上线步骤**：
  1. 从 v0.1-redo `main` 创建 3 个 worktree 分支。
  2. 各分支独立实现 + 测试（隔离 `.db` 文件在各自 worktree）。
  3. 各分支绿 test 后合入 `main`，解决冲突。
  4. 完整回归 + 覆盖率 + ruff/mypy。
  5. spec 合并：将 `changes/tinydb-v0.2/specs/*/spec.md` 合并入 `specs/` 主基线（或归档 v0.1-redo specs 后提升 v0.2 specs 为唯一基线）。
- **回滚步骤**：每分支一个原子 commit；合并前可独立 revert。
- **数据迁移**：无。v0.1 数据库文件直接兼容。

## 待明确问题（Open Issues）

- **问题 P1**：Hash Join 是否作为 v0.2 必交付项，还是作为"可选/实验"在 DP-4 执行时确认？**当前默认**：必交付（简化实现，小表构建哈希哈希表）。
- **问题 P2**：Windows 锁实现是否用 `msvcrt.locking`（阻塞模式有限）或仅文档化"Windows 多进程安全不保证"？**当前默认**：文档化 + CI 条件跳过。
- **问题 P3**：spec 合并目标路径——合并入仓库根 `specs/`（v0.1-redo 未建立此目录）还是保持 `changes/tinydb-v0.2/specs/` 并在发布时一次性归档合并？**当前默认**：发布时合并入 `specs/` 主基线。
