# TinyDB 架构

> W1 占位文件。完整内容在 Batch 12 填充（REWRITE-PENDING 4.2）。

## 数据流

```text
SQL text
  -> tinydb.parser.lexer        词法分析
  -> tinydb.parser              递归下降解析并生成 AST
  -> tinydb.parser.ast          frozen dataclass AST
  -> tinydb.executor            catalog、heap、DDL/DML、谓词与聚合
       -> tinydb.types          类型编解码和异常层次
       -> tinydb.storage        固定页、文件存储和缓冲池
       -> tinydb.index          B+ Tree
       -> tinydb.tx / wal       事务状态与 WAL
  -> tinydb.cli                 CLI、REPL 和批处理入口
```

## 模块布局

详见 `design.md` 的 D1 决策。
