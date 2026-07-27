## Purpose

The Execution Plan capability exposes the optimizer's query plan structure and renders it as human-readable output via `EXPLAIN` SQL and the `.explain` REPL command. In v0.1-redo the `IndexPlanner` is a stub that always returns `heap_scan`; this capability extends it to a real cost-based planner with table statistics, index awareness, and join ordering. It is ADDED in v0.2 and consumed by both the executor and the CLI.

## ADDED Requirements

### Requirement: plan node types

The planner MUST produce a tree of plan nodes. Each node MUST be one of the following types, represented as frozen dataclasses in `tinydb/executor/plan_nodes.py`:

- `TableScan(table, estimated_rows)` — full scan of a table's heap.
- `IndexScan(table, column, seek_key, estimated_rows)` — index seek + row fetch.
- `Filter(child, predicate)` — apply a WHERE predicate.
- `NestedLoopJoin(left, right, condition, estimated_rows)` — NLJ of two subtrees.
- `HashJoin(left, right, condition, estimated_rows)` — hash equi-join.
- `Project(child, columns)` — column projection (including Star expansion).
- `Sort(child, keys)` — ORDER BY.
- `Limit(child, limit, offset)` — LIMIT/OFFSET.
- `Aggregate(child, group_by, aggregates)` — GROUP BY + aggregate functions.

#### scenario: simple select produces scan + filter + project

- **WHEN** planning `SELECT name, age FROM users WHERE age > 18`
- **THEN** the plan tree is `Project([name, age], Filter(age > 18, TableScan(users)))`.

#### scenario: join produces join node with two scan children

- **WHEN** planning `SELECT * FROM A INNER JOIN B ON A.id = B.id`
- **THEN** the plan tree contains a `NestedLoopJoin` with `TableScan(A)` and `TableScan(B)` children.

### Requirement: index vs heap scan decision

The planner MUST choose `IndexSeek` over `TableScan` when (a) an index exists on the filtered column, (b) the predicate is an equality or range condition on that column, and (c) the estimated cost of index seek is lower than a full scan. Otherwise it MUST fall back to `TableScan`.

#### scenario: equality on indexed column uses index scan

- **WHEN** `users` has an index on `id` and the query is `SELECT * FROM users WHERE id = 42`
- **THEN** the plan root is `IndexScan(users, id, 42, estimated_rows=1)`.

#### scenario: equality on non-indexed column uses table scan

- **WHEN** `users` has no index on `email` and the query is `SELECT * FROM users WHERE email = 'x'`
- **THEN** the plan root is `TableScan(users)` followed by `Filter(email = 'x')`.

### Requirement: table statistics

The planner MUST estimate row counts from table statistics stored in the catalog: each table's approximate row count is maintained (updated on INSERT/DELETE or via a lightweight `ANALYZE` step). When statistics are missing, the planner MUST assume a default (e.g., 1000 rows) and document the limitation.

#### scenario: planner reads row count from catalog

- **WHEN** the catalog records `users` with `row_count=5000` and the query is `SELECT * FROM users`
- **THEN** the `TableScan(users)` node reports `estimated_rows=5000`.

### Requirement: join ordering

For multi-table joins, the planner MUST order joins as a left-deep tree, starting from the smallest table (by estimated row count) to minimize intermediate result size. The outermost left table is the `FROM` table; subsequent tables are reordered by the planner when safe (preserving semantics for INNER joins).

#### scenario: smaller table placed first for inner join

- **WHEN** planning `SELECT * FROM large INNER JOIN small ON large.id = small.id` with `large` having 10000 rows and `small` having 50 rows
- **THEN** the plan places `small` as the outer (driving) table and `large` as the inner table with index lookup, because reordering an INNER join is semantically safe.

#### scenario: left join preserves left table order

- **WHEN** planning `SELECT * FROM large LEFT JOIN small ON large.id = small.id`
- **THEN** `large` remains the outer table (LEFT JOIN semantics require preserving all left rows), even if `small` is smaller.

### Requirement: EXPLAIN SQL statement

The parser MUST recognize `EXPLAIN <statement>` as a new statement type `ast.Explain(statement)`. The executor MUST plan the inner statement and return the plan tree as a structured result (list of plan-node dicts), NOT execute the query.

#### scenario: explain returns plan without executing

- **WHEN** executing `EXPLAIN SELECT * FROM users WHERE id = 42`
- **THEN** the result is a plan description (e.g., `[{"node": "IndexScan", "table": "users", "column": "id", "key": 42, "estimated_rows": 1}]`) and no rows are read from the heap beyond index traversal.

#### scenario: explain on a join shows join node

- **WHEN** executing `EXPLAIN SELECT * FROM A INNER JOIN B ON A.id = B.id`
- **THEN** the result contains a `NestedLoopJoin` or `HashJoin` node with two children.

### Requirement: plan rendering

The CLI MUST render a plan tree as an indented human-readable string: each node on its own line, children indented by 2 spaces per level, with node type and key attributes (table, column, estimated_rows, condition).

#### scenario: rendered plan is indented tree

- **WHEN** `.explain SELECT * FROM users WHERE id = 42` is issued
- **THEN** the output resembles:
  ```
  Project [name, age, email]
    IndexScan users (id = 42) [estimated_rows: 1]
  ```

### Requirement: cost estimation

Each plan node MUST carry an `estimated_rows` and a numeric `estimated_cost` (abstract units: cost ≈ pages read). The planner MUST compute cost for `TableScan` as the number of data pages, for `IndexScan` as index height + 1 (row fetch), and for joins as outer_rows × inner_cost (NLJ) or outer_rows + inner_rows (Hash Join). These costs drive the index-vs-heap and NLJ-vs-hash decisions.

#### scenario: index scan cheaper than table scan for selective predicate

- **WHEN** a table has 100 pages and the predicate selectivity is 1%
- **THEN** `IndexScan` cost (≈ 3) is lower than `TableScan` cost (100), and the planner picks the index.

## MODIFIED Requirements

### Requirement: IndexPlanner (modified)

The `IndexPlanner` class in `tinydb/executor/index_plan.py` MUST be extended from its v0.1-redo stub. It MUST expose `plan_select(table, joins, where, order_by, limit, offset, group_by) -> PlanNode` returning a full plan tree (not just an `IndexPlan` strategy enum). The old `IndexPlan` dataclass MAY be retained as a deprecated compatibility shim or removed.

#### scenario: planner returns tree for single-table query

- **WHEN** calling `IndexPlanner().plan_select(table="users", joins=[], where=BinaryOp(">", Column("age"), SqlLiteral(18)))`
- **THEN** the result is a `Filter` node wrapping a `TableScan(users)` node.

### Requirement: executor consumes plan tree

The `exec_select` function (or a new `exec_plan` function) MUST execute the plan tree: instantiate the appropriate scan, apply filters, perform joins, and return rows. The existing single-table `exec_select` path MUST remain as a fast path or be refactored to use the plan tree internally.

#### scenario: executor runs plan tree for join

- **WHEN** executing a join query
- **THEN** the executor builds the plan tree via `IndexPlanner`, then walks it to produce result rows, matching the semantics of the v0.1 single-table path.
