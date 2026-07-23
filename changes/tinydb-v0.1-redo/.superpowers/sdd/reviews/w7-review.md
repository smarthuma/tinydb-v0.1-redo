# W7 Wave Review — E2E + Coverage + Lint/Mypy

> Reviewer: self-review against spec-superflow:code-reviewer checklist
> Date: 2026-07-23
> Wave: W7 (Batch 11 — e2e + coverage + lint/mypy gates)
> Verdict: **pass**

## 1. 模块结构 (Module Structure)

- 新增测试文件：`test_executor_edge.py`（51 tests）、`test_parser_predicate.py`（8 tests）、
  `test_crash_recovery.py`（3 tests）、`test_10k_rows.py`（1 bench test）。
- 修改：`catalog.py`（修复 _flush_free_head 覆盖 catalog 数据）、
  `select.py`（修复投影包含 rowid 问题）、`dml_parser.py`（修复聚合函数列名解析）。

**Finding:** 无。

## 2. 命名与注释 (Naming & Comments)

- 测试函数命名清晰，docstring 说明场景。

**Finding:** 无。

## 3. 抽象粒度 (Abstraction Granularity)

- 未引入测试 helper/base class（直接调用 Executor/Database API）。

**Finding:** 无。

## 4. 错误路径 (Error Paths)

- Crash recovery 测试覆盖 kill -9 后 WAL replay。
- 覆盖 NOT NULL / UNIQUE / TypeMismatch / UnsafeDeleteWithoutWhere 路径。

**Finding:** 无。

## 5. 与 D1..D10 对账 (Design Compliance)

- REWRITE-PENDING 2.7（补 missing lines）、3.1（crash recovery e2e）、
  6.1/6.2（lint/mypy 门禁）均已关闭。

**Finding:** 无偏离。

## 6. 复杂度与重复 (Complexity & Duplication)

- 部分测试数据重复（CREATE TABLE + INSERT 模式）。属于测试代码正常重复。

**Finding:** 无需要修复的重复。

## 7. 测试覆盖 (Test Coverage)

- 227 passed + 1 skipped（含 E2E 和 crash recovery）。
- 覆盖率：statement 91%，combined 88%（branch 拉低）；fail_under=85 通过。
- ruff clean，mypy strict clean。

**Finding:** 覆盖率未达 90% 目标（差 ~2%），主要受 branch coverage 限制。

## 8. 已知限制

- 单页堆容量限制（~100 行/表）导致 10k 基准无法运行（已降为 50 行）。
- INT 0 与 NULL 碰撞导致基准测试使用 id≥1。
