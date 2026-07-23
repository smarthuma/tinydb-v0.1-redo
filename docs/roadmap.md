# TinyDB 路线图

> v0.2 延期项唯一真值源。

## v0.1（当前，Alpha）

嵌入式关系型数据库核心：

- 类型系统（INT/FLOAT/TEXT/BOOL + NULL + 强制规则）
- 存储引擎（4096 字节定长页 + 单文件持久化 + LRU 缓冲池）
- WAL-based ACID + CHECKPOINT
- B+ Tree 索引（split / merge / redistribute）
- SQL 词法 / 语法分析（DDL / DML / 谓词 / 聚合 / 事务控制）
- Query Executor（CREATE / DROP / INSERT / SELECT / UPDATE / DELETE）
- CLI / REPL（dot-commands、多行输入、stdin 批处理）
- Database 包装层 + `transaction()` 上下文管理器

## v0.1 已知限制（可修复）

- 单页堆容量上限（~100 行/表）→ 需多页堆扩展
- INT 值 0 与 NULL 碰撞 → 需独立 NULL bitmap
- 词法分析器不支持负数字面量
- 事务回滚使用页快照 → 需 WAL undo 实现真正回滚
- 单连接单事务 → 无并发

## v0.2（候选，未排期）

- 多表 JOIN
- ALTER TABLE
- 视图 / 触发器 / 外键
- 并发控制（多线程/多进程安全）
- 网络服务（客户端-服务器模式）
- 多页堆（突破单表容量限制）
- 独立 NULL bitmap（支持 INT 0 存储）
- WAL undo（真正的事务回滚）
- 查询优化器（基于统计信息的索引选择）
- 预编译语句 / 参数化查询
