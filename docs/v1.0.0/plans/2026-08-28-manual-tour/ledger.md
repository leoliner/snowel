# Step 6 Web 手册弹窗 + tour 计划 ledger（2026-08-28-manual-tour）

> 归档自 `.superpowers/sdd/plan/progress.md`（live ledger，worktree 已删）。计划：同目录 `plan.md`（2026-08-28 批准；**用户裁决 R1 修订版：放开 markdown 依赖，渲染质量优先**——react-markdown@10.1.0 + remark-gfm@4.0.1，tour 仍零依赖自写）。

## 1. 执行总览

| 项 | 值 |
|---|---|
| 分支 | feat/manual-tour（worktree `D:\Code\snowel-manual-tour`，已删）→ merge --no-ff 回 dev-1.0.0 @ aeb988d |
| 提交链 | d59ddb5 (T1 手册 12 章) → 2d7c027 (T1 修复环) → 666dfc7 (T2 弹窗) → cc00210 (T3 tour) → c094ac2+f1a1f02+234909d (T4 minor+scenes 修复+落锚) |
| 模式 | Subagent-Driven，4 任务串行；T1 经 1 轮修复环（技术断言失实×2），T2/T3/T4 首轮即 Approved |
| 测试基线 | 后端 328→**331**（净增 3）、前端 vitest 91→**125**（净增 34）、build 绿；合并后主仓库依赖重装全量复跑确认 |
| 验收闭环 | addendum §6 全兑现：手册 12 章随前端打包进 dist（终审 dist 实证）、居中大窗+目录+过滤+esc/遮罩+"？"常驻（TC-SH-13 落锚）；tour 欢迎卡+6 步+localStorage+手册重看（TC-SH-14 落锚，81→**83 例**）；RW-③ 手册必写三事项落位（第 8/12 章）；**执行-6 carry：scenes→scene 既有真 bug 修复**（选"场景"生成修前必 400） |

## 2. Ruling 裁决记录（决策—理由—若错的成本）

### 计划级（用户批准，详见 plan.md §4）

| # | 裁决 | 若错的成本 |
|---|---|---|
| R1 | **用户修订版**：markdown 渲染用 react-markdown + remark-gfm（组件化无 XSS 面、GFM 表格、Tailwind components 映射单处定义）；md 加载 `import.meta.glob query:'?raw'` 构建期进 bundle | 依赖树增量已由用户知情接受 |
| R2 | tour 自写零依赖：欢迎卡顶栏下方右侧浮层不遮工作区；遮罩+叠加定位环（渲染期测量，不改 target class）；气泡上/下自适应 | 交互打磨升级再评估引库 |
| R3 | 手册入口 = 顶栏"？"（manual-btn）；居中大窗 + 左目录树 + 顶部过滤（纯客户端）+ esc/遮罩关闭（ConfirmDialog focus 先例） | 布局微调不改逻辑 |
| R4 | `localStorage["snowel.tour.done"]` 单键管三出口（跳过/完成/Esc 中止均记忆）；手册底部"重看操作导览"= 清键+关弹窗+启动 | 键拆分无产品收益 |
| R5 | SH-② = `_require_params` 守卫（ValueError 中文文案与 Web `_require` 400 对齐）；RW-② = 双入口 `host.strip("[]")`（守卫在 strip 后，"[::]"归一仍拦） | 文案/卫生级 |
| R6 | 手册 12 章定稿（§4.1 要点表），RW-③ 三事项落第 8/12 章 | 增删章 = 一文件 + 目录自动解析跟进 |
| R7 | tour 6 步定稿：三栏布局→流程树→生成表单→提案确认→正文编辑→聊天侧栏（第 5/6 步文案含 readonly/租约要点） | 步骤增删改 steps 数组一处 |

### 执行期追加

| # | 裁决 | 理由 | 若错的成本 |
|---|---|---|---|
| 执行-6 | **scenes→scene 既有真 bug carry 修复**（T1 撰写时移交疑点，控制器核实）：web labels.ts LAYERS 用 `scenes`（复数）而 core ARTIFACTS 键为 `scene`——选"场景"生成修前必 400；实现者深挖发现 flow wire 键也是复数（`flow/state.py` LAYERS + `_LAYER_ALIASES`），修法 = LayerKind 单数化（提交键）+ FlowLayer wire 型拆分 + `toFlowLayer` 换算适配 FlowTree（进度键），双向钉子测试；未动 core（pytest 基线不变） | 生成提交与进度展示是两个语义两套键，朴素改名会同时破两面；换算拆型是唯一正确方向 | 无（评审三向实证：core 键面/无业务残留/双链钉子测试） |
| 执行-7 | T1 修复环 2 Minor（07 章补行、failed 消歧）随 2 Important 同轮收口 | 同文件同性质措辞级 | 无 |

## 3. 挂账表

| L 项/新登记 | 内容 | 状态 | 承接 |
|---|---|---|---|
| SH-② | MCP 缺参 KeyError 文案 | **关闭**（`_require_params` 三例锚） | — |
| SH-③ | chips role=group + InspirationPanel 容错红条 | **关闭** | — |
| RW-② | 方括号 host 二次包裹崩 | **关闭**（双入口 strip + 双入口测试） | — |
| RW-③ | 手册必写三事项 | **关闭**（第 8 章 --http 守卫语义、第 12 章 rewrite 开关+无 key 建议） | — |
| MT-① | ManualModal 过滤词/选中章关闭后不清空（重开见残缺目录易被理解为 bug） | 新登记（ride，终审） | **Step 7 走查候选池**（一行 open effect 清空） |
| MT-② | Tour 气泡高度魔数 200 + BUBBLE_WIDTH/w-72 双源 | 新登记（ride，终审；T3-1 同族合并） | Step 7 走查候选池（导出常量收口） |
| MT-③ | welcome 卡与手册弹窗叠放——实际层序 z-40 < z-50 比预想 benign（运行中遮罩挡手册） | 记录性 | Step 7 走查确认观感 |
| MT-④ | `_require_params` 先于租约判定（报错优先序与 Web 不对称）；`host "[]"` 空串卫生项 | 记录性 | 顺手 |
| T4-①② | labels.ts:35 注释指向过时文件；InspirationPanel 双 alert 并存 | 记录性 | 顺手 / 维持现状即正确 |
| EX-③ / L16 / L26 / L27 / RW-① | 触发条件未变 / 发布债（含 mcp>=1.29 下限） / 记录性 / 卫生项 | 不携带 | 原承接 |
| TC-ON-17、TC-SH-09–14、TC-RT-07、TC-EX 转正 | 全量覆盖终核 | **开放 → Step 7 终核**（本 ledger 归档后控制器执行） | Step 7 |

## 4. 终审修复波

- T1 修复环（d59ddb5..2d7c027）：Important×2（第 3 章 MCP 确认断言语义反——实际 snowel_proposal 有 confirm；第 12 章向量召回失实于默认 deterministic 配置）+ Minor×2（07 章 28 行、failed 消歧）——复审 4/4 ADDRESSED 无新破坏。
- 终审（全分支 6c457ef..234909d）：**Yes（可合并）**——Critical×0、Important×0、Minor×4 全 ride（MT-①～④）。终审席独立复跑 331+125+build 绿、oxlint 零新增（5 条均在未触碰行）；**手册 20+ 处"危险指令"独立复验全部与实现一致**；tour 六步 target 全部存在于真实渲染树（proposal-panel 空态兜底是细心补强）；dist 实证 12 章内容与 tour 键进 bundle；testcases.md 实测 83 行 TC 锚。

## 5. 覆盖口径备忘

黑盒用例 **81→83 例**（TC-SH-13/14 落 §9 SH 域 + §11.2 §7.1 行 08–10、13、14；tests/README web 行双锚）；grep 实证零虚登记（评审逐锚验证）。AGENTS.md 阶段指针随本 ledger 归档同步更新（Step 6 完成 → Step 7 终核+人工走查）。
