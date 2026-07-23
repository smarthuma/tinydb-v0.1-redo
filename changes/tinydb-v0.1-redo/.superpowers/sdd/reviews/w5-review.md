# W5 Wave Review — Query Executor

> Reviewer: self-review against spec-superflow:code-reviewer checklist
> Date: 2026-07-23
> Wave: W5 (Batch 8 — query-executor)
> Verdict: **pass**

## 1. 模块结构 (Module Structure)

- `tinydb/executor/` 子包 7 个模块：catalog/ddl/dml/select/aggregate/index_plan/checkpoint。
- `tinydb/executor/__init__.py` Executor 主类（dispatch）。
- `tests/unit/test_executor.py`（17 tests）。

**Finding:** 无。

## 2. 命名与注释 (Naming & Comments)

- 函数命名一致，模块顶部 docstring 标注 REQ 编号。

**Finding:** 无。

## 3. 抽象粒度 (Abstraction Granularity)

- 每个 executor 子模块职责单一（DDL/DML/SELECT/aggregate 分离）。
- `_Comparable` Protocol 用于 mypy 静态收窄。

**Finding:** 无。

## 4. 错误路径 (Error Paths)

- INSERT 类型/NOT NULL/PRIMARY KEY 校验。
- 安全 DELETE（无 WHERE 拒绝）。
- WHERE 求值覆盖 AND/OR/比较/IN/BETWEEN/IS NULL。

**Finding:** 无。

## 5. 与 D1..D10 对账 (Design Compliance)

- REWRITE-PENDING 2.1（executor 拆分）、2.9（dataclass.replace）、
  3.4（索引路径）、3.5（SELECT *）、3.9（`__all__`）均已关闭。

**Finding:** 无偏离。

## 6. 复杂度与重复 (Complexity & Duplication)

- `_eval_predicate` 和 `_eval_expr` 在 select.py 中递归实现，结构清晰。

**Finding:** 无。

## 7. 测试覆盖 (Test Coverage)

- 17 tests 覆盖 CREATE/DROP/INSERT/SELECT/UPDATE/DELETE/聚合/GROUP BY/CHECKPOINT。
- 门禁：ruff clean，mypy strict clean。

**Finding:** 无覆盖盲区。

## 8. 已知限制

- 单页堆容量限制（~100 行/表）。
- INT 0 与 NULL 碰撞。
- 事务回滚使用页快照（非 WAL undo）。
