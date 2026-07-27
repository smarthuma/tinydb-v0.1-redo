# 变更提案：tinydb v0.2

## 背景（Why）

tinydb v0.1-redo 完成了嵌入式关系型数据库的核心能力（类型系统、存储引擎、WAL-based ACID、B+ Tree 索引、SQL 解析、Query Executor、CLI/REPL、Database 包装层），并关闭了全部 33 项 REWRITE-PENDING。但其存在三类明显短板，阻碍了从"教学原型"走向"可用的嵌入式引擎"：

1. **查询能力单薄**：仅支持单表查询，缺少多表 JOIN。任何涉及关联数据的场景（订单-用户、学生-课程）都需要应用层手工拼接，丧失了关系型数据库的核心价值。
2. **并发完全缺失**：`TxManager` 是单连接序列化模型，无锁管理器、无快照读、无多进程文件锁。多线程访问会竞争状态，多进程访问会损坏 `.db` 文件。
3. **CLI 交互原始**：REPL 使用裸 `input()`，无行编辑、无语法高亮、无执行计划观察手段，调试 SQL 效率低。

与此同时，v0.1-redo 在架构上为 v0.2 预留了扩展点：`Select` AST 已具备 `from` 扩展空间、`IndexPlanner` 已抽象出策略决策接口、`Database` 包装层隔离了资源生命周期。本次 v0.2 的目标不是推倒重来，而是：**在 v0.1-redo 稳定基线上，增量加入 JOIN、并发控制、CLI 增强三项能力，并在发布时把增量 spec 合并入完整规格基线。**

## 变更内容（What Changes）

### 新增能力

- **join-query**：多表 INNER JOIN / LEFT JOIN 解析与执行。`Select` AST 扩展 `from` 为表 + JOIN 子句列表；parser 识别 `JOIN ... ON ...`；executor 实现嵌套循环连接（Nested Loop Join）作为默认算法，键等值连接场景可选哈希连接（Hash Join）加速。支持别名（`table AS alias`）、链式多表 JOIN（`A JOIN B ON ... JOIN C ON ...`）、JOIN 条件含多列与 AND/OR。
- **concurrency-control**：连接级读写锁 + 快照读。`Database` 实例级 `threading.RLock` 保护元数据，读连接获取共享快照、写连接独占。多进程通过 `fcntl.flock` 文件锁互斥。`TxManager` 扩展为支持多事务 ID 并发（仍保持文件级单写者）。
- **cli-enhanced**：REPL 交互增强。`readline` 提供行编辑与历史；`pygments` 提供 SQL 语法高亮（CLI 层可选依赖）；新增 `.explain` 命令输出查询执行计划；新增 `.mode`、`.timer` 等 dot-commands。
- **execution-plan**：执行计划内暴露与 EXPLAIN 输出。`IndexPlanner` 从 stub 扩展为真正的代价估算器（索引扫描 vs 全表扫描、JOIN 顺序）；`EXPLAIN` SQL 语句与 `.explain` 命令消费该计划，输出人类可读的树形计划。

### 重构能力（行为扩展，接口兼容）

- **sql-parser**：`parser/dml_parser.py` 的 `parse_select` 扩展以解析 JOIN 子句；`ast.py` 新增 `JoinClause`、`JoinType`、`QualifiedColumn` 节点。单表查询的解析结果向后兼容（`joins` 字段为空列表）。
- **query-executor**：`executor/select.py` 的 `exec_select` 扩展为支持多表；新增 `executor/join.py` 实现连接算法；`executor/index_plan.py` 从 stub 扩展为真实 planner。单表查询路径不变。
- **transaction-manager**：`tx.py` 的 `TxManager` 扩展锁管理与快照读；新增 `tinydb/lock.py` 连接级锁管理器。单连接事务语义向后兼容。
- **database-api**：`database.py` 增加锁生命周期管理、工厂方法支持多连接。`Database` 单连接用法向后兼容。

### 行为变化

- SELECT 可从多表取数据，投影可用 `table.column` 限定列。
- 多线程/多进程可安全打开同一数据库（通过锁序列化）。
- REPL 获得行编辑、语法高亮、执行计划查看能力。
- EXPLAIN 语句可用。

### 依赖变化

- 新增 **可选** CLI 依赖 `pygments`（仅 `tinydb.cli` 使用，运行时 `tinydb` 包仍仅依赖标准库）。通过 `importlib` 懒加载，未安装时优雅降级为无颜色。
- 标准库新增 `readline`（Unix）/ `pyreadline3`（Windows，可选）用于行编辑。

## 能力（Capabilities）

### 新增能力

- `join-query` — 多表 INNER/LEFT JOIN 解析与执行。
- `concurrency-control` — 连接级读写锁、快照读、多进程文件锁。
- `cli-enhanced` — readline 行编辑、pygments 语法高亮、.explain、新 dot-commands。
- `execution-plan` — 代价估算、EXPLAIN 输出。

### 修改能力

- `sql-parser` — 扩展 SELECT 解析以支持 JOIN；AST 新增连接节点。
- `query-executor` — 扩展 SELECT 执行以支持多表；IndexPlanner 从 stub 扩展为真实 planner。
- `transaction-manager` — 扩展锁管理与快照读。
- `database-api` — 增加锁生命周期与多连接工厂。

### 保留能力（仅接口扩展，对外行为不变）

- `type-system`、`storage-engine`、`btree-index`、`heap-row-layout`、`catalog-codec`。

## 范围（Scope）

### 范围内（In Scope）

1. **JOIN 查询**：
   - INNER JOIN 与 LEFT JOIN（左外连接，右表无匹配时填 NULL）。
   - 多表链式 JOIN（`A JOIN B ON ... JOIN C ON ...`），结合性从左到右。
   - JOIN 条件支持多列、AND/OR、`=`/`>`/`<`/`>=`/`<=` 比较符。
   - 表别名（`table [AS] alias`），投影可用 `alias.column` 或 `table.column` 限定。
   - 默认 Nested Loop Join；键等值连接可选 Hash Join（基于 DP-4 执行时确认）。
   - JOIN + WHERE + ORDER BY + LIMIT/OFFSET 组合。
   - JOIN 列类型不匹配时抛 `TypeMismatch`。
2. **并发控制**：
   - 连接级读写锁：`threading.RLock` / `RWLock` 实现多读单写。
   - 快照读：读连接在获取锁时记录 LSN 快照，读取期间不受写连接影响。
   - 多进程安全：`fcntl.flock(LOCK_EX/LOCK_SH)` 文件锁（Unix；Windows 用 `msvcrt.locking` 或 `pywin32`，文档化降级）。
   - 锁超时与死锁检测（轻量级：超时释放 + 日志警告）。
   - 多连接共享同一 `FileStore` 时 catalog 缓存一致性。
3. **CLI 增强**：
   - `readline` 行编辑、历史（`~/.tinydb_history`）、多行 SQL 续行。
   - `pygments` SQL 语法高亮（可选依赖，未安装降级）。
   - `.explain <SQL>` 命令输出执行计划。
   - 新 dot-commands：`.mode table|csv|json`、`.timer on|off`、`.width n`、`.nullvalue <text>`。
   - `--color on|off|auto` CLI 参数控制高亮。
4. **执行计划**：
   - `IndexPlanner` 真实代价估算：基于表行数（来自 catalog）选择 index_seek vs heap_scan。
   - JOIN 顺序规划（按表大小升序，左深树）。
   - `EXPLAIN SQL` 语句 + `.explain` 命令输出树形计划（缩进 + 节点类型 + 估算代价）。
   - 计划节点类型：`TableScan`、`IndexScan`、`NestedLoopJoin`、`HashJoin`、`Filter`、`Project`、`Sort`、`Limit`。
5. **v0.2 发布时完整 spec 合并**：增量 specs 合并入 `specs/` 主基线（或 `changes/archive/` 归档后提升），形成 v0.2 完整规格。
6. **git worktree 隔离并行开发**：JOIN、并发、CLI 三项能力通过独立 worktree 分支开发，各自绿 test 后合入。

### 范围外（Out of Scope）

- RIGHT JOIN / FULL OUTER JOIN（LEFT JOIN 可模拟 RIGHT，FULL OUTER 留 v0.3）。
- CROSS JOIN（无 ON 条件的笛卡尔积，性能风险高）。
- `USING(column)` 语法（v0.3；当前用 `ON a.b = c.b`）。
- 子查询（WHERE 内嵌 SELECT，留 v0.3）。
- 查询优化器基于统计信息的复杂代价模型（仅做简化行数估算）。
- 网络 / 客户端-服务器模式。
- `ALTER TABLE`、视图、触发器、外键。
- 多页堆（突破单表容量限制，独立变更）。
- 独立 NULL bitmap（v0.1 已知限制，独立变更）。
- WAL undo 真正回滚（v0.1 已知限制，独立变更）。
- Windows 锁实现的完整测试（文档化 + CI 条件跳过）。
- 双人 review 互检（仅记录建议）。

## 影响（Impact）

- **影响的代码区域**：
  - `tinydb/parser/ast.py`（新增 JOIN 节点）
  - `tinydb/parser/dml_parser.py`（扩展 `parse_select`）
  - `tinydb/parser/lexer.py`（新增 `JOIN`/`INNER`/`LEFT`/`ON` 关键词）
  - `tinydb/executor/select.py`（扩展多表）
  - `tinydb/executor/join.py`（新增连接算法）
  - `tinydb/executor/index_plan.py`（扩展真实 planner）
  - `tinydb/executor/__init__.py`（新增 EXPLAIN 分派）
  - `tinydb/tx.py`（扩展锁管理与快照读）
  - `tinydb/lock.py`（新增连接级锁管理器）
  - `tinydb/database.py`（扩展锁生命周期、多连接工厂）
  - `tinydb/cli.py`（readline、pygments、.explain、新 dot-commands）
  - `pyproject.toml`（新增可选依赖 `pygments`）
  - `tests/`（新增与扩展测试）
- **影响的 API 或接口**：
  - `ast.Select.table` 保留（主表），新增 `ast.Select.joins: tuple[JoinClause, ...]`。单表查询 `joins=()`，向后兼容。
  - `ast.Column` 扩展为支持 `table` 限定（`QualifiedColumn(table, name)` 或 `Column(table, name)`）。
  - `Database(path, page_size, wal_path=None)` 签名保留；新增 `Database.open(path, **kwargs)` 工厂与锁参数。
  - `Executor.execute` 新增 `ast.Explain` 分派。
  - CLI 新增 `--color` 参数。
- **依赖或涉及的外部系统**：
  - 新增可选依赖 `pygments`（仅 CLI 层，运行时包零第三方依赖不变）。
  - 标准库 `readline`（Unix 内置；Windows 可选 `pyreadline3`）。
  - 标准库 `threading`、`fcntl`（Unix 文件锁）。
- **持久化格式兼容**：本次不改变页头、WAL 记录、B+ Tree 节点、catalog 的二进制布局。v0.1-redo 数据库文件可直接由 v0.2 打开。
- **并发模型变化**：从"单连接无锁"升级为"多连接读写锁 + 文件锁"。单连接用法行为不变。
- **教学可读性**：每文件 ≤ 400 行；JOIN、并发、CLI 各自独立模块，便于逐模块阅读。
