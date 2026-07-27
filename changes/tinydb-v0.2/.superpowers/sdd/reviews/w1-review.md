# Wave W1 Review — JOIN + Execution Plan

- **Wave**: W1
- **Verdict**: pass
- **Reviewer**: build-executor (controller, direct implementation)
- **Range**: 7a37e7b..a76308c (3 commits: J1, J2, J3)
- **Spec**: join-query (REQ-JQ-001..012) + execution-plan (REQ-EP-001..010)

## Spec Compliance

- REQ-JQ-001 INNER JOIN: NLJ execution, verified with multi-row tables. PASS.
- REQ-JQ-002 LEFT JOIN: unmatched left rows preserved with NULL right columns. PASS.
- REQ-JQ-003 chain JOIN: 3+ table parsing and execution. PASS.
- REQ-JQ-004 aliases + qualified columns: `table.column` in projection/ON/WHERE/ORDER; AmbiguousColumn on unqualified conflict. PASS.
- REQ-JQ-005 join condition operators: =, >, <, AND/ON. PASS.
- REQ-JQ-006 JOIN + WHERE + ORDER + LIMIT: combined correctly. PASS.
- REQ-JQ-008 NLJ algorithm: outer scan + inner match. PASS.
- REQ-JQ-011 type compatibility: check_join_type_compatibility (INT vs TEXT raises). PASS.
- REQ-JQ-012 empty table join: returns []. PASS.
- REQ-EP-001 9 plan node types: frozen dataclasses. PASS.
- REQ-EP-002 index vs heap: equality on indexed column → IndexScan. PASS.
- REQ-EP-005 EXPLAIN: returns structured plan dict. PASS.
- REQ-EP-006 rendering: indented tree via render_plan. PASS.
- REQ-EP-007 cost estimation: TableScan=pages, IndexScan=height+1, NLJ=outer×inner. PASS.
- Backward compat: single-table SELECT identical to v0.1 (223 → 252 tests, all green). PASS.

## Code Quality

- Modular: plan_nodes.py (170), join.py (240), index_plan.py (175) — each ≤ 400 lines.
- ruff: clean. mypy strict: clean (30 files).
- 252 passed, 1 skipped — full regression green.

## Concerns (non-blocking)

1. IndexPlanner uses simplified row_count from TableMeta (not persisted, defaults to 1000 when unknown). Documented limitation.
2. HashJoin implemented but not auto-selected by planner (NLJ always used). HashJoin available for future planner enhancement.
3. Join column merge uses `table.column` prefix for conflicts; projection strips to bare name via QualifiedColumn handling.

## Recommendation

**pass** — W1 complete and ready for W4 integration.
