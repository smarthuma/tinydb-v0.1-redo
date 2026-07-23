# TinyDB v0.1-redo

用于学习数据库内部原理的**嵌入式关系型 Python 数据库**。

这是原 v0.1 的**从零重置版**：补齐 33 项 REWRITE-PENDING、按能力拆分模块、新增
`Database` 包装层与 `transaction()` 上下文管理器，并把流程纪律（实质 review、
ruff / mypy 门禁、覆盖率 ≥85%）落到交付链中。

## 定位

- Python 3.10+；运行时仅依赖标准库。
- 嵌入式、单连接模型；用于教学，不追求生产级吞吐。
- 当前处于 Alpha 阶段，优先正确性、可读性与规格可追溯性。

## 快速开始

```bash
# 安装（开发模式）
python3 -m venv .venv
.venv/bin/python -m pip install -e ".[dev]"

# 启动 REPL
.venv/bin/python -m tinydb.cli my.db
```

### Python API

```python
from tinydb import Database

with Database("my.db") as db:
    db.execute("CREATE TABLE users (id INT PRIMARY KEY, name TEXT NOT NULL);")
    db.execute("INSERT INTO users (id, name) VALUES (1, 'alice');")
    db.execute("INSERT INTO users (id, name) VALUES (2, 'bob');")

    rows = db.execute("SELECT * FROM users ORDER BY id;")
    print(rows)  # [{'id': 1, 'name': 'alice'}, {'id': 2, 'name': 'bob'}]

    # 事务
    with db.transaction():
        db.execute("INSERT INTO users (id, name) VALUES (3, 'charlie');")
```

### REPL 示例

```
$ .venv/bin/python -m tinydb.cli my.db
TinyDB 0.1.0. Type .help for help.
tinydb> CREATE TABLE users (id INT, name TEXT);
OK
tinydb> INSERT INTO users (id, name) VALUES (1, 'alice');
1 row inserted
tinydb> SELECT * FROM users;
id | name
---+------
1  | alice
tinydb> .tables
users
tinydb> .schema users
CREATE TABLE users (id INT, name TEXT);
tinydb> .exit
```

## 范围（v0.1）

- INT / FLOAT / TEXT / BOOL 类型系统 + NULL + 强制规则
- 4096 字节定长页 + 单文件持久化 + LRU 缓冲池
- WAL-based ACID + CHECKPOINT
- B+ Tree 索引（split / merge / redistribute）
- SQL 词法 / 语法分析（DDL / DML / 谓词 / 聚合 / 事务控制）
- Query Executor（CREATE / DROP / INSERT / SELECT / UPDATE / DELETE）
- CLI / REPL（dot-commands、多行输入、stdin 批处理）
- Database 包装层 + `transaction()` 上下文管理器

## 范围外

多表 JOIN、并发控制、ALTER TABLE、视图、触发器、外键、网络服务。

## 已知限制

- 单页堆（每表约 100 行上限，v0.2 扩展多页）
- INT 值 0 与 NULL 在存储层不可区分（使用 NULL  sentinel）
- 词法分析器不支持负数字面量
- 事务回滚使用页快照（非 WAL undo）
- 单连接单事务（无并发）

## 文档

- 架构：`docs/architecture.md`
- 路线图：`docs/roadmap.md`

## 测试

```bash
.venv/bin/python -m pytest tests/ -q
.venv/bin/python -m pytest --cov=tinydb --cov-report=term-missing tests/
.venv/bin/python -m pytest -m bench tests/bench/  # 性能基准（非阻塞）
```
