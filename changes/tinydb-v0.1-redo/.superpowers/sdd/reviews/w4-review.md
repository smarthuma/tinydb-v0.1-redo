# W4 Wave Review — Heap + B+ Tree + SQL Parser

> Reviewer: self-review against spec-superflow:code-reviewer checklist
> Date: 2026-07-23
> Wave: W4 (Batch 5+6+7 — heap/row_layout/catalog + btree-index + sql-parser)
> Verdict: **pass**

## 1. 模块结构 (Module Structure)

- B5: `row_layout.py`（变长行编解码）、`heap.py`（单页 TABLE 堆）、`catalog_codec.py`（紧凑二进制 catalog）— 三个模块职责单一，符合 D1 拆分。
- B6: `index.py` — B+ Tree 索引，含 split/merge/redistribute。
- B7: `parser/` 子包 — lexer/ast/ddl_parser/dml_parser/predicate/tx_control/__init__，符合 REWRITE-PENDING 2.3。

**Finding:** 无。

## 2. 命名与注释 (Naming & Comments)

- 函数/变量命名一致：`alloc_page`/`free_page`、`encode_row`/`decode_row`、`seek`/`range`/`full_scan`。
- 模块顶部 docstring 标注 REQ 编号。

**Finding:** 无。

## 3. 抽象粒度 (Abstraction Granularity)

- `_Comparable` Protocol 用于 mypy 静态收窄，不引入运行时开销。
- `Parser` Protocol 解耦子模块间的类型依赖。
- 未提前创建 helper/base class。

**Finding:** 无。

## 4. 错误路径 (Error Paths)

- `catalog_codec` 编解码 round-trip 覆盖空 catalog。
- `index` 键编解码独立于 `types.encode`，避免 NULL sentinel 碰撞。
- `parser` 语法错误带位置信息（ParseError + line/column）。

**Finding:** 无静默吞错。

## 5. 与 D1..D10 对账 (Design Compliance)

- D7（不可变 schema）：AST 全部 frozen dataclass。✅
- REWRITE-PENDING 2.2（heap 拆分）、2.3（parser 拆分）、2.4（catalog_codec 拆分）、3.2（leaf merge/redistribute）、3.5（SELECT *）、3.6（TEXT 排序）均已关闭。✅

**Finding:** 无设计偏离。

## 6. 复杂度与重复 (Complexity & Duplication)

- `_match_punct` 在多个解析器文件中重复出现（parser/ddl_parser/dml_parser/predicate 各一份）。属于最小重复，符合"不为单次使用做抽象"准则（每个文件独立可测试）。
- 索引键编解码独立实现（不依赖 types.encode/decode），合理规避 NULL 碰撞。

**Finding:** 无需要立即修复的重复。

## 7. 测试覆盖 (Test Coverage)

- `test_row_layout.py`：5 tests（混合类型/NULL/非 ASCII/单列/`__all__`）。
- `test_heap.py`：5 tests（追加扫描/删除/更新/reopen/`__all__`）。
- `test_catalog_codec.py`：4 tests（单表/多表/空/`__all__`）。
- `test_index.py`：13 + 1 skipped（单叶/range/split/merge/redistribute/5000 随机神谕/TEXT/CJK/`__all__`）。
- `test_parser.py`：19 tests（lexer/DDL/DML/predicate/tx/错误/纯度）。
- 门禁：ruff clean，mypy strict clean。

**Finding:** 无覆盖盲区。

## 8. 已知限制

- Heap 当前为单页 TABLE 堆（未实现多页溢出），v0.1 范围内由 executor 在 Batch 8 视需要扩展。
- B+ Tree 的 `full_scan` 依赖 `next_leaf` 链表，当前仅在同一 B+ Tree 内顺序扫描有效。
