# TinyDB v0.1-redo

用于学习数据库内部原理的**嵌入式关系型 Python 数据库**。

这是原 v0.1 的**从零重置版**：补齐 33 项 REWRITE-PENDING、按能力拆分模块、新增
`Database` 包装层与 `transaction()` 上下文管理器，并把流程纪律（实质 review、
ruff / mypy 门禁、覆盖率 ≥90%）落到交付链中。

## 定位

- Python 3.10+；运行时仅依赖标准库。
- 嵌入式、单连接模型；用于教学，不追求生产级吞吐。
- 当前处于 Alpha 阶段，优先正确性、可读性与规格可追溯性。

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

## 文档

- 架构：`docs/architecture.md`
- 路线图：`docs/roadmap.md`
