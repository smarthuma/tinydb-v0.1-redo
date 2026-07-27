## Purpose

The CLI Enhanced capability improves the interactive REPL experience with line editing, syntax highlighting, execution plan inspection, and additional dot-commands. It modifies `tinydb/cli.py` and adds optional dependencies (`pygments`, `readline`). It is ADDED in v0.2 and is the user-visible layer over the `execution-plan` capability.

## ADDED Requirements

### Requirement: readline line editing and history

The REPL MUST use the standard library `readline` module (Unix) to provide line editing, history navigation (Up/Down), and persistent history saved to `~/.tinydb_history` across sessions. When `readline` is unavailable (e.g., native Windows without `pyreadline3`), the REPL MUST degrade gracefully to the v0.1 bare `input()` behavior with a one-time warning.

#### scenario: history persists across sessions

- **WHEN** a user types a query, exits the REPL, and starts a new session
- **THEN** pressing Up in the new session recalls the previous session's query from `~/.tinydb_history`.

#### scenario: graceful degradation without readline

- **WHEN** `import readline` fails on the current platform
- **THEN** the REPL prints a one-time warning ("readline unavailable: line editing disabled") and falls back to `input()`.

### Requirement: multiline SQL continuation

The REPL MUST support multi-line SQL input: a line that does not end with `;` is accumulated into a buffer, and the prompt changes to a continuation prompt (e.g., `   ...> `) until a line ending with `;` is entered. This matches v0.1 behavior and MUST be preserved; readline history MUST store the complete multi-line statement as one entry.

#### scenario: multi-line statement recalled as one entry

- **WHEN** a user enters a 3-line SELECT and presses Up later
- **THEN** all 3 lines are recalled together (joined) as a single history entry.

### Requirement: syntax highlighting with pygments

The REPL MUST highlight SQL keywords, strings, numbers, and comments using the `pygments` library when available. Highlighting MUST be toggleable via `.mode color on|off` and the `--color on|off|auto` CLI flag. When `pygments` is not installed, the REPL MUST degrade gracefully (no color) and inform the user once.

#### scenario: keywords highlighted when pygments available

- **WHEN** pygments is installed and color mode is on
- **THEN** typing `SELECT name FROM users` shows `SELECT` and `FROM` in a distinct color.

#### scenario: graceful degradation without pygments

- **WHEN** `import pygments` fails
- **THEN** the REPL prints a one-time notice ("pygments not installed: syntax coloring disabled") and proceeds without color.

#### scenario: --color off disables highlighting

- **WHEN** starting `tinydb test.db --color off`
- **THEN** no ANSI color codes are emitted regardless of pygments availability.

### Requirement: .explain command

The REPL MUST support `.explain <SQL>` which plans the SQL statement and prints the execution plan tree (indented, with node types and estimated costs) WITHOUT executing the query. `.explain` MUST also accept the SQL without the dot-command prefix when prefixed with `EXPLAIN`.

#### scenario: .explain prints plan tree

- **WHEN** entering `.explain SELECT * FROM users WHERE id = 42`
- **THEN** the output is an indented plan tree such as:
  ```
  Project [name, age, email]
    IndexScan users (id = 42) [estimated_rows: 1, cost: 3]
  ```

#### scenario: .explain on join shows join node

- **WHEN** entering `.explain SELECT * FROM A INNER JOIN B ON A.id = B.id`
- **THEN** the output contains a `NestedLoopJoin` or `HashJoin` node with its children.

#### scenario: .explain does not execute the query

- **WHEN** entering `.explain DELETE FROM users WHERE id = 1`
- **THEN** the plan is printed and NO rows are deleted.

### Requirement: .mode command

The REPL MUST support `.mode <format>` where `format` is one of `table` (default ASCII table), `csv` (comma-separated), `json` (one JSON object per line), or `color` (toggle syntax highlighting). The mode persists for the session.

#### scenario: .mode csv changes output format

- **WHEN** entering `.mode csv` then `SELECT * FROM users`
- **THEN** the result is printed as comma-separated values with a header row.

#### scenario: .mode json outputs JSON lines

- **WHEN** entering `.mode json` then `SELECT name, age FROM users`
- **THEN** each row is printed as `{"name": "...", "age": ...}`.

### Requirement: .timer command

The REPL MUST support `.timer on|off`. When on, each query's wall-clock execution time is printed after the result in milliseconds.

#### scenario: .timer on prints elapsed time

- **WHEN** entering `.timer on` then `SELECT count(*) FROM users`
- **THEN** the result is followed by a line like `Time: 12.3 ms`.

### Requirement: .width command

The REPL MUST support `.width <n>` to set the maximum column width for table rendering (default 30). Values wider than `n` are truncated with `...`.

#### scenario: .width truncates long values

- **WHEN** entering `.width 10` then `SELECT name FROM users` where a name is 20 chars
- **THEN** the displayed value is truncated to 10 characters with `...` appended.

### Requirement: .nullvalue command

The REPL MUST support `.nullvalue <text>` to set the display text for NULL values (default empty string).

#### scenario: .nullvalue changes NULL display

- **WHEN** entering `.nullvalue NULL` then `SELECT name FROM users WHERE name IS NULL`
- **THEN** the NULL cell prints as `NULL` instead of empty.

### Requirement: --color CLI flag

The `tinydb` CLI MUST accept `--color on|off|auto` (default `auto`: color when stdout is a tty AND pygments is available). The flag controls initial color mode for the session.

#### scenario: --color off in pipeline

- **WHEN** running `tinydb test.db --color off < queries.sql`
- **THEN** no ANSI codes are emitted (safe for piping).

### Requirement: result format backward compatibility

When no `.mode` is set and no `--color` flag is given, the default output format MUST remain the v0.1 ASCII table format. Existing tests against `_print_table` MUST continue to pass unchanged.

#### scenario: default output unchanged

- **WHEN** running a SELECT in a fresh REPL with no mode changes
- **THEN** the output is the same ASCII table format as v0.1-redo.

## MODIFIED Requirements

### Requirement: main() signature (modified)

The `main(argv, stdin, stdout, stderr)` signature MUST be retained. The internal `_build_parser` MUST add the `--color` argument. The `_run_repl` function MUST accept and pass the initial color mode. Existing tests calling `main([...], stdin=..., stdout=...)` MUST continue to work.

#### scenario: existing main() call unchanged

- **WHEN** calling `main(["test.db"], stdin=StringIO(".exit\n"), stdout=buf)`
- **THEN** the REPL starts and exits cleanly, as in v0.1.

### Requirement: _execute_one output format (modified)

`_execute_one` MUST consult the current `.mode` setting and dispatch to the appropriate renderer (table / csv / json). The default renderer MUST be the existing `_print_table`. This is an internal refactor; the public behavior is unchanged unless `.mode` is set.

#### scenario: default render path unchanged

- **WHEN** no `.mode` has been set
- **THEN** `_execute_one` calls `_print_table` exactly as in v0.1.
