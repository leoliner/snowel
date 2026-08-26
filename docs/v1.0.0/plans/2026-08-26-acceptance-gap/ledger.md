# 验收补丁计划 ledger（2026-08-26-acceptance-gap）

> 归档自 `.superpowers/sdd/2026-08-26-acceptance-gap/progress.md`（live ledger）。计划：同目录 `plan.md`（2026-08-26 批准）。

## 1. 执行总览

| 项 | 值 |
|---|---|
| 分支 | feat/acceptance-gap（worktree `D:\Code\snowel-acceptance-gap`，已删）→ merge --no-ff 回 dev-1.0.0 @ b2022bb |
| 提交链 | 8890660 (T1 beat_merged) → 46a3626 (T2 灵感层) → d503ceb (T3 小模型路由) → 5836880 (T4 后端小修包) → 5292b60 (T5 前端小修包) → e11e14a (终审修复波) |
| 模式 | Subagent-Driven，5 任务，每任务两席评审（spec+quality）全 Approved，修环 0 轮 |
| 测试基线 | 后端 252→**264**、前端 vitest 71→**74**、`npm run build` 绿；合并后在主仓库全量复跑确认 |
| 验收缺口闭环 | TC-ON-08（beat_merged + 伏笔迁移 + story_order 漂移顺带修复）、TC-ON-12（Inspiration 节点 + DERIVED_FROM）、TC-RT-05（低重要小模型路由 + extract_many）；ON-13/ON-14 弱覆盖补锚 |
| L 项处置 | L20/L21/L22 **关闭**（并入 T4/T5 落地）；L16 保持开放（发版前发布债）；新登记 L23/L24/L25/L26（见 §3） |

## 2. Ruling 裁决记录（决策—理由—若错的成本）

| # | 裁决 | 理由 | 若错的成本 |
|---|---|---|---|
| R1 | beat_merged 载荷自含迁移结果（moved_foreshadows old/new），api 预查、投影按载荷执行 | 设计事件表要求；复盘可读、rebuild 可重放 | 预查与投影不一致则 handler 局部重写 |
| R2 | 灵感原话 = Inspiration 节点（props.inspiration.text），不建独立表 | DERIVED_FROM 天然可连、edges_of 反查免费 | 全文过长则迁旁挂大文本表，投影一处改动 |
| R3 | "批量**或**小模型"取小模型路由承载成本语义；批量 = extract_many 循环便捷入口 | 需求原文是"或"；单章一次调用是抽取提示词结构约束 | 若验收坚持多章单调用，在 extract_many 内聚合提示词 |
| R4 | 重要性标记走事件 chapter_importance_set；config extraction.small_model 默认空 | append-only 铁律；向后兼容 | 无实质风险 |
| R5 | ON-13/ON-14 补锚走行为断言，不为结构性满足造死测试（ON-11 教训） | 弱覆盖最小补法 | — |
| 执行-1 | T4 brief 的"reject_auto 一行 ValueError"诊断被实测推翻——真实崩因是 unpack TypeError/IndexError + 字符串逐字拆分静默放行；改为形状校验 + 全局 400 映射 | 先复现后修；brief 配方对真实崩因无效 | 无（偏离 brief 且更正确，终审确认） |
| 执行-2 | T5 的 onGoGenerate 测试落 App.test.tsx 而非 ProseEditor.test.tsx | ProseEditor 回调用例已存在，真实缺口是 App 接线；App 层断言更强（tab 切换 + 面板挂载） | 无 |
| 执行-3 | L21 只统一门面默认（api.search 20→100），hybrid.py 内部默认 20 保留 | 终审裁定：chat 召回（context.py:78）喂 LLM prompt，20 是有意召回界，100 会撑上下文 → 登记 L26 显式记录 | 若 20 实非有意，一行改 hybrid 默认 + context 显式传参即可 |
| 执行-4 | favicon #E2A03F == tailwind accent token（控制器核对闭环） | 评审无法爬库验证的 ⚠️ 项 | 纯视觉偏移 |

## 3. 挂账表

| L 项 | 内容 | 状态 | 承接 |
|---|---|---|---|
| L16 | Windows python.org 构建扩展加载崩 + core/壳同步发包 | **开放**（不携带，环境/发布债） | 发版前单独处置 |
| L20 | daemon 心跳线程泄漏（良性） | **关闭**（T4：conftest session 清理，零生产改动） | — |
| L21 | api.search 门面 limit=20 与 fts 100 不一致 | **关闭**（T4：门面统一 100） | 深度口径见 L26 |
| L22 | 六项终审 triage park 小修 | **关闭**（favicon/reject_auto/onGoGenerate/chat to_thread/ForeshadowMap/sse 全落地，T4+T5+修复波） | — |
| L23 | beat_deleted 事件（D6 后半）+ 拍 active 语义（merge 两端 active 校验、valid_until_beat 迁移、重复合并语义） | **新登记** | v1.1 |
| L24 | TC-EX-01~05 扩展包机制（E4 全域） | **新登记** | v1.1 |
| L25 | 灵感层/拍合并壳端暴露（MCP advanced / Web / CLI）；暴露时 merge_beats 预查须移入事务（TOCTOU：SQLite 不防双进程，web 暴露后可达）+ derived_from 两阶段崩溃窗口补 L6 式恢复 + derive_from 校验自动化测试 | **新登记** | v1.1 |
| L26 | chat 召回界 hybrid 默认 20 是**有意上限**（喂 prompt 的召回深度），非 bug；勿再报"与 fts 100 不一致" | **新登记**（显式记录） | — |

顺带 minor 池（v1.1 顺手，不单开）：reject_auto 注释"500"应为"200"（e11e14a nit）；Viz.test 硬编码 320/3.5；inspirations() 无 ORDER BY；save_inspiration("") 空文本无校验；extract_many 异常类型并入消息；conftest 模块级 web_server 导入使 core-only 会话依赖 fastapi（try/except 条件化）；T3"config 已设+未标 low"组合测试；derive_from 重复 id 平行边。

## 4. 终审修复波

- 终审（全分支 d534300..5292b60）：**With fixes**——R1-R5 全兑现、四新事件 kind rebuild 可复现、三缺口门面级断言确认、测试独立复跑绿。Important×2。
- 修复 e11e14a：reject_auto 元素类型校验（str 二元组，短路安全）+ 非字符串测试例 ×2；tests/README flow 行登记 test_inspiration（TC-ON-12 + ON-14 补锚）。
- 定向复审：两 finding 全 ADDRESSED，无新破坏。终审 triage 表已并入 §3（L23-L26）。

## 5. 覆盖口径备忘

黑盒用例实际表格为 **75 例 / 9 域**（8+16+10+8+8+6+6+8+5），历史文档"66 例/10 域"口径过时。本计划补齐 3 例真缺口后：**70 例有测试锚 + 5 例计划内豁免（TC-EX，挂 L24 排 v1.1）= 75 例全处置**。AGENTS.md 与 handoff 口径已同步更新。
