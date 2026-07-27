## Purpose

The Join Query capability extends TinyDB from single-table queries to multi-table INNER JOIN and LEFT JOIN. It modifies the parser to recognize JOIN syntax and the executor to combine rows from multiple tables according to join conditions. This capability is ADDED in v0.2 and builds on the existing single-table `Select` path, which remains backward compatible.

## ADDED Requirements

### Requirement: INNER JOIN two tables

A `SELECT` statement with `table_a INNER JOIN table_b ON condition` MUST return the cross product of both tables filtered by the join condition, containing columns from both tables. The result MUST include only rows where the join condition evaluates to true.

#### Scenario: basic inner join on equality

- **WHEN** executing `SELECT a.name, b.score FROM students AS a INNER JOIN scores AS b ON a.id = b.student_id`
- **THEN** each returned row contains `a.name` and `b.score` for rows where `students.id = scores.student_id`, and rows from `students` with no matching `scores` are excluded.

#### Scenario: inner join with no matches

- **WHEN** no row in `table_b` satisfies the join condition for any row in `table_a`
- **THEN** the result is an empty list.

### Requirement: LEFT JOIN

A `SELECT` statement with `table_a LEFT JOIN table_b ON condition` MUST return all rows from `table_a`, with `table_b` columns filled where the join condition matches and filled with `NULL` where no match exists.

#### Scenario: left join fills NULL for unmatched right rows

- **WHEN** executing `SELECT a.name, b.score FROM students AS a LEFT JOIN scores AS b ON a.id = b.student_id` and a student has no scores
- **THEN** the student row is returned with `b.score IS NULL`.

#### Scenario: left join with all rows matching

- **WHEN** every row in `table_a` has at least one match in `table_b`
- **THEN** the result is equivalent to an INNER JOIN plus any unmatched left rows (none in this case).

### Requirement: multi-table chain JOIN

A `SELECT` statement MUST support chaining two or more JOIN clauses: `A JOIN B ON cond1 JOIN C ON cond2`. Joins MUST be applied left-to-right: `(A ⋈ B) ⋈ C`.

#### Scenario: three-table chain join

- **WHEN** executing `SELECT a.name, b.score, c.grade FROM students a INNER JOIN scores b ON a.id = b.student_id INNER JOIN courses c ON b.course_id = c.id`
- **THEN** the result is computed as `(students ⋈ scores) ⋈ courses`, and each row contains columns from all three tables where both join conditions hold.

### Requirement: table aliases

A `SELECT` statement MUST support table aliases using `[AS] alias` after the table name. Projections and join conditions MUST reference the alias in place of the original table name. When an alias is present, the original table name MUST NOT be visible in the result column names.

#### Scenario: aliased table in projection and condition

- **WHEN** executing `SELECT s.name FROM students AS s WHERE s.id = 1`
- **THEN** the result column is named `name` (not `s.name`), and `s.id` resolves to `students.id`.

#### scenario: alias required when joining a table to itself

- **WHEN** a self-join is attempted without aliases
- **THEN** a `TableNotFound` or ambiguous column error is raised (aliases disambiguate the two instances).

### Requirement: qualified column references

A projection or join condition MUST support qualified columns in the form `table.column` or `alias.column` to disambiguate columns present in multiple tables. An unqualified column present in multiple tables MUST raise an ambiguity error.

#### scenario: qualified column disambiguates shared names

- **WHEN** both `students` and `scores` have a column named `id` and the query is `SELECT a.id, b.id FROM students a INNER JOIN scores b ON a.id = b.student_id`
- **THEN** `a.id` resolves to `students.id` and `b.id` resolves to `scores.id`.

#### scenario: unqualified ambiguous column raises error

- **WHEN** executing `SELECT id FROM students a INNER JOIN scores b ON a.id = b.student_id` (unqualified `id` exists in both tables)
- **THEN** an `AmbiguousColumn` error is raised at parse or planning time.

### Requirement: join condition operators

A join condition MUST support the comparison operators `=`, `>`, `<`, `>=`, `<=`, `<>` and the logical combinators `AND` / `OR`. The join condition MUST reference columns from both joined tables (cross-table condition); same-table conditions belong in `WHERE`.

#### scenario: join with AND condition on two columns

- **WHEN** executing `SELECT * FROM A INNER JOIN B ON A.x = B.x AND A.y = B.y`
- **THEN** only rows where both `A.x = B.x` and `A.y = B.y` are returned.

#### scenario: join with greater-than condition

- **WHEN** executing `SELECT * FROM events e INNER JOIN thresholds t ON e.value > t.min_value`
- **THEN** rows are returned where the event value exceeds the threshold minimum (non-equi join).

### Requirement: combine JOIN with WHERE, ORDER BY, LIMIT

A join query MUST support `WHERE`, `ORDER BY`, `LIMIT`, and `OFFSET` clauses applied after the join. `WHERE` filters the joined result set; `ORDER BY` sorts it; `LIMIT`/`OFFSET` restrict the output.

#### scenario: join with where and order

- **WHEN** executing `SELECT a.name, b.score FROM students a INNER JOIN scores b ON a.id = b.student_id WHERE b.score > 80 ORDER BY b.score DESC LIMIT 10`
- **THEN** only joined rows with `score > 80` are returned, sorted descending by score, capped at 10 rows.

### Requirement: join execution algorithm

The executor MUST implement Nested Loop Join (NLJ) as the default algorithm: for each row of the outer table, scan the inner table for matching rows. An equi-join on an indexed inner column SHOULD use index seek to accelerate the inner scan. A Hash Join MAY be used for key-equi joins when the planner estimates it cheaper.

#### scenario: nested loop join reads inner table per outer row

- **WHEN** executing an inner join with outer table of M rows and inner table of N rows without a usable index
- **THEN** the executor performs M × N row comparisons in the worst case.

#### scenario: index-accelerated inner scan

- **WHEN** the inner table has an index on the join column
- **THEN** the executor uses index seek for each outer row, reducing inner scan to O(log N) per outer row.

### Requirement: join column type compatibility

A join condition that compares columns of incompatible types (e.g., INT column to TEXT column with `=`) MUST raise `TypeMismatch`. Compatible type pairs follow the v0.1 type coercion rules (INT/FLOAT comparable; TEXT only comparable to TEXT).

#### scenario: joining int column to text column

- **WHEN** executing `SELECT * FROM A INNER JOIN B ON A.id = B.name` where `A.id` is INT and `B.name` is TEXT
- **THEN** a `TypeMismatch` error is raised before any rows are returned.

### Requirement: empty table join

A join where either table is empty MUST return an empty result set without error (except LEFT JOIN on an empty left table, which also returns empty).

#### scenario: inner join with empty right table

- **WHEN** executing `SELECT * FROM students INNER JOIN empty_table ON students.id = empty_table.student_id`
- **THEN** the result is an empty list.

## MODIFIED Requirements

### Requirement: Select AST (modified)

The `ast.Select` node MUST retain its existing fields (`projections`, `table`, `where`, `order_by`, `limit`, `offset`, `group_by`) and ADD a `joins: tuple[JoinClause, ...]` field defaulting to `()`. A single-table select produced by the parser MUST have `joins=()`, preserving backward compatibility with all v0.1 code paths.

#### scenario: parsed single-table select has empty joins

- **WHEN** parsing `SELECT * FROM users`
- **THEN** the resulting `Select` node has `table="users"` and `joins=()`.

#### scenario: parsed join select populates joins

- **WHEN** parsing `SELECT * FROM A INNER JOIN B ON A.id = B.id`
- **THEN** the resulting node has `table="A"` and `joins=(JoinClause(kind=INNER, table="B", on=BinaryOp("=", Column("A.id"), Column("B.id"))),)`.

### Requirement: Column AST (modified)

The column reference MUST support an optional table qualifier. This is modeled as a new `QualifiedColumn(table: str | None, name: str)` frozen dataclass, OR by extending `ast.Column` with an optional `table` field. Unqualified columns have `table=None` or use the existing `Column` shape.

#### scenario: qualified column parsed

- **WHEN** parsing `SELECT a.name FROM A a`
- **THEN** the projection contains a qualified column with `table="a"` and `name="name"`.

#### scenario: unqualified column still parsed

- **WHEN** parsing `SELECT name FROM A`
- **THEN** the projection contains a column with `name="name"` and no table qualifier.
