# TinyDB 架构

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
  -> tinydb.database            Database 包装层（公共 API）
```

## 模块布局

```
tinydb/
├── __init__.py          # 公共 API 重导出 + __version__
├── database.py          # Database 包装层（execute/transaction/close）
├── errors.py            # TinyDBError 层次 + format() 单一入口
├── types.py             # ColumnType + 编解码 + 强制 + 比较
├── storage.py           # FileStore + BufferPool + Page + PageType
├── index.py             # B+ Tree（seek/range/insert/delete/split/merge）
├── tx.py                # TxManager（BEGIN/COMMIT/ROLLBACK/CHECKPOINT）
├── wal.py               # Wal + WalRecord + replay_wal
├── catalog_codec.py     # TableMeta + encode/decode_catalog
├── row_layout.py        # 行编解码（变长布局）
├── heap.py              # Heap（单页 TABLE 堆）
├── parser/
│   ├── __init__.py      # parse() 公共入口 + Parser 类
│   ├── ast.py           # frozen dataclass AST 节点
│   ├── lexer.py         # tokenize() + Token
│   ├── ddl_parser.py    # CREATE/DROP TABLE
│   ├── dml_parser.py    # INSERT/SELECT/UPDATE/DELETE
│   ├── predicate.py     # WHERE 谓词（AND/OR/BETWEEN/IN/IS NULL）
│   └── tx_control.py    # BEGIN/COMMIT/ROLLBACK
└── executor/
    ├── __init__.py      # Executor 主类（dispatch）
    ├── catalog.py       # Catalog（文件头页持久化）
    ├── ddl.py           # exec_create_table/exec_drop_table
    ├── dml.py           # exec_insert/exec_update/exec_delete
    ├── select.py        # exec_select（投影/WHERE/ORDER BY/LIMIT）
    ├── aggregate.py     # exec_aggregate（COUNT/SUM/AVG + GROUP BY）
    ├── index_plan.py    # IndexPlanner（heap_scan fallback）
    └── checkpoint.py    # exec_checkpoint
```

## Spec → 模块交叉引用

| Spec | 需求 | 主模块 | 测试 |
|------|------|--------|------|
| type-system | REQ-TS-001..009 | `types.py` | `test_types.py` |
| storage-engine | REQ-SE-001..007 | `storage.py` | `test_storage.py` |
| btree-index | REQ-BT-001..009 | `index.py` | `test_index.py` |
| transaction-manager | REQ-TM-001..008 | `tx.py`, `wal.py` | `test_tx.py`, `test_wal.py` |
| sql-parser | REQ-SP-001..007 | `parser/` | `test_parser.py` |
| query-executor | REQ-QE-001..011 | `executor/` | `test_executor.py` |
| cli-repl | REQ-CR-001..008 | `cli.py` | `test_cli_repl.py` |
| database-api | REQ-DB-001..006 | `database.py` | `test_database.py` |

## 关键设计决策

- **D1 模块边界**：parser/executor 子包拆分，单文件模块 ≤400 行。
- **D4 WAL 格式**：magic(8) + length(4) + crc32(4) + body + crc32(4)。
- **D5 Catalog**：存储在文件头页（page 0）body 尾部。
- **D7 不可变 AST**：全部 frozen dataclass；catalog 更新用 `dataclasses.replace`。
- **NULL sentinel**：8 字节全零表示 NULL（INT 值 0 不可存储）。
- **行布局**：`[row_length u32][deleted u1][rowid u64][col_count u16][(len u32 + value) * n]`。
