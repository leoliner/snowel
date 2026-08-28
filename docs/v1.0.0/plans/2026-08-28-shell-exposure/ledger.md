# Step 4 壳端暴露计划 ledger（2026-08-28-shell-exposure）

> 归档自 `.superpowers/sdd/plan/progress.md`（live ledger，worktree 已删）。计划：同目录 `plan.md`（2026-08-28 批准）。

## 1. 执行总览

| 项 | 值 |
|---|---|
| 分支 | feat/shell-exposure（worktree `D:\Code\snowel-shell-exposure`，已删）→ merge --no-ff 回 dev-1.0.0 @ cffad57 |
| 提交链 | 31c475f (T1 MCP advanced) → 3e3e50a (T2 Web 路由+beats_of) → 481f2ac (T3 灵感面板) → a1a6f8d (T4 拍操作) → eb74019 (T5 落锚) → a67d4a6 (终审修复波) |
| 模式 | Subagent-Driven，5 任务（T1 独立、T2→T3→T4 串行、T5 收口）；五任务全部首轮 Approved，终审 1 Important 经修复波闭环 |
| 测试基线 | 后端 309→**318**（净增 9）、前端 vitest 74→**91**（净增 17）、build 绿；合并后主仓库 editable 重装全量复跑确认 |
| 验收闭环 | addendum §4 暴露矩阵全格交付（灵感层 Web+MCP+generate derive_from 双侧、拍操作 Web+MCP、扩展包无壳面=裁决 6）；**L25 全关**；TC-SH-09/10/11 落锚（76→79 例口径，§11.1/§11.2 联动更新）；唯一 core 增量 = 只读门面 `beats_of`（壳零 SQL 铁律） |

## 2. Ruling 裁决记录（决策—理由—若错的成本）

### 计划级（用户批准，详见 plan.md §4）

| # | 裁决 | 若错的成本 |
|---|---|---|
| R1 | 拍列表走 core 新只读门面 `beats_of(chapter_id)`（壳零 SQL 铁律）——实现按 props.address 双键（volume+chapter）适配并加 Chapter 类型校验（编号跨卷不唯一，stats_pacing 同口径） | 字段增删改一处 SQL + 断言 |
| R2 | 伏笔迁移预览 = 前端过滤既有 `stats/foreshadow`（零 core 改动）；valid_until_beat 边级明细不做 | 要边明细则照 R1 模式补门面 |
| R3 | MCP 六工具不变式：新能力走 ADVANCED_CATALOG + `snowel_advanced` op（新增可选 `params` 传参，既有调用零变化）；`extension_packs` 占位改"仅 CLI 管理（裁决 6）" | 拆新工具动 TC-SH-01 契约 |
| R4 | 灵感面板挂右栏提案 tab（GenerateForm 之上）不新开 tab；derive 联动 = GenerateForm 灵感多选 chips（空选不含键，与后端条件透传对齐） | 面板拥挤则后移独立 tab，组件零重写 |
| R5 | 拍操作全复用现成范式（ConfirmDialog/doSave 红条/onMutated）；合并交互 = 两段式点选（源拍进目标点选态） | 挪位置不重写逻辑 |

### 执行期追加

| # | 裁决 | 理由 | 若错的成本 |
|---|---|---|---|
| 执行-3 | addendum "合并到相邻拍"读作**示意描述非硬校验约束**——core merge_beats 自 Step 1 起任意拍合并（TC-ON-17 依赖伏笔可迁任意承接拍），UI 允许任选 target 与后端能力一致 | 相邻硬约束须 core+UI 两层同加，现不作为 | 用户若坚持产品意图，一行前端过滤 |
| 执行-4 | 计划"§11.2 壳域行 01–08"字面不存在（§11.2 按需求章节组织）——按 TC-ON-17 先例拆 §7.1/§7.2 行并联动 §11.1 C10/铁律5 | 计划字面不可执行，语义等价意图 | 无（评审核实忠实） |
| 终审-1 | 终审 Important：增补 §4 矩阵 MCP 侧 "`generate` 带 `derive_from`" 缺失——**计划收窄缺陷（控制器认领：拆计划时漏圈）**，采方案①补齐 `snowel_generate` 可选参条件透传（a67d4a6，+1 测试） | addendum 字面即需求，补齐回归本义；若用户裁决 MCP 侧不必有则应显式降级登记 | 已按补齐处置，无遗留 |

## 3. 挂账表

| L 项/新登记 | 内容 | 状态 | 承接 |
|---|---|---|---|
| L25 | 壳端暴露部分（Web 灵感/拍操作、MCP advanced） | **全关**（core 部分 Step 1、壳端部分本步） | — |
| **EX-③** | discovery 警告池归因漂移 + per-instance 注册表决策 | **开放，挂账条件已精确化**："任何壳扩展包面落地之日"（本步核实 Web/MCP 不做扩展面，触发条件不成立；原"Step 4 必查"预告解除） | 条件触发之日 |
| SH-① | 两壳拍操作响应键名不对称（web `moved`/`deleted` vs MCP `event_seq`；delete 丢 seq）——前端均不消费响应体，无功能风险 | 新登记（ride） | **Step 5 壳面工作统一**（勿专开修复波） |
| SH-② | MCP 缺参 KeyError 文案劣于 Web `_require` 400（沿用 foreshadow_register 既有惯例，目录 hint 有参数提示） | 新登记（ride） | Step 6 手册/顺手 |
| SH-③ | a11y 与容错 polish：chips 缺 role=group、InspirationPanel 列表取数失败静默（拍侧栏有红条不对称）、App 级 refreshKey 接线无测试锚 | 新登记（ride） | Step 6（a11y 批次）/ Step 7 走查修复波 |
| SH-④ | TC-SH-02 预期列目录枚举不含新四 op（包容式读法仍真，TC-SH-11 单独锚）；stats/foreshadow 预览不随操作刷新（二次对话框可能陈旧，纯预览无风险）；plan §4/§6 面板位置措辞不一致（实现取"之上"，R4 本意完整兑现，归档勘误不改已批正文） | 记录性 | Step 6 手册 / Step 7 走查 |
| L16 / L26 / L27 | 发布债 / 记录性 / 卫生项 | 开放（未携带） | Step 8 / — / 专门时机 |

## 4. 终审修复波

- 终审（全分支 9fb10a1..eb74019）：**With fixes**——Critical×0、Important×1（MCP generate derive_from 缺失，计划收窄缺陷，终审-1 补齐）；Minor×4 全 ride（SH-①②③④）。终审席实测基线 317+91+build 绿、`git status` 干净；三方契约（core↔web_server↔types.ts）逐字段闭环；6 个新写入口租约双保险一致；TC-SH-09/10/11 黑盒语义逐句可追溯。
- 修复波 a67d4a6：`snowel_generate` 加可选 `derive_from` 条件透传（与 Web T2 同款 isinstance list 门，缺席调用形状不变）+ 契约测试 `test_generate_derive_from_passthrough`（带/不带双锚）。全量 317→**318**。
- 定向复审：ADDRESSED、无新 Critical/Important（既有 generate 测试原样绿即缺席不变之证；DERIVED_FROM 边建立由 core TC-ON-12 覆盖，口径无缺口）。

## 5. 覆盖口径备忘

黑盒用例 **76→79 例**（TC-SH-09/10/11 落 §9 壳域 + §11 矩阵三处联动；testcases.md 无显式总数文案，口径在 AGENTS.md/ledger 侧维护）；tests/README.md shell/web 行反向索引同步（grep 实证零虚登记，评审逐锚验证行号与断言）。AGENTS.md 阶段指针随本 ledger 归档同步更新。
