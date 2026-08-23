# SDD ledger — plan: docs/v1.0.0/plans/2026-08-23-snowel-core.md

> 2026-08-23 执行完毕后按用户指示重建：本文件是该计划执行期 ledger 的持久化重建版（原 ledger 在收尾清理时删除，裁决与遗留问题内容完整迁移至此）。目录被 .gitignore 忽略，随工作区存活；计划文件末节保留指针。

## 执行总览

- 分支 feat/snowel-core（worktree 隔离，已合并清理），12 提交 789846a..6334903，11 任务 + 终审修复波，37/37 测试通过，合并入 dev-1.0.0。
- 各任务均一次通过任务评审（无修环）；终审发现 1 Critical + 1 Important，修复波 6334903 一次解决，定向复审全 ADDRESSED。

## Preflight 裁决

- Ruling: T6 测试断言 flatten 键为 `core_level`（计划原文 `props_core_level` 与实现矛盾）— 若错成本：T6 测试当场失败暴露。
- Ruling: 边有效期契约 = fact 顶层 `valid_from_beat/valid_until_beat`，物化存 `edges.props`，recompute 从 props 读 — 若错成本：T6 端到端失败暴露。
- Ruling: T3 测试数据按计划"执行注意"自洽化（EDGE_FACT 引用）。

## 任务完成记录

- Task 1: complete (789846a..eb43978, review clean) — minor: 未用 import sqlite3；transaction 不支持嵌套
- Task 2: complete (eb43978..0015ab0, review clean) — minor: payload 列未断言
- Task 3: complete (0015ab0..2b27da6, review clean；裁决落地) — minor: 未知 kind 注释与行为不一致；apply 无事务内断言
- Task 4: complete (2b27da6..3c93f37, review clean) — minor: retraction 非法 target 静默落 edges；track_added DO NOTHING
- Task 5: complete (3c93f37..7b062a0, review clean) — minor: 失活节点保留过期 story_order；_revision_applied 对不存在 node 抛 TypeError；双重重算冗余
- Task 6: complete (7b062a0..481ca0c, review clean；实现者补 story_order 谓词修正计划矛盾) — minor: death_beat N+1；flatten 键可覆盖列
- Task 7: complete (481ca0c..7262c5d, review clean；FK 删除顺序裁决) — minor: edges 仅断言计数
- Task 8: complete (7262c5d..d953fe5, review clean；descendants 不含起点以测试语义消解) — minor: 裸 list 返回类型；无边时效过滤
- Task 9: complete (d953fe5..2a93657, review clean；derive 签名按 props 版) — parked 见下
- Task 10: complete (2a93657..16e610d, review clean) — minor: _transition 不存在 id 抛 TypeError；list 遮蔽内建
- Task 11: complete (16e610d..498081b, review clean) — minor: 路径注释；renew/release 不在事务内；⚠️ BEGIN IMMEDIATE 已核实、测试计数 35 已复核
- Final: complete (789846a..6334903, 12 commits, merge-ready)

## Parked（挂账，下游计划 preflight 必须携带）

| # | 问题 | 位置 | 承接计划 | 处理要求 |
|---|---|---|---|---|
| L1 | `groups.validate` 对畸形 `_schema` 版本串（如 `"demo@x"`）抛 ValueError，违背 D3 降级精神 | ontology/groups.py | 接线属性组校验的计划（回写环/级联检查） | 补 try/except，畸形串归入 version_mismatch 警告 |
| L2 | `completeness.derive(props)` 无测试覆盖；Interfaces 文档签名（derive(conn, node_id)）与实现不一致，以实现为准 | ontology/completeness.py | 接线 completeness 的计划 | preflight 强制携带：先补测试、统一签名再接线；active 判定本就属回写环计划 |
| L3 | `api.open(path)` 不校验库文件存在/已迁移 | api.py | MCP/CLI 壳计划 | 壳层启动校验并给可读错误 |
| L4 | `descendants` 不做边时效过滤；kinds 参数未消费 | storage/queries.py | 级联检查计划 | 依赖反查时按需补 |

## 随行小项（无现实触发面，顺手清理，不强制）

- proposal/queue.py：_transition 不存在 id 抛 TypeError 而非 ProposalStateError；list 遮蔽内建名；状态检查在事务外（TOCTOU，租约压制）
- storage/queries.py：裸 list 返回类型；flatten 键可覆盖同名列；death_beat N+1
- storage/projector.py：_retraction 非法 target 静默；_track_added DO NOTHING；_revision_applied 对不存在 node 抛 TypeError；apply 尾部与 handler 双重重算
- 风格：文件首行 `# src/...` 路径注释；renew/release 不在事务内；测试操纵 groups._registered 私有结构

## 终审修复波（6334903）

- Critical：边撤回哨兵 `valid_until=-1` 被 apply 尾部 recompute 重置为 NULL（撤回失效）——修复：recompute 跳过 `valid_until=-1` 的边；回归测试 test_edge_retraction_survives_recompute
- Important：重确认不复活节点——修复：`_upsert_node` ON CONFLICT SET 补 `active=1`；回归测试 test_reconfirmed_node_revived
