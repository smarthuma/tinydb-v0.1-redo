# tinydb v0.1 重做待办清单

> 本文件记录当前 `tinydb` v0.1 **应当做但未做** 的事项，作为下一次 v0.1 重做或 v0.2 启动的需求输入。
>
> 整理依据：
> - `changes/archive/tinydb-v0.1/.spec-superflow.yaml`（决策点 8/8）
> - `changes/archive/tinydb-v0.1/.superpowers/sdd/reviews/`（9 份 wave 评审）
> - `changes/archive/tinydb-v0.1/reports/b1-review.md`（唯一实质评审）
> - `changes/archive/tinydb-v0.1/design.md`（D1..D8 / R1..R8）
> - `changes/archive/tinydb-v0.1/CHANGELOG.md`（Known Limitations）
> - 当前源码与 `docs/`、`README.md`、`.gitignore`、`pyproject.toml` 事实校核
> - 实际测试 `194 passed`、覆盖率 83.82%
>
> 状态：未提交，仅作记录用，便于 v0.1 重做时一次性消化。

## 1. 流程与评审

| ID | 类别 | 待办 | 当前现状 | 期望 | 影响 |
|---|---|---|---|---|---|
| 1.1 | 流程 | b2..b9 实质 Code Review | 8 份 review 是 12 行占位（"re-transcribed after revision 2 replan"），零 finding | 每个 wave 出 1 份 ≥ 30 行的实质 review，覆盖：模块结构、命名/注释、抽象粒度、错误路径、与 D1..D8 对账、复杂度与重复 | 高 |
| 1.2 | 流程 | 提交前 lint/mypy | `pyproject.toml` 已声明 ruff 与 mypy，但 `.venv` 未安装、CI 也未跑 | 提交前必跑 `ruff check` 与 `mypy tinydb` 并通过；missing 时必须如实报告，不准以“未安装”跳过 | 高 |
| 1.3 | 流程 | `decision-point-audit.md` 滞后 | 仍显示 5/8 记录，DP-5/6/7 为 "not recorded"；而 `.spec-superflow.yaml` 实际 8/8 | 重新生成 `decision-point-audit.md`，或删除并仅保留 `.spec-superflow.yaml` 为真值 | 中 |
| 1.4 | 流程 | wave 评审 review 模板 | 现模板只要求 "verdict: pass|fail"，没要求 finding 计数与 categories | 加入 severity 表格（Critical/Important/Minor/Suggestion）、REQ-Spec 合规、Design-Compliance、TDD Iron-Law 四段式 | 中 |
| 1.5 | 流程 | 实际 reviewer | b1-review.md 注明 "self-review against spec-superflow:code-reviewer checklist"，其余 8 份连 self-review 都没填 | 至少留 self-review 痕迹（**谁**、**何时**、**按哪个 checklist**），不能"事后补 receipt" | 中 |

## 2. 代码质量与精简化

| ID | 类别 | 待办 | 当前现状 | 期望 | 影响 |
|---|---|---|---|---|---|
| 2.1 | 体量 | `executor.py` 容量预警 | 720 行（v0.1.1）/ 544 statement；v0.2 计划再加 4 项能力（Database 入口、transaction 块、索引路径、CHECKPOINT） | v0.2 启动前先按 D1 拆分（如 `tinydb/executor/{select,update,delete,ddl,index_plan,checkpoint}.py`），每文件 ≤ 400 行 | 高 |
| 2.2 | 抽象 | `executor.py` 内 `_Heap` 单文件 130+ 行 | 编码、扫描、删除、append 全部在 `_Heap` 中 | 拆分为 `heap.py` / `heap_codec.py` / `row_layout.py` | 中 |
| 2.3 | 抽象 | `parser/parser.py` 489 行 | 词法、语法、tx-control、predicates 全部揉在一起 | 按语法/谓词/tx-control 拆出子模块 | 中 |
| 2.4 | 抽象 | `_CatalogCodec.serialize/deserialize` 写在 executor.py | 改 catalog 格式时 executor 也要动 | 把 catalog 编解码独立到 `tinydb/catalog_codec.py` | 中 |
| 2.5 | 重复 | 错误信息在多处手工拼 | 例如 executor / cli / wal 都有 `f"{e}\n"` 类硬拼输出 | 引入 `tinydb.errors.format(e) -> str` 单一入口 | 低 |
| 2.6 | 注释 | 注释密度与 v0.1 现有风格差异 | b1 review 已点出 `types.py` 缺 `__all__` | 公共 API 加 `__all__`，每个模块顶部保留 design 引用块 | 低 |
| 2.7 | 测试 | 8 份 wave review 0 finding 不代表代码无问题 | 例如 `executor.py` 110 missing lines（覆盖率 17% 未触达） | 补 8 份 review 时同步补 missing lines 的单测 | 中 |
| 2.8 | 测试 | `executor_extra.py` 与 `executor.py` 分裂 | 命名暗示主文件是基线，其他是“额外”，不利于维护 | 合并或按子能力拆成 `test_executor_dml.py` / `test_executor_aggregate.py` | 低 |
| 2.9 | 类型 | `tinydb/executor.py` 内部 `object.__setattr__(schema, ...)` | 改了 frozen schema，破坏 D7 不可变约定 | 改成 `dataclass.replace(...)` 或重写 catalog.flush | 中 |

## 3. 设计前瞻与延期项

| ID | 类别 | 待办 | 设计依据 | 期望 | 影响 |
|---|---|---|---|---|---|
| 3.1 | 设计 | `Wal.replay()` 接入 `FileStore.open` | D4 + R3：crash recovery 端到端 | 在 `FileStore.open` 路径中调用 `Wal.replay`，并补 e2e（`kill -9` 重开一致） | 高 |
| 3.2 | 设计 | B+ Tree leaf delete 触发 merge / redistribute | D3：split 已有；merge 缺失 | 实现 underflow → merge/redistribute + 5k 随机 key 神谕测试 | 高 |
| 3.3 | 设计 | `CHECKPOINT` SQL | R3：WAL 可无限增长；`Wal.truncate()` 已实现 | parser 加 `Checkpoint` 语句；executor 接收后 truncate WAL | 高 |
| 3.4 | 设计 | 索引路径接入 executor | D3 + R2 | 增加 `IndexPlanner`/`IndexScan` 代码路径；非索引列继续走 heap 扫描 | 高 |
| 3.5 | 设计 | `SELECT *` 投影 | executor 仅支持显式列 | parser 把 `*` 展开为 schema 全列；或在 executor 顶层做展开 | 中 |
| 3.6 | 设计 | TEXT B+ Tree ordering 测试 | R2 | 测 `'Banana' < 'apple'`（UTF-8 字节序）+ 中文/emoji | 中 |
| 3.7 | 设计 | 10k 行性能基准 | DP-0 范围内未跑 | 加 `tests/bench/test_10k_rows.py`，记录平均/99 分位查询时延 | 中 |
| 3.8 | 设计 | `Database` 包装层 + `db.transaction()` 块 | 当前 `tinydb/__init__.py` 为空；README 提到不存在的方法 | 显式决定：v0.1 不做（保持现状）还是 v0.1 重做时一并做；如做，写在 proposal 与 `__init__.py` | 中 |
| 3.9 | 设计 | 公共 API `__all__` | b1 review 已 Suggestion；其它模块未跟进 | `tinydb/types.py` 外的 8 个模块都补 `__all__` | 低 |

## 4. 文档与一致性

| ID | 类别 | 待办 | 当前现状 | 期望 | 影响 |
|---|---|---|---|---|---|
| 4.1 | 文档 | README 描述与实现不一致 | README 第 99 行写 `db.transaction()`，实现没有 | 二选一：在 v0.1 重做时把 `Database` + `transaction()` 写出来；或者从 README 删掉对应行 | 中 |
| 4.2 | 文档 | `docs/architecture.md` 文件树过时 | 仍描述 `__init__.py re-exports Database, TinyDBError, etc.` | 同步实现：要么补 `__init__.py`，要么改 architecture.md | 中 |
| 4.3 | 文档 | `__init__.py` 为空 | `wc -l tinydb/__init__.py` = 0 | 视决策 3.8：要么重导出 `Executor`、`TinyDBError`、异常子类；要么明示"无公共 re-export" | 中 |
| 4.4 | 文档 | Known Limitations 散落 | CHANGELOG、architecture.md、CLAUDE.md 三处都列了 v0.2 延期项 | 建立 `docs/roadmap.md` 作为唯一真值源，CHANGELOG/architecture.md 链接过去 | 中 |
| 4.5 | 文档 | 设计变更未沉淀 | 实际行为改了（如 SQL 转义、CLI 输入）但 design.md 未同步 | design.md 加 "Changes since v0.1.0" 一节，记录每条偏离的 commit 与原因 | 中 |
| 4.6 | 文档 | `tinydb/__init__.py` 是空文件 | 影响 IDE 自动补全与外部 import | 与 4.3 同处 | 中 |

## 5. 仓库卫生

| ID | 类别 | 待办 | 当前现状 | 期望 | 影响 |
|---|---|---|---|---|---|
| 5.1 | 忽略 | `.gitignore` 缺 `*.db` / `*.db-wal` | 本地 CLI 跑过会留下 `sample.db`、`tx.db` 等 | 仓库根加 `*.db` 与 `*.db-wal` | 高 |
| 5.2 | 忽略 | `.coverage`、`htmlcov/` 已忽略 | OK | 维持 | — |
| 5.3 | 提交纪律 | 跟踪文件含 2 个 `.pyc` | `git ls-files \| grep \.pyc$` 输出 2 项 | `git rm --cached <file>`，并补忽略规则 | 中 |
| 5.4 | 提交纪律 | master ahead origin 1 | `master...origin/master [ahead 1]` | 该 commit 是文档（`开发回忆录`），需决定是否推送 | 低 |

## 6. 静态质量门禁

| ID | 类别 | 待办 | 当前现状 | 期望 | 影响 |
|---|---|---|---|---|---|
| 6.1 | 工具 | `ruff` 未安装 | `.venv/bin/python -m ruff check` → "No module named ruff" | `pip install -e ".[dev]"` 后跑 `ruff check tinydb tests` 直至 0 warning | 高 |
| 6.2 | 工具 | `mypy` 未安装 | `.venv/bin/python -m mypy tinydb` → "No module named mypy" | 同上，跑 `mypy tinydb` 直至 0 error | 高 |
| 6.3 | 工具 | pytest-cov 覆盖率门 | 已过 80%（83.82%） | 维持 ≥ 80%；新增模块不许拉低 | 高 |
| 6.4 | 工具 | coverage 17% 未触达 | executor.py 110 missing lines | 补测试至 90%+（per b1 review 的 100% type-system 标准） | 中 |

## 7. 决策点（DP）层面

| ID | 类别 | 待办 | 备注 |
|---|---|---|---|
| 7.1 | DP | DP-0/1/2/3/4 已留痕；DP-5/6/7 在 yaml 有结果但 audit 报告未刷新 | 重新生成 audit 报告对齐 |
| 7.2 | DP | v0.1 重做时是否走完整 Spec-Superflow（DP-0..DP-7）？ | 用户决策：建议保留完整流程，并要求每个 DP 留 1 份产物 |
| 7.3 | DP | wave 评审是否升级为"双人 review + 一人 approval"？ | 当前 self-review 是合规下限；v0.1 重做时建议加 review 互检 |

## 8. 使用方式（给 v0.1 重做的入口）

重做 v0.1 时建议这样消费本清单：

1. **新建 `changes/tinydb-v0.1-redo/`**（或等价目录），不修改 `archive/tinydb-v0.1/`。
2. 在 `proposal.md` 中显式声明本清单所列 25 项是 v0.1-redo 的 In-Scope（含 1.1-1.5 流程、2.1-2.9 质量、3.1-3.9 设计、4.1-4.6 文档、5.1-5.4 仓库、6.1-6.4 静态门、7.1-7.3 DP）。
3. 把本文件改名为 `changes/tinydb-v0.1-redo/backlog.md`，原文件 `REWRITE-PENDING.md` 删除。
4. 走 DP-0..DP-7 完整流程；本清单逐条 → tasks。
5. 每次 wave review 必须出 ≥ 30 行实质 review（不再用 12 行占位）。
6. v0.1-redo 关闭时把 `execution-contract.md`、`design.md`、9 份 review receipt、8/8 DP 字段全部留齐。

## 9. 统计

- 待办总数：33 条
- 高影响：9 条
- 中影响：18 条
- 低影响：6 条
- 涉及模块：流程 5 / 代码质量 9 / 设计 9 / 文档 6 / 仓库 4 / 工具 4 / DP 3（部分条目跨多类）
- 主要热点：`executor.py`（2.1, 2.2, 2.4, 2.7, 2.9）、`__init__.py` + README + architecture.md（3.8, 4.1, 4.2, 4.3, 4.6）、`.gitignore` 与静态门禁（5.1, 6.1, 6.2, 6.4）。

## 10. 参考引用

- `CLAUDE.md` — 项目级指令
- `README.md` — 用户面文档
- `docs/architecture.md` — 模块映射
- `docs/CHANGELOG.md` — Known Limitations
- `docs/TEST-REPORT.md` — 覆盖率与回归基线
- `changes/archive/tinydb-v0.1/proposal.md` — v0.1 提案
- `changes/archive/tinydb-v0.1/design.md` — D1..D8 / R1..R8
- `changes/archive/tinydb-v0.1/tasks.md` — 9 batch 任务拆分
- `changes/archive/tinydb-v0.1/execution-contract.md` — wave 合同
- `changes/archive/tinydb-v0.1/.spec-superflow.yaml` — 决策点真值
- `changes/archive/tinydb-v0.1/.superpowers/sdd/reviews/` — 9 份 wave 评审
- `changes/archive/tinydb-v0.1/reports/b1-review.md` — 唯一实质评审
