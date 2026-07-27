# 实现任务：tinydb v0.2

## 文件结构（File Structure）

仓库根：`/home/wfj/新建文件夹/开发tinydb-重置版/`。下表列出全部新建（Create）与修改（Modify）文件；未列出的 v0.1-redo 文件保持不变。

| 路径 | 职责 | 状态 |
|---|---|---|
| `tinydb/lock.py` | `RWLock` 读写锁 + `FileLock` 文件锁（fcntl）+ `DatabaseBusy` 异常 | Create |
| `tinydb/parser/join_parser.py` | `_parse_join_clause`、`_parse_ident_or_qualified`、`parse_select` 的 JOIN 扩展入口 | Create |
| `tinydb/executor/plan_nodes.py` | 9 种计划节点 frozen dataclass（TableScan/IndexScan/Filter/NLJ/HashJoin/Project/Sort/Limit/Aggregate） | Create |
| `tinydb/executor/join.py` | `exec_nested_loop_join`、`exec_hash_join`、`resolve_qualified_columns` | Create |
| `specs/join-query/spec.md` | JOIN 能力规格（已创建） | Create |
| `specs/execution-plan/spec.md` | 执行计划能力规格（已创建） | Create |
| `specs/concurrency-control/spec.md` | 并发控制能力规格（已创建） | Create |
| `specs/cli-enhanced/spec.md` | CLI 增强能力规格（已创建） | Create |
| `tinydb/parser/ast.py` | 新增 `JoinClause`、`JoinType`、`QualifiedColumn`、`Explain`；`Select` 加 `joins` 字段 | Modify |
| `tinydb/parser/lexer.py` | 新增 `JOIN`、`INNER`、`LEFT`、`ON`、`EXPLAIN` 关键词 | Modify |
| `tinydb/parser/dml_parser.py` | `parse_select` 扩展以调用 `join_parser` | Modify |
| `tinydb/parser/__init__.py` | `parse` 分派新增 `ast.Explain` | Modify |
| `tinydb/executor/__init__.py` | `_dispatch` 新增 `ast.Explain` 分派；导入 `Explain` | Modify |
| `tinydb/executor/select.py` | `exec_select` 扩展支持多表 JOIN；新增 `exec_explain` | Modify |
| `tinydb/executor/index_plan.py` | `IndexPlanner` 从 stub 重写为真实代价模型，返回 `PlanNode` 树 | Modify |
| `tinydb/executor/aggregate.py` | 适配多表行字典（加表前缀隔离） | Modify |
| `tinydb/tx.py` | `TxManager` 支持多事务 ID 字典 + 可选 `lock_manager` | Modify |
| `tinydb/database.py` | 新增 `lock_timeout`/`readonly` 参数、RWLock 生命周期、多连接工厂、`DatabaseBusy` 导入 | Modify |
| `tinydb/cli.py` | readline、pygments 懒加载、.explain、.mode/.timer/.width/.nullvalue、--color | Modify |
| `pyproject.toml` | 新增 `pygments` 可选依赖、`pytest` 标记 | Modify |
| `tests/unit/test_join_query.py` | REQ-JQ-001..012 场景 | Create |
| `tests/unit/test_execution_plan.py` | REQ-EP-001..010 场景 | Create |
| `tests/unit/test_concurrency.py` | REQ-CC-001..009 场景（线程 + 文件锁） | Create |
| `tests/unit/test_cli_enhanced.py` | REQ-CE-001..012 场景（含降级路径） | Create |
| `tests/e2e/test_join_cli_e2e.py` | JOIN + .explain 端到端（REPL 驱动） | Create |

## 接口（Interfaces）

跨批次契约。被依赖 batch 先交付，消费 batch 后开始。

### Batch J1 → J2, C1, CL1 消费的接口

```python
# tinydb/parser/ast.py (J1 交付)
@dataclass(frozen=True)
class JoinType(Enum):
    INNER = "INNER"
    LEFT = "LEFT"

@dataclass(frozen=True)
class JoinClause:
    kind: JoinType
    table: str
    alias: str | None
    on: object          # 谓词表达式

@dataclass(frozen=True)
class QualifiedColumn:
    table: str | None   # None 表示无限定
    name: str

@dataclass(frozen=True)
class Explain:
    statement: object   # 内层 Statement

# ast.Select 扩展
@dataclass(frozen=True)
class Select:
    projections: tuple[object, ...]
    table: str
    joins: tuple[JoinClause, ...] = ()   # 新增，默认空
    where: object = None
    order_by: tuple[OrderItem, ...] = ()
    limit: int | None = None
    offset: int | None = None
    group_by: tuple[object, ...] = ()
```

### Batch J2 → J3, CL1(Explain) 消费的接口

```python
# tinydb/executor/plan_nodes.py (J2 交付)
@dataclass(frozen=True)
class PlanNode:
    """计划树基类（9 种具体节点）"""
    node_type: str
    estimated_rows: int
    estimated_cost: float
    children: tuple[PlanNode, ...] = ()

# tinydb/executor/index_plan.py (J2 交付)
class IndexPlanner:
    def plan_select(
        self,
        table: str,
        joins: tuple[JoinClause, ...],
        where: object,
        order_by: tuple[OrderItem, ...],
        limit: int | None,
        offset: int | None,
        group_by: tuple[object, ...],
        catalog: Catalog,      # 读取 row_count / 索引元数据
    ) -> PlanNode: ...

# tinydb/executor/join.py (J2 交付)
def exec_nested_loop_join(
    store: FileStore,
    catalog: Catalog,
    planner: IndexPlanner,
    left_rows: list[dict],
    join: JoinClause,
) -> list[dict]: ...

def exec_hash_join(
    store: FileStore,
    catalog: Catalog,
    left_rows: list[dict],
    join: JoinClause,
) -> list[dict]: ...
```

### Batch C1 → C2, J3(可选) 消费的接口

```python
# tinydb/lock.py (C1 交付)
class RWLock:
    def acquire_read(self, timeout: float = 5.0) -> None: ...
    def release_read(self) -> None: ...
    def acquire_write(self, timeout: float = 5.0) -> None: ...
    def release_write(self) -> None: ...

class FileLock:
    def __init__(self, path: str) -> None: ...
    def shared(self, timeout: float = 5.0) -> None: ...   # LOCK_SH
    def exclusive(self, timeout: float = 5.0) -> None: ... # LOCK_EX
    def release(self) -> None: ...

class DatabaseBusy(TinyDBError): ...
```

### Batch C2 → 集成消费的接口

```python
# tinydb/tx.py (C2 交付)
class TxManager:
    def __init__(self, store: object, wal: Wal, lock_manager: LockManager | None = None) -> None: ...
    def begin(self) -> int: ...
    def commit(self, tx_id: int) -> None: ...
    def rollback(self, tx_id: int) -> None: ...
```

## 执行 Wave 与 Batch 划分

基于 git worktree 并行策略（E10），4 个能力域拆为 3 路：

| Wave | 能力域 | Batch | Worktree 分支 | 策略 | 依赖 |
|---|---|---|---|---|---|
| W1 | join-query + execution-plan | J1, J2, J3 | `feature/v0.2-join` | serial | 无 |
| W2 | concurrency-control | C1, C2 | `feature/v0.2-concurrency` | serial | 无 |
| W3 | cli-enhanced | CL1 | `feature/v0.2-cli` | serial | 无 |
| W4 | 集成 + spec 合并 | INT | `main` | serial | W1, W2, W3 |

W1/W2/W3 **可并行派发**（各自独立 worktree，无跨路共享文件冲突，除 `pyproject.toml` 与 `database.py` 可能需在 W4 合并）。W4 等待三路绿 test 后合入 main。

---

## Batch J1 — JOIN AST + Parser

Depends on: 无

### T-J1.1 — 扩展 ast.py 新增 JOIN 节点

- **Files**: `Modify: tinydb/parser/ast.py`
- **接口产出**: `JoinType`、`JoinClause`、`QualifiedColumn`、`Explain`；`Select.joins` 字段
- **TDD 5 步**:
  1. **Red**: 写 `test_join_query.py` 测试 `parse("SELECT * FROM A INNER JOIN B ON A.id = B.id")` 返回 `Select(joins=(JoinClause(...),))`，运行，失败。
  2. **Green**: 在 `ast.py` 新增 `JoinType`/`JoinClause`/`QualifiedColumn`/`Explain`，给 `Select` 加 `joins: tuple[JoinClause, ...] = ()`。
  3. **Refactor**: 确认 `Select` 的 `__init__` 默认值不破坏现有单表构造点；必要时用 `field(default_factory=tuple)` 模式。
  4. **Verify**: `test_join_query.py` 中 JOIN 解析场景绿；运行 `tests/unit/test_parser_*.py` 确认单表路径不变。
  5. **Commit**: `feat(J1): add JOIN AST nodes (JoinClause/JoinType/QualifiedColumn/Explain)`.

### T-J1.2 — 扩展 lexer.py 新增 JOIN 关键词

- **Files**: `Modify: tinydb/parser/lexer.py`
- **TDD 5 步**:
  1. **Red**: 测试 `tokenize("SELECT * FROM A JOIN B ON A.id = B.id")` 产出 `JOIN`/`ON` 关键词 token。
  2. **Green**: 在 `lexer.py` 关键词 frozenset 新增 `JOIN`、`INNER`、`LEFT`、`ON`、`EXPLAIN`、`FULL`、`RIGHT`、`CROSS`、`USING`（后者为 v0.3 预留，标记 reserved）。
  3. **Refactor**: 关键词排序与现有风格一致。
  4. **Verify**: 新关键词 token 类型正确；现有 lexer 测试不变。
  5. **Commit**: `feat(J1): add JOIN/ON/EXPLAIN keywords to lexer`.

### T-J1.3 — 新建 join_parser.py 实现 JOIN 解析

- **Files**: `Create: tinydb/parser/join_parser.py`, `Modify: tinydb/parser/dml_parser.py`
- **接口产出**: `_parse_join_clause(parser) -> JoinClause`
- **TDD 5 步**:
  1. **Red**: 测试链式 JOIN、别名、ON 多列 AND/OR、LEFT JOIN 解析。
  2. **Green**: 实现 `_parse_join_clause`（消耗 `[INNER|LEFT] JOIN table [AS alias] ON expr`）；修改 `parse_select` 在 `FROM table` 后循环调用 `_parse_join_clause`。
  3. **Refactor**: 提取 `_parse_qualified_column` 处理 `table.column`。
  4. **Verify**: 全部 JOIN 解析场景绿；单表 SELECT `joins=()`。
  5. **Commit**: `feat(J1): implement JOIN clause parser (inner/left, aliases, qualified columns)`.

### T-J1.4 — parser 公共入口支持 EXPLAIN

- **Files**: `Modify: tinydb/parser/__init__.py`
- **TDD 5 步**:
  1. **Red**: 测试 `parse("EXPLAIN SELECT * FROM users")` 返回 `Explain(statement=Select(...))`。
  2. **Green**: `parse_statement` 新增 `EXPLAIN` 分支，递归解析内层语句。
  3. **Refactor**: 无。
  4. **Verify**: EXPLAIN 解析绿；现有 parse 测试不变。
  5. **Commit**: `feat(J1): parser supports EXPLAIN statement`.

---

## Batch J2 — Execution Plan + Join Execution

Depends on: J1

### T-J2.1 — 新建 plan_nodes.py 定义 9 种计划节点

- **Files**: `Create: tinydb/executor/plan_nodes.py`
- **接口产出**: 9 种 `PlanNode` 子类
- **TDD 5 步**:
  1. **Red**: 测试构建 `Project(Filter(TableScan(...)))` 树并访问字段。
  2. **Green**: 实现 9 种 frozen dataclass。
  3. **Refactor**: 通用字段（`estimated_rows`/`estimated_cost`）提到基类或共用。
  4. **Verify**: 可构建任意深度树；`__eq__`/`__repr__` 可用（frozen dataclass 自动生成）。
  5. **Commit**: `feat(J2): add 9 plan node types (TableScan/IndexScan/NLJ/HashJoin/...)`.

### T-J2.2 — 重写 IndexPlanner 为真实代价模型

- **Files**: `Modify: tinydb/executor/index_plan.py`
- **接口产出**: `IndexPlanner.plan_select(...) -> PlanNode`
- **TDD 5 步**:
  1. **Red**: 测试 `plan_select` 对等值索引列选 `IndexScan`、对非索引列选 `TableScan`。
  2. **Green**: 实现代价公式（TableScan = 页数；IndexScan = 高 + 1；NLJ = outer × inner；HashJoin = outer + inner），读取 catalog `row_count`。
  3. **Refactor**: 提取 `_cost_table_scan` / `_cost_index_scan` / `_cost_nlj` / `_cost_hash` 辅助函数。
  4. **Verify**: 索引等值查询必选 IndexScan；大表全扫选 TableScan。
  5. **Commit**: `feat(J2): IndexPlanner real cost model (index vs heap, NLJ vs hash)`.

### T-J2.3 — 新建 join.py 实现 NLJ + Hash Join

- **Files**: `Create: tinydb/executor/join.py`
- **接口产出**: `exec_nested_loop_join`、`exec_hash_join`
- **TDD 5 步**:
  1. **Red**: 测试 NLJ 两表等值连接、左连接填 NULL、索引加速内扫描。
  2. **Green**: 实现 NLJ（外表逐行 + 内表 scan/seek）；实现 Hash Join（小表建哈希 + 外表探测）。
  3. **Refactor**: 提取 `_match_join_condition` 复用于 NLJ 与 Hash。
  4. **Verify**: NLJ 与 Hash Join 结果一致（oracle 对比）；空表 / 无匹配场景正确。
  5. **Commit**: `feat(J2): join execution (nested-loop + hash join)`.

### T-J2.4 — exec_select 扩展支持多表

- **Files**: `Modify: tinydb/executor/select.py`
- **TDD 5 步**:
  1. **Red**: 测试 `exec_select` 传入 `joins=(JoinClause(...),)` 返回多表结果。
  2. **Green**: `exec_select` 在 `joins` 非空时走 JOIN 路径（调用 `IndexPlanner` + `join.py`），否则走原单表路径。
  3. **Refactor**: 提取 `_exec_join_path` 函数，保持 `exec_select` 主函数 ≤ 40 行。
  4. **Verify**: 单表路径不变；多表路径正确；WHERE/ORDER/LIMIT 在 JOIN 后应用。
  5. **Commit**: `feat(J2): exec_select supports multi-table JOIN`.

---

## Batch J3 — JOIN 集成 + 列解析 + 类型校验

Depends on: J2

### T-J3.1 — 限定列解析与歧义检测

- **Files**: `Modify: tinydb/executor/join.py`（新增 `resolve_qualified_columns`）
- **TDD 5 步**:
  1. **Red**: 测试 `SELECT a.id, b.id FROM A a JOIN B a ON ...` 歧义列抛 `AmbiguousColumn`。
  2. **Green**: 规划阶段收集所有表列别名映射，歧义列立即报错。
  3. **Refactor**: 提取 `_build_column_map` 辅助。
  4. **Verify**: 限定列正确解析；无限定歧义列报错；无歧义无限定列正常。
  5. **Commit**: `feat(J3): qualified column resolution + AmbiguousColumn detection`.

### T-J3.2 — JOIN 列类型兼容性校验

- **Files**: `Modify: tinydb/executor/join.py`
- **TDD 5 步**:
  1. **Red**: 测试 INT 列与 TEXT 列等值连接抛 `TypeMismatch`。
  2. **Green**: 规划阶段校验 ON 条件两端列类型兼容（遵循 v0.1 类型规则）。
  3. **Refactor**: 复用 `tinydb.types` 的类型兼容判断。
  4. **Verify**: INT=TEXT 报错；INT=FLOAT 允许；TEXT=TEXT 允许。
  5. **Commit**: `feat(J3): join column type compatibility check`.

### T-J3.3 — executor __init__ 分派 EXPLAIN

- **Files**: `Modify: tinydb/executor/__init__.py`
- **TDD 5 步**:
  1. **Red**: 测试 `Executor.execute("EXPLAIN SELECT ...")` 返回计划 dict 列表，不执行查询。
  2. **Green**: `_dispatch` 新增 `ast.Explain` 分支，调用 `IndexPlanner` + `exec_explain`。
  3. **Refactor**: 提取 `exec_explain(stmt, planner, catalog) -> list[dict]`。
  4. **Verify**: EXPLAIN 返回结构化计划；不修改数据库状态。
  5. **Commit**: `feat(J3): EXPLAIN statement returns plan tree`.

### T-J3.4 — JOIN 全场景测试覆盖

- **Files**: `Modify: tests/unit/test_join_query.py`
- **TDD**: 补全 REQ-JQ-001..012 全部场景（链式 JOIN、别名、限定列、WHERE/ORDER/LIMIT 组合、空表、类型错误）。
- **Commit**: `test(J3): full JOIN scenario coverage (REQ-JQ-001..012)`.

---

## Batch C1 — 锁基础设施

Depends on: 无

### T-C1.1 — 新建 lock.py 实现 RWLock + FileLock

- **Files**: `Create: tinydb/lock.py`
- **接口产出**: `RWLock`、`FileLock`、`DatabaseBusy`
- **TDD 5 步**:
  1. **Red**: 测试多线程并发读不阻塞、写阻塞其他读写、超时抛 `DatabaseBusy`。
  2. **Green**: 实现 `RWLock`（`threading.Lock` + `Condition`，写者优先）；实现 `FileLock`（`fcntl.flock`）；实现 `DatabaseBusy(TinyDBError)`。
  3. **Refactor**: 提取 `_LockContext` 支持 `with lock.read():` / `with lock.write():` 上下文协议。
  4. **Verify**: 并发读吞吐 > 串行；写互斥；超时正确。
  5. **Commit**: `feat(C1): RWLock + FileLock + DatabaseBusy exception`.

### T-C1.2 — Database 集成锁生命周期

- **Files**: `Modify: tinydb/database.py`
- **TDD 5 步**:
  1. **Red**: 测试 `Database(path, lock_timeout=1.0)` 打开后 lock 在 close 时释放。
  2. **Green**: `__init__` 新增 `lock_timeout`/`readonly` 参数；打开时获取 FileLock；close 时释放。
  3. **Refactor**: 提取 `_acquire_file_lock` / `_release_file_lock`。
  4. **Verify**: close 释放文件锁（第二个进程可打开）；readonly=True 获共享锁。
  5. **Commit**: `feat(C1): Database integrates lock lifecycle (lock_timeout, readonly)`.

---

## Batch C2 — 多事务 + 快照读 + catalog 一致性

Depends on: C1

### T-C2.1 — TxManager 多事务 ID 字典

- **Files**: `Modify: tinydb/tx.py`
- **接口产出**: `TxManager._txs: dict[int, _TxState]`
- **TDD 5 步**:
  1. **Red**: 测试两连接各 BEGIN 得不同 tx_id；各自 COMMIT 互不干扰。
  2. **Green**: `_tx` → `_txs: dict`；`begin` 分配新 id；`commit`/`rollback` 按键操作。
  3. **Refactor**: 提取 `_active_tx_for_connection`（按连接标识，可选）。
  4. **Verify**: 同连接嵌套 BEGIN 仍抛 TransactionAlreadyActive；多连接并发正常。
  5. **Commit**: `feat(C2): TxManager supports multi-transaction IDs`.

### T-C2.2 — 快照读 + catalog 一致性

- **Files**: `Modify: tinydb/database.py`, `tinydb/executor/catalog.py`
- **TDD 5 步**:
  1. **Red**: 测试读连接 BEGIN 后，写连接提交 DDL，读连接看不到新表。
  2. **Green**: 读锁获取时记录 catalog 版本；写连接提交 DDL 后递增版本并刷新缓存。
  3. **Refactor**: 提取 `_CatalogSnapshot` 轻量封装。
  4. **Verify**: 快照隔离正确；新读者看到最新 DDL。
  5. **Commit**: `feat(C2): snapshot read + catalog cache coherence`.

### T-C2.3 — 并发全场景测试

- **Files**: `Modify: tests/unit/test_concurrency.py`
- **TDD**: 覆盖 REQ-CC-001..009（读写锁、快照读、文件锁、超时、close 释放、多事务、catalog 一致性）。
- **Commit**: `test(C2): full concurrency scenario coverage (REQ-CC-001..009)`.

---

## Batch CL1 — CLI 增强

Depends: 无（.explain 消费 J2 的 IndexPlanner，但可用 stub 占位先开发，W4 集成时切换真实 planner）

### T-CL1.1 — readline + 多行 + 历史

- **Files**: `Modify: tinydb/cli.py`
- **TDD 5 步**:
  1. **Red**: 测试 REPL 在无 readline 时降级并打印一次警告。
  2. **Green**: 顶层 `try: import readline`；`_readline_ok` 标志；`~/.tinydb_history` 持久化。
  3. **Refactor**: 提取 `_setup_readline(history_path)` 函数。
  4. **Verify**: 有 readline 时历史可用；无 readline 时降级不崩溃。
  5. **Commit**: `feat(CL1): readline line editing + history + graceful degradation`.

### T-CL1.2 — pygments 语法高亮

- **Files**: `Modify: tinydb/cli.py`, `Modify: pyproject.toml`
- **TDD 5 步**:
  1. **Red**: 测试有 pygments 时输入关键词带 ANSI 颜色；无 pygments 时降级。
  2. **Green**: 懒加载 pygments；`--color on|off|auto` 参数；`.mode color on|off`。
  3. **Refactor**: 提取 `_highlight_sql(sql) -> str`。
  4. **Verify**: 颜色模式切换正确；无 pygments 降级不崩溃。
  5. **Commit**: `feat(CL1): pygments syntax highlighting (optional, lazy-loaded)`.

### T-CL1.3 — .explain 命令

- **Files**: `Modify: tinydb/cli.py`
- **TDD 5 步**:
  1. **Red**: 测试 `.explain SELECT ...` 输出缩进计划树且不执行查询。
  2. **Green**: `_handle_dot_command` 新增 `.explain` 分支，调用 `db._executor` 的 EXPLAIN 路径，渲染缩进树。
  3. **Refactor**: 提取 `_render_plan_tree(plan: list[dict]) -> str`。
  4. **Verify**: .explain 不修改数据；计划树格式正确。
  **Commit**: `feat(CL1): .explain command renders query plan tree`.

### T-CL1.4 — .mode/.timer/.width/.nullvalue + 多格式渲染

- **Files**: `Modify: tinydb/cli.py`
- **TDD 5 步**:
  1. **Red**: 测试 `.mode csv` 输出 CSV；`.timer on` 输出耗时；`.width 10` 截断；`.nullvalue NULL` 显示。
  2. **Green**: 实现 4 个 dot-commands；`_execute_one` 按 mode 分派到 `_print_table`/`_print_csv`/`_print_json`。
  3. **Refactor**: 提取 `_Renderer` 注册表（mode → render 函数）。
  4. **Verify**: 各模式输出正确；默认模式与 v0.1 一致。
  5. **Commit**: `feat(CL1): .mode/.timer/.width/.nullvalue dot-commands + multi-format render`.

### T-CL1.5 — CLI 增强全场景测试

- **Files**: `Create: tests/unit/test_cli_enhanced.py`, `Create: tests/e2e/test_join_cli_e2e.py`
- **TDD**: 覆盖 REQ-CE-001..012（含降级路径、各 dot-commands、--color、向后兼容）。
- **Commit**: `test(CL1): full CLI enhanced coverage (REQ-CE-001..012)`.

---

## Batch INT — 集成 + Spec 合并

Depends on: W1(J1..J3 绿), W2(C1..C2 绿), W3(CL1 绿)

### T-INT.1 — 三路合入 main + 冲突解决

- **Files**: 无独立文件（合并操作）
- **步骤**:
  1. 各 worktree 分支 rebase 到最新 main。
  2. `git merge feature/v0.2-join` → `feature/v0.2-concurrency` → `feature/v0.2-cli`（或 rebase 后 fast-forward）。
  3. 解决冲突（`pyproject.toml`、`database.py`、`cli.py`、`ast.py` 可能重叠）。
  4. 完整回归 + 覆盖率 + ruff/mypy。
- **Verify**: 227+ 原有测试 + 新增测试全绿；覆盖率 ≥80%。
- **Commit**: `chore(INT): merge join/concurrency/cli worktrees into main`.

### T-INT.2 — .explain 接入真实 planner

- **Files**: `Modify: tinydb/cli.py`
- **步骤**: CL1 的 .explain 若用 stub 占位，此时接入 J2 的真实 IndexPlanner。
- **Verify**: .explain 输出真实代价估算。
- **Commit**: `fix(INT): .explain wired to real IndexPlanner`.

### T-INT.3 — Spec 合并入specs/ 主基线

- **Files**: `Create: specs/*/spec.md`（从 changes/tinydb-v0.2/specs/ 合并）
- **步骤**:
  1. 在仓库根创建 `specs/` 目录。
  2. 将 v0.1-redo specs（归档后）与 v0.2 specs 合并，解决 REQ 编号冲突（v0.1 用 REQ-TS/SE/BT/TM/SP/QE/CR/DB，v0.2 用 REQ-JQ/EP/CC/CE，无冲突）。
  3. 更新 `.spec-superflow.yaml` `spec_merged: true`。
- **Verify**: `specs/` 下 12 个能力域 spec 齐全（8 v0.1 + 4 v0.2）。
- **Commit**: `chore(INT): merge v0.2 delta specs into specs/ main baseline`.

### T-INT.4 — v0.2 发布审计（DP-7）

- **Files**: `.spec-superflow.yaml`, `docs/roadmap.md`, `README.md`
- **步骤**:
  1. 运行完整回归 + 覆盖率 + ruff/mypy。
  2. 更新 `docs/roadmap.md`：v0.2 项标记完成，v0.3 候选更新。
  3. 更新 `README.md`：新增 JOIN / 并发 / CLI 功能说明。
  4. `.spec-superflow.yaml` → `state: closing`。
- **Verify**: DP-7 审计清单通过。
- **Commit**: `chore: v0.2 release — spec merged, roadmap/README updated, closing`.

---

## 跨批次验收门（Cross-cutting Acceptance Gates）

- [ ] Batch J1, J2, J3, C1, C2, CL1 全部完成；commit 在 DP-0 约束可追溯。
- [ ] 三路 worktree 各自绿 test 后合入 main。
- [ ] `pytest --cov=tinydb --cov-fail-under=80` 通过；整体覆盖率 ≥90%。
- [ ] `ruff check tinydb tests` 零错误；`mypy tinydb` 零错误。
- [ ] 并发测试在 CI 连续 3 次无 flake（RWLock/FileLock 时序敏感）。
- [ ] E2E 全部通过（含 JOIN + .explain REPL 驱动）。
- [ ] `ssf validate changes/tinydb-v0.2` 通过（若 ssf CLI 可用）。
- [ ] `.spec-superflow.yaml` 显示 `state: closing`、`spec_merged: true`。
- [ ] `specs/` 主基线含 12 个能力域 spec（8 v0.1 + 4 v0.2）。
- [ ] v0.1 数据库文件可由 v0.2 直接打开（向后兼容）。
