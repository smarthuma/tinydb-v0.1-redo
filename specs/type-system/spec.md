## Purpose

The Type System capability defines the four supported column types (INT, FLOAT, TEXT, BOOL), their on-disk encodings, the coercion and comparison rules, and the exception hierarchy used across the engine. It also owns the single error-formatting entry point `tinydb.errors.format`.

## ADDED Requirements

### Requirement: INT storage

A column declared INT MUST accept Python `int` values in the signed 64-bit range `[-2^63, 2^63 - 1]`. The on-disk encoding MUST be little-endian two's-complement int64.

#### Scenario: round-trip INT

- **WHEN** the value `-1234567890` is stored in an INT column and then read back
- **THEN** the read value equals `-1234567890` exactly (no float precision loss).

#### Scenario: out-of-range value rejected

- **WHEN** the value `2**63` is inserted into an INT column
- **THEN** the executor raises `IntegerOverflow(value=2**63, max=2**63 - 1)`.

### Requirement: FLOAT storage

A column declared FLOAT MUST accept Python `float` values and store them as IEEE-754 binary64.

#### Scenario: round-trip FLOAT

- **WHEN** the value `3.141592653589793` is stored in a FLOAT column and then read back
- **THEN** the read value equals `3.141592653589793` within the IEEE-754 binary64 round-trip guarantee.

### Requirement: TEXT storage

A column declared TEXT MUST accept Python `str` values and store them as UTF-8 bytes with a length prefix. Empty strings MUST be accepted.

#### Scenario: round-trip non-ASCII TEXT

- **WHEN** the value `'你好, tinydb 🚀'` is stored in a TEXT column and then read back
- **THEN** the read value equals the original `str` exactly.

#### Scenario: empty string is allowed

- **WHEN** the value `''` is stored in a TEXT column
- **THEN** the read value is `''` and no error is raised.

### Requirement: BOOL storage

A column declared BOOL MUST accept only Python `bool` values (`True` and `False`). Any other type, including the integers `0` and `1`, MUST be rejected.

#### Scenario: numeric 0/1 is rejected as BOOL

- **WHEN** the value `0` (a Python `int`) is inserted into a BOOL column
- **THEN** the executor raises `TypeMismatch(column, expected='BOOL', got='INT')`.

#### Scenario: True/False round-trip

- **WHEN** the values `True` and `False` are stored in BOOL columns
- **THEN** reading them back yields exactly `True` and `False`.

### Requirement: NULL handling

A column declared without `NOT NULL` MUST accept SQL `NULL`. Reading a NULL column MUST yield Python `None`.

#### Scenario: NULL round-trip

- **WHEN** a row with `name=NULL` is inserted into a nullable column
- **THEN** `SELECT name FROM t;` returns `None`.

### Requirement: Implicit coercion rules

The executor MUST apply the following coercion rules on insert:

- An INT column MUST accept `bool`, mapping `False` to `0` and `True` to `1`.
- All other cross-type inserts (e.g., a TEXT column receiving an `int`, or an INT column receiving a `str`) MUST be rejected with `TypeMismatch`.

#### Scenario: bool coerced into INT

- **WHEN** the value `True` is inserted into an INT column
- **THEN** the stored value is `1` and no error is raised.

#### Scenario: int rejected for TEXT

- **WHEN** the value `42` (a Python `int`) is inserted into a TEXT column
- **THEN** the executor raises `TypeMismatch(column, expected='TEXT', got='INT')`.

### Requirement: Comparison semantics

WHERE-clause comparisons MUST respect column types: INT and FLOAT use numeric ordering, TEXT uses byte-wise UTF-8 codepoint ordering, and BOOL uses `False < True`. Comparing NULL with any operator MUST yield `NULL`, meaning the row is excluded from the result.

#### Scenario: NULL is excluded from WHERE comparisons

- **WHEN** a row has `age=NULL` and the query is `SELECT * FROM t WHERE age = NULL;`
- **THEN** the row is excluded. (The correct form is `age IS NULL`.)

### Requirement: Exception hierarchy

The system MUST expose a single base `TinyDBError(Exception)` and concrete subclasses: `ParseError`, `TypeMismatch`, `UniqueViolation`, `NotNullViolation`, `TableNotFound`, `UnsafeDeleteWithoutWhere`, `IntegerOverflow`, `TransactionAlreadyActive`, `PageCorrupt`, `TransactionLogCorrupt`. Each subclass MUST carry the structured fields its name implies (e.g. `TypeMismatch(column, expected, got)`).

#### Scenario: catch by base class

- **WHEN** any engine error is raised
- **THEN** `except TinyDBError` catches it, and `err.__class__.__name__` identifies the specific subclass.

### Requirement: Single error-formatting entry point

The system MUST expose `tinydb.errors.format(exc: BaseException) -> str` as the single, centralized entry point for turning any exception into a human-readable one-line message. CLI and REPL MUST route all error output through this function; application code MUST NOT hand-format `f"{e}"` or `f"{e}\n"` at multiple call sites.

#### Scenario: format produces a stable one-line string

- **WHEN** `format(TypeMismatch(column='age', expected='INT', got='TEXT'))` is called
- **THEN** the result is a single line containing `age`, `INT`, and `TEXT`, with no trailing newline.

#### Scenario: CLI uses format for all errors

- **WHEN** the REPL catches any exception and prints it
- **THEN** the printed string is exactly `format(exc)` and no other code path in `cli.py` formats errors independently.
