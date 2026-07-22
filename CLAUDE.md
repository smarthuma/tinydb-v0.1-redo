# TinyDB 项目指令

> 本文件是项目级补充：项目定位、架构边界、开发环境、测试与质量门禁、提交纪律。
> 通用行为准则（思考先行、精简优先、精准修改、目标驱动）请遵循上级文件 `../CLAUDE.md`。
> Claude Code 在启动时会沿目录层级向上自动加载各级 `CLAUDE.md`，所以上级准则会与本文件一并生效。

## 项目定位

TinyDB 是一个用于学习数据库内部原理的 Python 嵌入式关系型数据库。当前处于 Alpha 阶段，重点是正确性、可读性、规格可追溯性和教学价值，而不是生产级吞吐量。

必须保持的边界：

- Python 3.10+；不要使用只在更高版本可用的语法或标准库 API。
- `tinydb` 运行时只允许依赖 Python 标准库；pytest、pytest-cov、ruff、mypy 仅属于开发依赖。
- 数据库是嵌入式、单连接模型；不要暗示或引入多线程、多进程并发语义。
- 未经规格批准，不要加入 JOIN、网络服务、外键、视图、触发器等范围外能力。

## 事实来源与冲突处理

按以下顺序理解任务，不要用低优先级材料覆盖高优先级事实：

1. 用户当前明确提出并确认的需求。
2. `changes/<change-name>/` 中尚未归档的当前变更制品。
3. `specs/*/spec.md` 中的预期行为和 REQUIREMENT / Scenario。
4. `tests/` 与 `tinydb/` 中的现有可观察行为。
5. `pyproject.toml` 中的构建、依赖和质量工具配置。
6. `README.md`、`docs/` 中的说明性材料。
7. `changes/archive/` 中的历史方案、合同和决策记录。

`changes/archive/` 是只读历史记录，不要为当前任务修改它。历史设计可能包含已延期、已调整或尚未实现的目标，不能直接当作当前实现事实。

当前仓库存在少量已知文档漂移：

- `docs/architecture.md` 的文件树仍描述 `tinydb/__init__.py` 会导出 `Database`，但当前 `tinydb/__init__.py` 为空。
- `README.md` 的 v0.1 范围列表仍提到 `db.transaction()`，但当前实现没有该方法。

遇到这些说法时，以当前源码、测试和下面的库级入口说明为准，不要新增不存在的高层 API。

## 架构边界

数据流保持为：

```text
SQL text
  -> tinydb.parser.lexer        词法分析
  -> tinydb.parser.parser       递归下降解析并生成 AST
  -> tinydb.parser.ast          frozen dataclass AST
  -> tinydb.executor            catalog、heap、DDL/DML、谓词与聚合
       -> tinydb.types          类型编解码和异常层次
       -> tinydb.storage        固定页、文件存储和缓冲池
       -> tinydb.index          B+ Tree
       -> tinydb.tx / wal       事务状态与 WAL
  -> tinydb.cli                 CLI、REPL 和批处理入口
```

核心约束：

- Parser 与 Executor 通过类型化 AST 通信，不要退化为字符串字典或全局状态。
- `tinydb/parser/parser.py` 的解析过程应保持无跨调用状态泄漏。
- 类型错误使用 `tinydb.types` 中的异常层次，不要用随意的字符串错误代替。
- 存储页、catalog、索引节点和 WAL 都是持久化格式。修改二进制布局时，必须明确兼容性影响并补充重开文件、损坏检测或迁移测试。
- 当前库级入口以 `tinydb.executor.Executor.open(...)` 和 `tinydb.parser.parser.parse(...)` 为准；不要假设空的 `tinydb/__init__.py` 已提供高层 `Database` API。

详细模块映射见 `docs/architecture.md`；预期行为见对应的 `specs/*/spec.md`。

## 开发环境

优先使用项目虚拟环境，不要把开发包安装到系统 Python：

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -e ".[dev]"
```

现有 `.venv` 可能只安装了 pytest。执行 lint 或类型检查前，用 `pip show` 探测，缺什么补什么，不要跳过检查并声称通过：

```bash
.venv/bin/python -m pip show ruff mypy pytest-cov
```

常用入口：

```bash
.venv/bin/python -m tinydb.cli sample.db
.venv/bin/python -m pytest tests/ -q
```

## 代码规范

遵循 `pyproject.toml`，不要在代码中自行放宽：

- Ruff 目标版本为 Python 3.10，行宽 100；启用 E、F、W、I、B、UP 规则。
- Mypy 对 `tinydb/` 使用 strict 模式。
- 公共行为错误应抛出明确的 `TinyDBError` 子类；CLI 边界负责把错误转换为稳定输出。
- 文件描述符、Executor、WAL 等资源必须可靠关闭，异常路径也不能泄漏。

通用准则（避免 `Any`、不复述代码、不为单次使用做抽象、修改前先量化成功标准）已在上级 `../CLAUDE.md` 给出，本文件不重复。

## 修改流程

按上级 “Goal-Driven Execution” 把任务变成可验证目标。建议步骤：

1. 找到对应的 `specs/*/spec.md`、实现模块和测试文件。
2. 明确现有行为、目标行为、兼容性影响和范围边界。
3. 先写失败的测试或文档改写目标，再做最小实现。
4. 先运行聚焦测试，再运行完整回归和覆盖率门槛。
5. 行为、CLI、架构或已知限制发生变化时，同步更新 `README.md` 或 `docs/`。

新增能力、改变持久化格式或调整既有 REQUIREMENT 时，应先在 `changes/<change-name>/` 建立当前 Spec Superflow 变更；不要修改已归档的 `changes/archive/tinydb-v0.1/`。当前 `changes/` 只有归档内容；新变更目录需要按任务实际创建。普通的内部重构或不改变规格语义的小型修复不需要伪造新的历史制品。

## 测试映射

修改模块时至少运行对应测试：

| 修改区域 | 聚焦测试 |
|---|---|
| `tinydb/types.py` | `tests/unit/test_types*.py` |
| `tinydb/parser/` | `tests/unit/test_lexer.py`、`test_parser*.py` |
| `tinydb/storage.py` | `tests/unit/test_storage.py` |
| `tinydb/index.py` | `tests/unit/test_index.py`、`test_index_ddl.py` |
| `tinydb/executor.py` | `tests/unit/test_executor*.py` |
| `tinydb/tx.py`、`tinydb/wal.py` | `tests/unit/test_tx_e2e.py`、`test_wal.py` |
| `tinydb/cli.py` | `tests/e2e/test_cli_repl.py` |

测试必须使用 pytest 的临时目录或明确创建的临时文件，不要对用户已有 `.db` 文件运行破坏性测试。测试结束后应关闭数据库资源。当前 `.gitignore` 没有忽略 `*.db` / `*.db-wal`，因此更要使用 `tmp_path` 并在结束前检查 `git status`，不要把本地数据库文件留在仓库根目录，也不要提交 `.coverage`、`htmlcov/`、`.pytest_cache/`、`__pycache__/`、`.pyc` 等生成物。

## 完成前验证

至少执行：

```bash
# 聚焦测试（按修改区域选择）
.venv/bin/python -m pytest <relevant-test-path> -q

# 完整回归
.venv/bin/python -m pytest tests/ -q

# 覆盖率硬门槛
.venv/bin/python -m pytest --cov=tinydb --cov-fail-under=80 tests/

# 静态质量门槛（需要安装 .[dev]）
.venv/bin/python -m ruff check tinydb tests
.venv/bin/python -m mypy tinydb
```

各门禁对应的设计来源是 DP-0：覆盖率 ≥ 80% 由 `pyproject.toml fail_under=80` 强制，Ruff 规则集 E/F/W/I/B/UP 与 mypy strict 在 `pyproject.toml` 同一处声明。如需修改这些数值，先在 `changes/<change-name>/proposal.md` 中明确说明影响范围。

涉及 CLI 时，还应至少实际运行一次临时数据库的 CLI/批处理流程。涉及 storage、index 或 WAL 时，除单元测试外还应验证关闭后重新打开的数据一致性。

只有实际运行且通过的检查才能报告为通过。若命令失败、工具未安装或某项检查被跳过，最终回复必须如实说明。

## 提交与报告纪律

- 开始修改前检查 `git status`，保留用户已有改动，不覆盖、不回滚无关文件。
- 默认不提交、不推送、不创建标签，除非用户明确要求。
- 不修改与任务无关的历史报告或归档制品以制造“全绿”外观。
- 完成时简要列出：变更文件、行为变化、实际运行的验证及仍存在的限制。
