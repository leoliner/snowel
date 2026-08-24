# SDD ledger — plan: docs/v1.0.0/plans/2026-08-24-writeback-retrieval-flow/plan.md

> 2026-08-24/25 两波执行完毕归档：前半 T1–T12（回写环+混合检索）08-24 合入 94dd484；后半 T13–T18（生成环+壳接线）08-25 合入 84e0053。用户裁决分两波放行（前半验收通过后开后半）。live ledger 原位于 worktree `.superpowers/sdd/plan/progress.md`（git 忽略），收尾迁移为本文件随 git 提交。

## 执行总览

- 前半（T1–T12）：20 提交 + merge 94dd484。修环 6 任务共 8 findings；终审 With fixes（存量库兼容崩/README 违约/测试掩蔽 + 3 顺手）修复波 fe7203d 闭环；合入时全量 121/121。
- 后半（T13–T18）：11 提交 + merge 84e0053。T13/T15 一次过，T14/T16/T17/T18 各 1 轮修环（7 findings）；终审 With fixes（1 Critical + 3 Important + 2 Minor）修复波 ae0041e 闭环；合并后全量 **160/160**（项目基线 69 + 新增 91）。
- 交付：挂账修复 L1/L2/L5/L6/L7/L8/L9/L10 全部关闭；config KV + 嵌入 provider（确定性默认 + fastembed extras）；正文镜像与文件优先对账（D8/C1）；FTS5+jieba；sqlite-vec + per-project 重建（C6）；compose_context 三策略 + retrieval_audit + hybrid（E3）；llm backend + litellm + parse_llm_json 共享解析；抽取分级（§5.3/D1/忽略修辞）；确认即写文件（C1）；hook 三模式（P4）；appeared→active（D5）+ 偏离报告（C12）；auto 否决+轻量反查（C2/C11）；flow 状态模型（TC-FL-03）；ai_generate 生成环（E3/D7/11 产物型注册表）；小雪花受限展开（TC-FL-04）；卷首世界状态重放+卷展开（C8/C9）；统一 revision + 提案改写（§5.2/C5 revision 面）；MCP 五面接线（generate/writeback 六动作含 re-register/search/audit/rewrite）+ CLI export。
- 计划级缺陷修正共 11 处（Ruling 全落盘）；brief 笔误/语法修复约 10 处（均以测试为契约）。

## Ruling 裁决记录（决策—理由—若错的成本）

### 前半（T1–T12）

- 执行范围 = T1–T12；T18 壳接线整段留后半（not_wired 翻转与 generate 接线交织，拆开产生半接线状态）— 若错成本：前半能力暂无 MCP 面。
- T9 的 confirm(exclude) 补过滤测试（消费者 T14 在后半）— 若错成本：无。
- 本环境 Agent 工具无模型分级参数 — 统一 general-purpose，评审强度靠 prompt 补偿 — 若错成本：评审档位低于规约，两席评审结构对冲。
- 计划缺陷：`_prose_event` 读 `payload["hash"]` 但 external_change 键为 `new_hash` — `payload.get("hash") or payload["new_hash"]`（测试为契约）。
- 计划缺陷：write_prose 后 prose 列恒空/残留、rebuild 后无法重灌（断供镜像消费链）— write_prose 事务内水化 + reconcile 增"哈希一致但 prose 空→重灌（不追加事件）"分支。
- 计划缺陷：apply→fts.refresh 时 prose 未水化，prose_fts 落后一拍（brief 测试手动 refresh 掩盖）— 全部水化路径同事务补 fts.refresh（双重 refresh 冗余接受）。
- 计划缺陷 ×2：TODO 排除漏 fallback_recall（双剔除 refs+text）；foreshadows 未滤已回收（payoff_beat 同 death 模式）；"∩ 相关"v1 不做。
- 计划缺陷：裸 json.loads 对真实 LLM 输出不可靠 — _parse_response 剥围栏+ValueError+facts 键校验；补 force-high 测试。
- 计划固有窗口：api.confirm 两事务（文件写失败=已确认无文件，重试被拒）— 接受（无法原子/失败响亮/单机触发面窄）；恢复入口挂 L6。
- 计划缺陷：hook 守护线程无异常防护（单章毒死轮询）— 守卫入 tick() 仅包每章 extract，异常→extract_error 继续余章。
- 计划缺陷：全 high 章节 appeared 不物化（numeric_high 默认开，战斗/终章易全 high）— extract_facts 载荷+confirm 事件载荷带 appeared；零事实章接受边。
- 前半终审 Ruling（fe7203d）：api.open 补 db.migrate（存量库崩，实证）；README 登记；死亡过滤测试去掩蔽；hybrid vec 滤 active；_node_section 死参数；vec.ensure 短路 DDL 但保留扩展加载（vec0 按连接注册，字面全跳会崩重开项目）。

### 后半（T13–T18）

- E1：T16 自行给 ai_generate 补"卷首世界状态"prompt 分支（T14 不预埋死代码）— 若错成本：T16 多一轮小改。
- E2：api.confirm 恒返回 int seq（计划文本"返回 dict"与 T17 自身测试矛盾，以测试为契约），cascade 占位入 revision 提案 payload.cascade_hint — 若错成本：无。
- T14 prose payload 契约缝隙 — generate 对 prose 型增补 chapter_id/content（生产端集中）；补 L9 持久测试。
- T16 两缺陷：end 按目标卷 address.volume 截断（Volume 节点新增 address 约定；无 address 回退全图最大——滚动展开场景天然正确）；伏笔过滤复用 unrecovered（提升公共名）。
- T17：_parse_response 迁 llm/ports.parse_llm_json 共用；rewrite 的 facts/appeared 继承原 payload 属保守正确；补 address 判别断言。
- T18 两先在缺陷：MCP confirm 改走 api.confirm 统一编排（绕过则 prose 不写文件、revision 静默丢事件）；reconcile 加 require_write（对账写库不得无租约）。
- 后半终审 Ruling（ae0041e）：①rewrite 对 prose 同步 content（确认写旧文的静默错内容链——generate→rewrite→confirm 已复现）；②LAYERS scenes↔scene 别名映射（层永 todo 卡死）；③ai_generate 改 parse_llm_json（主生成口围栏容忍）+文案中性化；④latest_extract_proposal 门面（壳内领域筛选归零）；⑤默认 backend 统一 ports.get_backend；⑥scene_of_chapter 公有化。

## Parked（挂账，下游计划 preflight 必须携带）

| # | 问题 | 位置 | 承接计划 | 处理要求 |
|---|---|---|---|---|
| L4（继承） | `descendants` 无边时效过滤、kinds 未消费 | storage/queries.py | 级联检查计划 | 依赖反查时按需补 |
| **L13（新）** | T16 dead 单扫不查死亡拍节点 active（与 state_at 口径分叉）；dead 解析与 state_at 重复实现 | flow/snowflake.py | 级联检查计划（与 L4 同族） | 抽公共"死亡判定"助手时统一 |
| **L14（新）** | C5 stale 循环事务外逐条标记（中途崩溃留部分标记保守态） | api.py | 多端并发硬化 | 包事务或补偿 |
| **L15（新）** | 零事实章 appeared 丢失（激活滞后到下一低敏章） | writeback/extract.py | 级联/后续（接受边维持） | 滞后显著时发空 facts 事件 |
| **L16（新）** | Windows python.org 构建 sqlite3 无 enable_load_extension → api.open 崩；shell 单独安装需 core 已在索引 | storage/vec.py / 发布 | v1.0.0 发版前（发布债） | 文档注明 conda/自带扩展构建；core+壳同步发包 |
| L1/L2/L3/L5/L6/L7/L8/L9/L10 | ~~全部修复关闭~~（L1–L3 壳计划；L5 T1、L7 T18；L6/L8/L10 T18；L9 T14；L2 T1+T11） | — | — | — |

随行小项（不强制，两波终审 triage 维持 deferred）：generate 返回无 audit_hint（审计经 advanced/audit 可查）；rewrite 指示经 reason 参数（语义重载，功能正确）；CLI --format 未校验；re-register 连字符命名；FTS 侧表升级窗口（旧库首 refresh 前段落检索空，首写自愈）；mirror.reconcile project_root 未用（目录迁移误报 missing）；fts 8-token 截断/引号未剥；N+1 族（fts name 回填/alias/appeared/deviation 全表扫/卷章嵌套）；filterwarnings 按消息前缀；set(exclude) 循环内重建；api.confirm 不存在 pid 抛 TypeError；reject_auto 计条目数非命中数；reason=None 无测试；manual 模式 confirm 静默覆盖未对账外部编辑（Web UI 提示面）；若干析取弱断言。

## 终审修复波

- 前半（fe7203d）：api.open 补 migrate（存量库兼容，评审实证崩）+ 回归测试 ×2；tests/README §1/§3 登记；TC-RT-03 死亡过滤去掩蔽；hybrid vec 滤 active；死参数清理；vec.ensure 短路。定向复审 6/6。
- 后半（ae0041e）：Critical——rewrite 后 prose content 过期（确认写旧文，静默错内容）——同步 content=draft，回归锁文件+哈希+reregister 链；Important——scenes/scene 层别名、ai_generate 围栏容忍（parse_llm_json+文案中性化）、latest_extract_proposal 门面化；Minor——backend 路径统一、scene_of_chapter 公有化。定向复审 6/6。

## 后续计划注意

1. **级联检查计划**（下一候选）preflight：L4 + L13（同族统一）+ retcon 触发面 stale（T17 只接 revision 面）+ "受影响"依赖图分析（现为全 pending 保守标记）+ TC-CC 全域 + WB-08 封卷后半。
2. Web 三栏计划 preflight：manual confirm 覆盖提示、rewrite reason 语义重载 UI 面、TC-SH-08、result/deviation 面板数据源。
3. v1.0.0 发版前：L16 发布债；黑盒覆盖矩阵终核（66 例中两波覆盖约 50 例，豁免：TC-CC 全域、TC-EX、WB-08 后半、PR-02 retcon 面、RT-05 批量抽取）。
