# 技术设计：tinydb v0.1-redo

## 上下文（Context）

### 当前状态

- 仓库 `/home/wfj/新建文件夹/开发tinydb-重置版/` 当前**不含任何实现代码**：仅有 `CLAUDE.md`、`REWRITE-PENDING.md`、`tinydb-proposal.md`、`开发回忆录-从0到1做tinydb.md`，以及 `changes/tinydb-v0.1-redo/.spec-superflow.yaml`。
- 原始 v0.1 的实现与归档制品位于**另一个仓库** `/home/wfj/新建文件夹/开发tinydb/`（含 `changes/archive/tinydb-v0.1/`、`docs/`、`README.md`）。本重置版是**从零构建**，但设计决策（D1..D8 / R1..R8）以归档版为起点，按需调整。
- 无迁移、无遗留存储格式、无并发用户。

### 约束条件（来自 DP-0 与用户决策）

- **Python 3.10+** 运行时；包本身仅依赖标准库（零第三方运行时依赖）。
- **单文件持久化**：一个 `.db` 文件持有数据、catalog、索引；WAL 为兄弟文件 `<path>-wal`。
- **B+ Tree 索引**：默认 order 64，10k 行树高 2–3；支持 split / merge / redistribute。
- **WAL-based ACID**：`Wal.replay()` 必须在 `FileStore.open` 时调用（3.1 关闭）。
- **覆盖率硬门槛 ≥80%**（`pyproject.toml` `fail_under=80`），v0.1-redo 目标 ≥90%。
- **ruff + mypy 零错误**作为提交前门禁（6.1 / 6.2 关闭）。
- **git + spec-superflow 纪律**：完整走 DP-0..DP-7；每个 wave 出 ≥30 行实质 review（1.1 关闭）。
- **Database 包装层纳入**（用户决策）：`Database` 类 + `transaction()` 上下文管理器 + `__init__.py` 重导出。

### 利益相关者

- **开发者自身**：通过造轮子学习数据库内部原理。
- **未来贡献者 / 教学读者**：把代码当教材，可读性与正确性同等重要。
- **Spec 驱动 agent**（spec-writer / build-executor / code-reviewer / release-archivist）：需要每个决策显式、可发现。

## 目标（Goals）

1. **正确性**：`specs/*/spec.md` 中每个 SHALL/MUST 都被满足，且可通过 pytest 场景验证。
2. **教学可读性**：每文件 ≤ 400 行；每个概念一个命名良好的类或函数；模块与能力一一对应。
3. **可组合性**：层间（parser → AST → executor → storage / index / tx / types）通过类型化 Python 对象通信，不退化为字符串字典。
4. **可恢复性**：任意两次操作之间发生 kill -9，数据库状态等价于"所有已提交事务已应用"。
5. **可操作性**：CLI/REPL 行为可预测——错误不崩溃 REPL、多行输入可用、stdin 批处理确定性退出码。
6. **可测试性**：≥80% 行覆盖率（硬门），目标 ≥90%；E2E 覆盖每个 CLI/REPL 需求；无真实时钟 / 网络依赖。
7. **可追溯性**：每条代码变更可追溯到 spec 场景；每个 spec 场景至少一个测试；`.spec-superflow.yaml` 记录全部 7 个 DP。
8. **公共 API 稳定性**：`Database` 包装层 + `__init__.py` 重导出为用户提供稳定入口，底层 `Executor` 仍保留供高级用户。

## 非目标（Non-Goals）

- 多表 JOIN、并发控制、ALTER TABLE、视图、触发器、外键、网络服务。
- 双人 review 互检（仅作为建议记录，不强制）。
- 重新生成 `decision-point-audit.md`（决策：删除该文件，仅保留 `.spec-superflow.yaml` 为真值）。
- 推送 / 打标签（仅记录决策）。
- 改变页头、WAL 记录、B+ Tree 节点、catalog 的二进制布局（避免迁移成本）。

## 决策（Decisions）

### 决策 D1：包布局 — 按能力拆分的扁平 `tinydb/` 树

- **选择**：一个 Python 包 `tinydb/`，子模块与能力一一对应：
  - `parser/` 子包（`lexer.py`、`ast.py`、`ddl_parser.py`、`dml_parser.py`、`predicate.py`、`tx_control.py`、`__init__.py`）
  - `executor/` 子包（`catalog.py`、`dml.py`、`ddl.py`、`select.py`、`aggregate.py`、`index_plan.py`、`checkpoint.py`、`__init__.py`）
  - 顶层模块：`types.py`、`errors.py`、`storage.py`、`heap.py`、`row_layout.py`、`catalog_codec.py`、`index.py`、`wal.py`、`tx.py`、`database.py`、`cli.py`、`__init__.py`
- **理由**：扁平树让导入路径显而易见（`from tinydb.heap import Heap`）；每文件 ≤ 400 行（2.1 关闭）；pytest 可按镜像树发现测试。
- **考虑的替代方案**：
  - 单文件 `tinydb.py` — 拒绝，会膨胀到 1000+ 行，破坏分层。
  - 命名空间包跨多个顶层名（`tinydb_parser`、`tinydb_storage`）— 拒绝，拆分公共 API。

### 决策 D2：页格式 — 4096 字节默认、小端、结构化头部

- **选择**：每页固定 4096 字节（可配 512–65536），8 字节头部 `[page_id u32 | page_type u8 | lsn u32]`，其余为页体。多字节字段小端。
- **理由**：4 KiB 匹配 SQLite 默认，平衡 I/O 效率与堆碎片；小端是 x86/ARM 主流约定。
- **考虑的替代方案**：
  - 变长页 — 拒绝，固定大小简化缓冲池数学与空闲页查找。
  - 大端 — 拒绝，目标架构无实际收益。

### 决策 D3：B+ Tree 参数 — order 64，leaf/internal split / merge / redistribute

- **选择**：B+ Tree 默认 order 64（每节点最多 63 key、64 子指针）。溢出时 split；underflow 时 merge 或 redistribute。key 与子指针同页存储，仅当单值超页体时才退化为 overflow 页。
- **理由**：order 64 + 8 字节 key + 8 字节 rowid，每叶约 250 条目，10k 行树高 2。split / merge / redistribute 实现与测试都直接。
- **考虑的替代方案**：
  - order 16 — 拒绝，10k 行树高 4，页数翻倍。
  - 无重平衡（懒删除）— 拒绝，违反搜索性质，查找退化。

### 决策 D4：WAL 格式 — 仅追加、长度前缀记录、页写前刷盘

- **选择**：每条 WAL 记录 `[len u32 | lsn u32 | page_id u32 | page_type u8 | before_image | after_image | checksum u32]`，追加写入 `<file>-wal`。`commit` 记录 `[len u32 | 'COMMIT' | tx_id u64 | checksum]` 终止事务。
- **理由**：仅追加 WAL 让 crash recovery 单向前向扫描；长度前缀让恢复可跳过损坏记录；checksum 检测 torn write。before/after image 让 undo（回滚）与 redo（重做）都廉价。
- **考虑的替代方案**：
  - 影子分页 — 拒绝，复杂化缓冲池、写放大翻倍。
  - 逻辑 WAL（仅操作，不存页镜像）— 拒绝，引擎足够小，页镜像 WAL 更简单、易测。

### 决策 D5：Catalog 在首页（page 1）

- **选择**：首页（page id 1）持有 catalog：`(table_name, schema, root_data_page_id, root_index_page_ids)` 列表。小文件阶段空闲页列表也放此处；增长后转 `SYSTEM` 页链。
- **理由**：catalog 与文件头共置，open 时单页读取；schema 位置确定。
- **考虑的替代方案**：
  - catalog 作 B+ Tree — 拒绝，v0.1 表数量上限几十，过度设计。
  - 独立 `<file>-catalog` 文件 — 拒绝，违反单文件持久化约束。

### 决策 D6：单连接事务序列化，无锁管理器

- **选择**：每个数据库文件同时仅一个活跃事务。第二个 `BEGIN` 抛 `TransactionAlreadyActive`。无锁管理器、无死锁检测、无 MVCC。
- **理由**：匹配 proposal"范围外：并发控制"，让事务管理器 ≤ 300 行。
- **考虑的替代方案**：
  - 读写锁 — 拒绝，v0.1 过度设计。
  - 乐观 MVCC — 拒绝，需多版本页存储，复杂化 WAL。

### 决策 D7：AST 用 frozen dataclass，不用 dict

- **选择**：每个 SQL 节点是 `@dataclass(frozen=True)`（`CreateTable`、`Select`、`BinaryOp` 等）。Visitor 携带 `Database` / `Executor` 引用，通过类型化方法签名调用下层。
- **理由**：dataclass 免费获得 `__eq__` / `__repr__`，parser 与 executor 测试 trivial；mypy 在 CI 捕获接线错误。
- **考虑的替代方案**：
  - `TypedDict` / 纯 `dict` — 拒绝，字段名 typo 仅运行时暴露。
  - `attrs` / `pydantic` — 拒绝，v0.1 坚持 stdlib。

### 决策 D8：错误为小异常层次 + 单一格式化入口

- **选择**：单一基类 `TinyDBError(Exception)` + 具体子类（`ParseError`、`TypeMismatch`、`UniqueViolation`、`NotNullViolation`、`TableNotFound`、`UnsafeDeleteWithoutWhere`、`IntegerOverflow`、`TransactionAlreadyActive`、`PageCorrupt`、`TransactionLogCorrupt`）。新增 `tinydb.errors.format(exc) -> str` 作为唯一错误格式化入口（2.5 关闭）。
- **理由**：调用方可 catch `TinyDBError` 表"任意 DB 问题"，或 catch 子类做精确处理。REPL 原样打印 `format(exc)`；批处理退出非零。单一格式化入口消除 executor / cli / wal 多处手工拼串。
- **考虑的替代方案**：
  - 返回结果即错误 — 拒绝，不与 `try/except` 组合。
  - 单一字符串错误码 — 拒绝，丢失类型信息。

### 决策 D9：Database 包装层封装 Executor 生命周期

- **选择**：`Database(path, page_size=4096, wal_path=None)` 在 `__init__` 中构造 `FileStore` / `BufferPool` / `WAL` / `Executor`，持有它们的引用。`execute(sql)` 解析 + 执行 + 归一化返回。`transaction()` 返回上下文管理器。`close()` 逆序释放（WAL flush → bufferpool flush → fsync → fd close）。
- **理由**：把"可靠关闭"与"事务块"封装到一个类里，CLI 与终端用户不必手动管理 4 个底层对象；底层 `Executor.open()` 仍保留供高级用户。
- **考虑的替代方案**：
  - 把 `Database` 做成 `Executor` 子类 — 拒绝，继承暴露太多内部方法，违反封装。
  - 把 `Database` 做成自由函数集合 — 拒绝，无法持有资源状态，无法可靠关闭。

### 决策 D10：`__init__.py` 重导出 + `__all__`

- **选择**：`tinydb/__init__.py` 导入并重导出 `Database`、`TinyDBError` 及全部异常子类，声明 `__all__`。
- **理由**：为用户提供稳定、简短的导入路径（`from tinydb import Database`）；`__all__` 明确公共边界，便于 IDE 补全与 `import *`。
- **考虑的替代方案**：
  - 空 `__init__.py` — 拒绝，当前现状，正是 4.3 / 4.6 要关闭的问题。
  - 重导出 `Executor` 等底层类 — 拒绝，v0.1-redo 公共 API 以 `Database` 为入口，底层类通过 `tinydb.executor` 显式导入。

## 风险与权衡（Risks And Trade-Offs）

- **风险 R1**：存储引擎 bug 可静默损坏 `.db` 文件。**缓解**：每页读验证头部 magic 与 checksum；WAL recovery 对坏 checksum 大声失败。**权衡**：checksum 带来约 3% 吞吐开销。

- **风险 R2**：B+ Tree split/merge/redistribute 是最易出 bug 的路径。**缓解**：每个操作独立 pytest 文件，含手工构造树（3 / 7 / 31 / 255 节点）+ 随机化性质测试（insert N 随机 key、delete 全部、re-insert、与 `SortedDict` oracle 对比）。**权衡**：约 25% 测试套件是索引测试。

- **风险 R3**：单文件 WAL 在无 CHECKPOINT 时无限增长。**缓解**：v0.1-redo 交付 `CHECKPOINT` SQL，flush 后 truncate WAL。**权衡**：`CHECKPOINT` 单线程、锁文件，对嵌入式使用可接受。

- **风险 R4**：Parser 错误恢复浅——多语句脚本中间语法错误会中止后续。**缓解**：REPL 仅接受单语句，故仅 stdin 批处理受影响；批处理文档化"fail fast"语义。

- **风险 R5**：80% 覆盖率由 CI 强制，但不保证变异分。**缓解**：code review（skill: `spec-superflow:code-reviewer`）显式检查空 `except:`、未测错误路径、仅 happy-path 的断言。**权衡**：v0.1-redo 目标 ≥90% 以留余量。

- **风险 R6**：CLI REPL 用 `input()`，对 pytest 不友好。**缓解**：REPL 从任意 `Readable` 流读取（默认 `sys.stdin`，测试可注入），`tests/e2e/test_cli_repl.py` 通过 `subprocess` 驱动。

- **风险 R7**：`0` / `1` 被 BOOL 拒绝，对 MySQL/Postgres 用户反直觉。**缓解**：README 文档化，`TypeMismatch` 带 hint 建议显式 cast。**权衡**：严格类型带来小成本。

- **风险 R8**：无多表查询 / 无 JOIN。**缓解**：DP-0 范围决策；v0.2 可能添加。`Select` AST 已带 `from_tables` 列表，扩展是局部的。

- **风险 R9**：Database 包装层若设计不当，可能泄漏 Executor 内部或重复生命周期逻辑。**缓解**：`Database` 仅持有 4 个底层对象引用，不重复实现 WAL / bufferpool / catalog 逻辑；`close()` 逆序调用各组件的 close/flush。

## 迁移计划（Migration Plan）

- **上线步骤**：本变更从零构建，无旧格式迁移。首次 `git init` 后按 tasks.md 的 Batch 1..N 顺序实现；每 batch 跑聚焦测试 → 完整回归 → 覆盖率 → ruff / mypy。
- **回滚步骤**：每 batch 一个原子 commit；若某 batch 引入回归，`git revert <commit>` 回退到上一 batch。
- **数据迁移**：不适用（无既有用户数据格式）。

## 待明确问题（Open Issues）

- **问题 O1**：10k 性能基准的"非阻塞"具体含义——是否作为 `pytest` 默认收集的一部分，还是标记为 `@pytest.mark.bench` 仅在显式请求时运行？**决策负责人**：build-executor 在 Batch N 实现时与用户确认。
- **问题 O2**：`.pyc` 清理（5.3）与 master ahead 决策（5.4）是否在本次变更中执行，或仅记录？**决策负责人**：仅记录，不执行（范围外）。
