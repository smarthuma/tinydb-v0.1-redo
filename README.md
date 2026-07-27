# TinyDB v0.2

用于学习数据库内部原理的**嵌入式关系型 Python 数据库**。

在 v0.1-redo 基础上增量加入**多表 JOIN**、**并发控制**、**CLI 增强**与**执行计划可观测性**。

## 定位

- Python 3.10+；运行时仅依赖标准库（`pygments` 为可选 CLI 依赖）。
- 嵌入式、多连接安全（读写锁 + 文件锁）；用于教学，不追求生产级吞吐。
- 当前处于 Alpha 阶段，优先正确性、可读性与规格可追溯性。

## 快速开始

```bash
# 安装（开发模式，含可选 CLI 依赖）
python3 -m venv .venv
.venv/bin/python -m pip install -e ".[dev]"
# 可选：安装 pygments 启用语法高亮
.venv/bin/python -m pip install pygments

# 启动 REPL
.venv/bin/python -m tinydb.cli my.db
```

### Python API

```python
from tinydb import Database

with Database("my.db") as db:
    db.execute("CREATE TABLE users (id INT PRIMARY KEY, name TEXT NOT NULL);")
    db.execute("CREATE TABLE scores (id INT, user_id INT, score INT);")
    db.execute("INSERT INTO users (id, name) VALUES (1, 'alice');")
    db.execute("INSERT INTO scores (id, user_id, score) VALUES (1, 1, 90);")

    # 多表 JOIN
    rows = db.execute(
        "SELECT u.name, s.score FROM users u "
        "INNER JOIN scores s ON u.id = s.user_id "
        "WHERE s.score > 80 ORDER BY s.score DESC;"
    )
    print(rows)  # [{'name': 'alice', 'score': 90}]

    # 查看执行计划
    plan = db.execute("EXPLAIN SELECT * FROM users WHERE id = 1;")
    print(plan)  # [{'node': 'IndexScan', ...}]

    # 事务
    with db.transaction():
        db.execute("INSERT INTO users (id, name) VALUES (2, 'bob');")
```

### REPL 示例

```
$ .venv/bin/python -m tinydb.cli my.db
TinyDB 0.2.0. Type .help for help.
tinydb> CREATE TABLE users (id INT, name TEXT);
OK
tinydb> SELECT u.name FROM users u JOIN scores s ON u.id = s.user_id;
name
-----
alice
tinydb> .explain SELECT * FROM users WHERE id = 1
IndexScan users (id = 1) [estimated_rows: 1, cost: 4.0]
tinydb> .mode csv
tinydb> SELECT * FROM users;
id,name
1,alice
tinydb> .timer on
tinydb> SELECT count(*) FROM users;
count(*)
--------
1
Time: 0.5 ms
tinydb> .exit
```

## 范围（v0.2）

- INT / FLOAT / TEXT / BOOL 类型系统 + NULL + 强制规则
- 4096 字节定长页 + 单文件持久化 + LRU 缓冲池
- WAL-based ACID + CHECKPOINT
- B+ Tree 索引（split / merge / redistribute）
- SQL 词法 / 语法分析（DDL / DML / 谓词 / 聚合 / 事务控制 / JOIN / EXPLAIN）
- Query Executor（CREATE / DROP / INSERT / SELECT / UPDATE / DELETE / JOIN）
- **多表 INNER/LEFT JOIN**（链式、别名、限定列）
- **并发控制**（连接级读写锁 + 快照读 + 多进程文件锁 + 多事务 ID）
- **CLI 增强**（readline、pygments 高亮、`.explain`、`.mode/.timer/.width/.nullvalue`、`--color`）
- **执行计划**（9 种节点、代价模型、EXPLAIN 输出）
- Database 包装层 + `transaction()` 上下文管理器 + 锁生命周期

## 范围外

ALTER TABLE、视图、触发器、外键、网络服务、RIGHT/FULL OUTER JOIN、子查询。

## 已知限制

- 单页堆（每表约 100 行上限，v0.3 扩展多页）
- INT 值 0 与 NULL 在存储层不可区分
- 词法分析器不支持负数字面量
- 事务回滚使用页快照（非 WAL undo）
- HashJoin 已实现但未自动由 planner 选择
- Windows 多进程锁未完整测试

## 文档

- 架构：`docs/architecture.md`
- 路线图：`docs/roadmap.md`
- 规格：`specs/`（12 个能力域）

## 测试

```bash
.venv/bin/python -m pytest tests/ -q
.venv/bin/python -m pytest --cov=tinydb --cov-report=term-missing tests/
.venv/bin/python -m pytest -m bench tests/bench/  # 性能基准（非阻塞）
```

## 致谢

v0.2 基于 v0.1-redo 基线开发，使用 spec-superflow 工作流（SDD 模式，3 worktree 隔离并行开发）。
