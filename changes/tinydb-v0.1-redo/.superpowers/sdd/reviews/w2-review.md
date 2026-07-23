# W2 Wave Review — Type System + errors.format

> Reviewer: self-review against spec-superflow:code-reviewer checklist
> Date: 2026-07-23
> Wave: W2 (Batch 2 — type-system)
> Verdict: **pass**

## 1. 模块结构 (Module Structure)

- `tinydb/errors.py` 独立承载异常层次 + `format()` 单一入口，符合 REQ-TS-009 与 REWRITE-PENDING 2.5。
- `tinydb/types.py` 承载 `ColumnType` 枚举、编解码、强制、比较，模块职责单一。
- 两个模块均声明 `__all__`，公共边界清晰（REWRITE-PENDING 3.9 部分关闭）。
- 无跨层导入：types.py 仅依赖 errors.py；errors.py 零内部依赖。

**Finding:** 无。

## 2. 命名与注释 (Naming & Comments)

- 异常类名与 spec 一致：`TinyDBError`、`ParseError`、`TypeMismatch`、`UniqueViolation`、`NotNullViolation`、`TableNotFound`、`UnsafeDeleteWithoutWhere`、`IntegerOverflow`、`TransactionAlreadyActive`、`PageCorrupt`、`TransactionLogCorrupt`。
- 编解码函数命名 `encode_int` / `decode_int` 等，成对出现，符合惯例。
- 模块顶部 docstring 标注对应 REQ 编号，便于追溯。

**Finding:** 无命名违规。

## 3. 抽象粒度 (Abstraction Granularity)

- 未引入 helper/base class 用于单次使用。`_SupportsLessThan` 协议仅用于 mypy 静态收窄（`object` 不支持 `<`），属于类型系统需要而非过度抽象。
- `encode` / `decode` 作为统一分派入口，避免调用方到处写 match，合理。

**Finding:** 无。

## 4. 错误路径 (Error Paths)

- `encode_int` 对越界抛 `IntegerOverflow`，对非 int 抛 `TypeMismatch`。
- `encode_float` / `encode_text` / `encode_bool` 对类型不符统一抛 `TypeMismatch`。
- `encode_bool` 显式拒绝 `int`（包括 0/1），通过 `_python_type_name` 优先识别 `bool` 避免 `isinstance(True, int)` 陷阱。
- `format()` 用 `match` 分派，覆盖全部 10 个子类 + 兜底 `TinyDBError` + 通用 `BaseException`，无漏路径。

**Finding:** 无静默吞错。

## 5. 与 D1..D10 对账 (Design Compliance)

- D7（不可变 schema）：W2 不涉及，留待 Batch 8。
- 类型编解码与 design.md 一致：INT little-endian int64、FLOAT IEEE-754 binary64、TEXT u32 长度前缀 + UTF-8、BOOL 单字节。
- `format()` 作为 CLI/REPL 唯一错误出口，符合 REWRITE-PENDING 2.5。

**Finding:** 无设计偏离。

## 6. 复杂度与重复 (Complexity & Duplication)

- `_python_type_name` 集中处理 `bool` 优先于 `int` 的识别顺序，避免在 `encode_int` / `encode_bool` 重复逻辑。
- `format()` 集中处理所有异常消息，无 `f"{e}"` 散落。
- `NULL` sentinel（8 字节全零）在 dispatch `encode`/`decode` 中处理，低层编解码不感知 NULL，职责清晰。

**Finding:** 无重复。

## 7. 测试覆盖 (Test Coverage)

- `test_errors.py`：6 tests — 基类捕获全部子类、`format` 输出含关键字段、单行无换行、未知异常兜底、`__all__` 存在。
- `test_types.py`：21 tests — INT round-trip + 溢出、FLOAT round-trip、TEXT 非 ASCII + 空串、BOOL 拒绝 int + round-trip + 类型保持、统一分派、强制规则（bool→int 允许、int→text 拒绝）、NULL round-trip、NULL 排除、各类型比较语义、`__all__`。
- 门禁：pytest 31 passed ✅ · ruff 零错误 ✅ · mypy strict 零错误 ✅。

**Finding:** 无覆盖盲区。

## 8. 已知限制

- NULL 在纯类型编解码层用 8 字节全零作 sentinel，与 INT 数值 0 碰撞。实际由 Batch 5 行层 null bitmap 区分，类型层仅保证 `decode(encode(None))` 还原为 None。已留注释说明。
