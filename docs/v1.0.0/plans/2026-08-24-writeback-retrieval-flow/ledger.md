# SDD ledger — plan: docs/v1.0.0/plans/2026-08-24-writeback-retrieval-flow/plan.md

> 2026-08-24 执行完毕归档（前半 T1–T12；T13–T17 生成环与 T18 壳接线经用户裁决延后，待前半质量验收后执行）。live ledger 原位于 worktree `.superpowers/sdd/plan/progress.md`（git 忽略），收尾时迁移为本文件随 git 提交。

## 执行总览

- 分支 feat/writeback-retrieval-flow（worktree 隔离，已合并清理），20 提交 2529907..fe7203d + merge 94dd484，12 任务 + 终审修复波，合并后全量 121/121 通过（基线 69 + 新增 52）。
- 任务评审：T1/T2/T5/T7/T9/T12 一次通过；T3/T4/T6/T8/T10/T11 各 1 轮修环（共 8 findings，全部 ADDRESSED 复审闭环）。终审（全分支）判 With fixes：3 Important（存量库兼容崩、README 登记违约、死亡过滤测试掩蔽）+ 3 顺手项，修复波 fe7203d 一次解决，定向复审 6/6 ADDRESSED。
- 交付：挂账修复 L1/L2/L5 + 测试基建；config KV + 嵌入 provider（确定性默认 + fastembed extras）；正文镜像与文件优先对账（D8/C1）；FTS5+jieba（nodes+prose）；sqlite-vec + per-project 重建（C6）；compose_context 三策略 + retrieval_audit + hybrid（E3）；llm backend 协议 + litellm 适配 + rewrite_query 桩；抽取分级管线（§5.3/D1/忽略修辞/组校验接线）；确认即写文件（C1）；hook 轮询三模式（P4）；appeared→active 物化（D5）+ 偏离报告（C12）；auto 否决 + 轻量反查（C2/C11）。
- 计划级缺陷修正 7 处（Ruling 落盘）；brief 笔误/语法修复 6 处（均以测试为契约）。

## Ruling 裁决记录（决策—理由—若错的成本）

- Ruling: 执行范围 = T1–T12；T18 壳接线整段留后半（not_wired 测试翻转与 generate/rewrite 接线交织，前半单独拆会产生半接线状态）— 若错成本：前半检索/回写能力暂无 MCP 面，验收走 core API。
- Ruling: T9 的 confirm(exclude) 过滤逻辑计划未配测试（消费者 T14 在后半）— 前半执行时补 exclude 过滤测试；若错成本：无。
- Ruling: 本环境 Agent 工具无模型分级参数 — 全部任务统一 general-purpose subagent，评审强度靠 prompt 补偿；若错成本：评审档位低于规约预期，靠两席评审结构对冲。
- Ruling: 计划缺陷——`_prose_event` 共享 handler 读 `payload["hash"]` 但 `prose_external_change` 键为 `new_hash` — 最小修正 `payload.get("hash") or payload["new_hash"]`（以简报测试为契约）；若错成本：无。
- Ruling: 计划缺陷——write_prose 后 prose 列恒空/残留、rebuild 后无法重灌（断供 T4/T5/T8 镜像全文消费链）— ①write_prose 事务内 apply 后 UPDATE 灌 prose；②reconcile 增"哈希一致但 prose 空→从文件重灌（不追加事件）"分支；若错成本：无。
- Ruling: 计划缺陷——write_prose/reconcile 的 apply→fts.refresh 时 prose 尚未水化，prose_fts 落后一拍（brief 测试手动 refresh 掩盖；T6/T12 消费面漏检）— 全部水化路径同事务补 fts.refresh；若错成本：无（含每次 apply 双重 refresh 的冗余工作，接受）。
- Ruling: 计划缺陷 ×2——TODO 排除未覆盖 fallback_recall；foreshadows 未做"未回收"过滤 — fallback 双剔除（refs+text）；payoff_beat 同 death 过滤模式；"∩ 相关"v1 不做；若错成本：低。
- Ruling: 计划缺陷——裸 json.loads 对真实 LLM 输出不可靠 — _parse_response 剥围栏+ValueError 包装+facts 键校验；顺带补 force-high 路径测试；若错成本：无。
- Ruling: 计划固有窗口——api.confirm 两事务：queue.confirm 先提交、write_prose 后执行，文件写失败终态=已确认+无文件+无登记，重试被状态机拒 — 接受（文件 IO 与库事务无法原子、反向更糟、失败响亮、单机触发面极窄）；恢复入口挂 L6 后半壳接线；若错成本：极端时序下人工恢复一章节。
- Ruling: 计划缺陷——hook 守护线程 tick() 无异常防护，单章抽取异常杀死轮询（评审"每轮重报"不成立：reconcile 登记先于 extract）— 守卫移入 tick() 仅包每章 extract，异常→ch["extract_error"] 继续余章；若错成本：无。
- Ruling: 计划缺陷——全 high 章节 appeared 不物化（D5 激活洞，numeric_high 默认开致战斗/终章易全 high）— extract_facts 载荷+confirm 事件载荷带 appeared（投影器零改动）；零事实章维持接受边；若错成本：无。
- 终审 Ruling（随修复波落地）：api.open 补 db.migrate（存量库兼容，评审实证崩）；tests/README §1/§3 登记；死亡过滤测试去掩蔽（场景 characters 补 dead1）；hybrid vec 路径滤 active=0；_node_section 删死参数；vec.ensure 短路 DDL 但保留扩展加载（vec0 按连接注册，字面"表存在即全跳"会崩重开项目——修复者实证偏离，正确）。

## Parked（挂账，下游计划 preflight 必须携带）

| # | 问题 | 位置 | 承接计划 | 处理要求 |
|---|---|---|---|---|
| L4（继承） | `descendants` 无边时效过滤、kinds 未消费 | storage/queries.py | 级联检查计划（继承未变） | 依赖反查时按需补 |
| **L6（新）** | confirm 两事务窗口：文件写失败后提案已确认但无文件无哈希登记，重试被状态机拒 | api.py confirm | **后半壳接线（T18 面）** | 提供恢复入口（re-register 命令或 MCP action） |
| **L7（新）** | 心跳线程 renew 抛异常（sqlite busy 等）静默杀循环且 readonly 不翻转——L5 修的是返回 False 路径，异常路径仍开双写窗口 | shell/project.py | **后半（多端并发接线）必修** | _loop 包 try/except + 失租等效处理 |
| **L8（新）** | rebuild_embeddings 非原子（DELETE 先落盘，中途失败留部分向量+陈旧 built_with） | storage/vec.py | 后半接线层 | 包 db.transaction（两行） |
| **L9（新）** | hook/compose 的 fallback 查询词用章节 id（"ch1"），对召回无意义；"章关键词"本是生成环产物 | retrieval/context.py | **后半 T14 接线时** | fallback 改章关键词或场景卡文本 |
| **L10（新）** | fts.search 的 paragraphs[].text 是分词后空格串，AI 客户端引用提示需按 chapter_id+para_idx 回查原文 | storage/fts.py | **后半 T18 preflight 必带** | 壳接线时回查原文或改返回原段落 |
| **L11（新）** | 零事实章 appeared 丢失（无提案无 auto 事件） | writeback/extract.py | 级联/后续（接受边） | 若激活滞后显著可发空 facts 事件 |
| **L12（新）** | Windows python.org 构建 sqlite3 无 enable_load_extension → api.open AttributeError | storage/vec.py | 发布/文档债 | 打包文档注明需 conda 或自带扩展的构建 |
| L1/L2/L5 | ~~groups 畸形串 / derive 签名 / readonly 翻转~~ | — | **本计划已修复关闭**（T1；L1 并于 T8 接线消费面） | — |
| L3 | ~~api.open 校验~~ | — | 壳计划已关闭 | — |

随行小项（不强制，终审 triage 维持 deferred）：mirror.reconcile 的 project_root 参数未用（绝对路径入事件，项目目录迁移误报 missing_file）；test_fts/test_vec 残留手动 UPDATE（T4 修复后多余）；fts._query_expr 8-token 截断与引号未剥；N+1 族（fts name 回填/alias/appeared/deviation 全表扫）；filterwarnings 按消息前缀；set(exclude) 循环内重建；api.confirm 不存在 pid 抛 TypeError；from_config 非法 mode KeyError；reject_auto 计条目数非命中数；reason=None 无测试；hybrid 并发删除理论性 None 解引用；manual 模式 confirm prose 静默覆盖未对账外部编辑（壳接线 UI 提示）。

## 终审修复波（fe7203d）

- Important：api.open 不 migrate——存量库（旧 schema 子集）首次 confirm/reconcile/config.get 崩（评审用基线 schema 实证复现）——修复：open() 补 db.migrate（幂等）；回归测试 ×2（旧库 open + 旧库 confirm 端到端过 fts.refresh）。
- Important：tests/README §1 未登记 llm/retrieval/writeback 三目录（全局约束违约）、§3 conftest 描述过时——补三行（含黑盒用例反向索引）+ §3 更新。
- Important：TC-RT-03 死亡过滤测试掩蔽（dead1 不在场景 characters，断言恒过）——场景 characters 补 dead1，断言不变，反向验证翻红。
- 顺手：hybrid vec 回填滤 active=0（撤回节点不回流）；_node_section 删 conn 死参数（6 调用点同步）；vec.ensure 短路 DDL（sqlite_master 查 node_vec；扩展加载保留——vec0 按连接注册，评审字面方案会崩重开项目）。
- 定向复审：6/6 ADDRESSED，无新破坏；全量 121/121。

## 后半（T13–T18）执行注意

1. 计划文本中 T9 的 confirm(exclude) 已在前半落地并测试；T14 微节拍组消费时直接可用。
2. T13 flow 状态 / T14 ai_generate / T15 小雪花 / T16 卷展开 / T17 revision 的 brief 代码未受前半修环影响，但 T14 的 compose_context 消费面注意：context.compose_context 签名未变；L9 的 fallback 查询词在 T14 接线时一并修。
3. T18 preflight 必带：L6/L7/L10 + 终审 triage 的"L12 发布债"；not_wired 测试翻转清单见计划 T18 节。
4. worktree 执行时先 `pip install -e . -e ./shell`（新依赖 litellm/jieba/sqlite-vec 已入 pyproject）。
