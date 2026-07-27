# TinyDB 路线图

> v0.3 延期项唯一真值源。

## v0.2（当前，Alpha）

在 v0.1 基础上增量加入多表查询、并发控制、CLI 增强：

- **多表 JOIN**：INNER/LEFT JOIN、链式多表、别名、`table.column` 限定列
- **并发控制**：连接级读写锁（RWLock）+ 快照读 + 多进程文件锁（fcntl.flock）+ 多事务 ID
- **CLI 增强**：readline 行编辑/历史、pygments 语法高亮、`.explain` 执行计划、`.mode/.timer/.width/.nullvalue`、`--color`
- **执行计划**：9 种计划节点、代价模型（index vs heap）、EXPLAIN 语句 + 树形输出
- 类型系统（INT/FLOAT/TEXT/BOOL + NULL + 强制规则）
- 存储引擎（4096 字节定长页 + 单文件持久化 + LRU 缓冲池）
- WAL-based ACID + CHECKPOINT
- B+ Tree 索引（split / merge / redistribute）
- SQL 词法 / 语法分析（DDL / DML / 谓词 / 聚合 / 事务控制 / JOIN / EXPLAIN）
- Query Executor（CREATE / DROP / INSERT / SELECT / UPDATE / DELETE / JOIN）
- CLI / REPL（readline、pygments、多行输入、stdin 批处理、执行计划查看）
- Database 包装层 + `transaction()` 上下文管理器 + 锁生命周期

## v0.2 已知限制（可修复）

- 单页堆容量上限（~100 行/表）→ 需多页堆扩展
- INT 值 0 与 NULL 碰撞 → 需独立 NULL bitmap
- 词法分析器不支持负数字面量
- 事务回滚使用页快照 → 需 WAL undo 实现真正回滚
- 无 ALTER TABLE / 视图 / 触发器 / 外键
- 网络服务（客户端-服务器模式）未实现
- HashJoin 已实现但未自动由 planner 选择（始终 NLJ）
- Windows 多进程锁未完整测试（仅文档化 + CI 跳过）

## v0.3（候选，未排期）

- ALTER TABLE
- 视图 / 触发器 / 外键
- 网络服务（客户端-服务器模式）
- 多页堆（突破单表容量限制）
- 独立 NULL bitmap（支持 INT 0 存储）
- WAL undo（真正的事务回滚）
- 查询优化器（基于统计信息的索引选择 + HashJoin 自动选择）
- 预编译语句 / 参数化查询
- RIGHT / FULL OUTER JOIN、CROSS JOIN、USING 语法
- 子查询
