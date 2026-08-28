# v1.0.0 范围扩容 Step 6：Web 手册弹窗 + 操作指引 tour

> 日期：2026-08-28。来源：范围增补 `requirements-addendum.md` §6 / §8（Step 6 行）——8 step 链第 6 步。
> 性质：前端功能计划——手册章节依赖的 Step 1–5 功能全部定稿，本步撰写内容并落地两个 UI 功能；章节清单与 tour 步骤按 addendum 授权在本计划定稿（§4 R6/R7，随计划批准生效）。
> 上游素材：`plans/2026-08-28-rewrite-http/ledger.md`（preflight：RW-②③、SH-②③ 本步消化）；手册内容权威 = 各功能实现现状 + `extensions/SKILL.md`（扩展包章对齐）。

## 1. 背景与范围

| 项 | 内容 | 黑盒锚 |
|---|---|---|
| 手册弹窗 | Markdown 随前端打包（`web/src/manual/*.md` raw import 进构建，进 dist/进 Release）；居中大窗 modal + 左侧目录树 + 顶部关键词过滤（纯客户端匹配）；esc/遮罩关闭；"？"入口常驻顶栏 | TC-SH-13 转正 |
| 操作指引 tour | 首次打开显欢迎卡（不遮工作区）→"开始导览"手动启动；跳过/完成 localStorage 记忆不再自动出现；手册弹窗内可随时重启；高亮定位+气泡提示；前进/后退/随时退出；6 步定稿（R7） | TC-SH-14 转正 |
| 手册内容 | 12 章全功能域定稿（R6）——含 RW-③ 必写事项（rewrite 开关说明、无 key 环境建议、`--token`/通配守卫语义） | — |
| minor 分摊 | Viz.test 硬编码 320/3.5 常量解耦（acceptance-gap ledger）；SH-② MCP 缺参文案；SH-③ chips role=group + InspirationPanel 容错红条；RW-② 方括号 host 规范化 | — |
| 文档落锚 | testcases.md §9 +TC-SH-13/14（81→83 例）+ §11 联动 + tests/README 反向索引 | — |

不在范围：手册的多语言/主题切换；tour 的视频/动效；MCP 缺参文案以外的壳侧改动；发布打包流程（Step 8 L16——raw import 天然进 dist 已满足"进 Release"）。

## 2. Global Constraints

- 领域逻辑只在 core——本步纯前端 + 一处 MCP 错误文案（SH-②）+ 一处 host 规范化（RW-②），零后端行为变更。
- **依赖边界（用户修订）**：markdown 渲染放开 `react-markdown` + `remark-gfm`（R1 修订版）；tour 与其余功能仍零依赖自写（R2）；除这两包及其传递依赖外不得引入新包。
- 前端范式沿用：Tailwind 语义 token、data-testid、labels.ts 中文文案单处维护、vi.mock('../api') 测试范式、oxlint 零新增警告。
- `npm run build` 必须绿（tsc -b 严格模式）；raw import 的 md 文件进 dist 由 vite 构建天然保证。
- 每任务 TDD、conventional commits；testcases.md 落锚 grep 实证。
- 全量基线：dev-1.0.0 @ 6c457ef，后端 328 + 前端 vitest 91 + build 绿。

## 3. Preflight 挂账裁决（同版本已归档 ledger 全量双查）

| 挂账 | 内容 | 裁决 | 去向 |
|---|---|---|---|
| SH-② | MCP 新四 op 缺参 KeyError 文案劣于 Web `_require` 400 | **携带**——mcp_server.py 分派层加 `_require` 同款守卫（ValueError→既有 400 语义） | Task 4 |
| SH-③ | GenerateForm chips 缺 role=group；InspirationPanel 列表取数失败静默 | **携带**——两处一行级 polish | Task 4 |
| RW-② | `--host` 带方括号形态（"[::1]"）二次包裹构造崩 | **携带**——CLI/main 入口 `host.strip("[]")` 规范化 | Task 4 |
| RW-③ | 手册必写：rewrite 开关说明、无 key 环境建议、--token/通配守卫语义 | **携带**——手册第 8/12 章内容需求 | Task 1 |
| Viz.test 常量 | 硬编码 320/3.5（acceptance-gap ledger minor 池） | **携带**——grep 定位后从组件导出常量 import 解耦 | Task 4 |
| TC-SH-13/14 | addendum §6 建议用例（未列入 testcases.md） | **携带**——转正落锚 | Task 4 |
| EX-③ / L16 / L26 / L27 / RW-① | 触发条件未变 / 发布债（含 mcp 下限） / 记录性 / 卫生项 | 不携带 | 原承接 |

任务间共享文件冲突：T1 独占 `web/src/manual/`（新目录）；T2 独占 ManualModal 组件 + App.tsx 入口；T3 独占 tour 组件 + App.tsx（基于 T2 提交串行）；T4 独占 mcp_server/cli/Viz.test/GenerateForm/InspirationPanel + 文档。无并行冲突。

## 4. 计划级设计裁决（预登记 Ruling，随计划批准生效）

| # | 裁决 | 理由 | 若错的成本 |
|---|---|---|---|
| R1 | **markdown 渲染用 `react-markdown` + `remark-gfm`**（**2026-08-28 用户修订版**：放开 markdown 依赖，渲染质量优先）；React 组件化渲染无 XSS 面（无 dangerouslySetInnerHTML）；GFM 表格/删除线支持，手册源文可用 GFM 全集（12 章鼓励用表格提升可读性）；components 映射 Tailwind 语义 token（prose 样式统一在渲染器单处定义）；md 加载用 `import.meta.glob('../manual/*.md', { query: '?raw', import: 'default' })`（vite 原生，构建期进 bundle） | 用户裁决渲染质量优先；成熟库的可读性/表格支持远超自写子集；组件化渲染与项目安全风格一致 | 依赖树增量（纯 JS 若干包）已由用户知情接受 |
| R2 | **tour 自写零依赖**：欢迎卡 = 顶栏下方右侧固定浮层（不遮工作区，含"开始导览/跳过"）；步骤高亮 = 全屏半透明遮罩层 + target 元素动态加高亮环（z-index 提升 + ring 样式，比遮罩挖洞简单稳健）；气泡 = 相对 target 矩形定位（上/下自适应视口）；前后退/退出按钮在气泡内 | 引 tour 库（driver.js 等）违反零依赖；自写 6 步的量级 ~150 行可控 | 交互打磨需求升级再评估引库 |
| R3 | 手册入口 = 顶栏"？"按钮（session-dot 旁，`data-testid="manual-btn"`，title"使用手册"）；弹窗结构 = 居中大窗（max-w-4xl 级）内左目录树（章节锚点列表）+ 右内容区滚动 + 顶部关键词过滤框（前端 filter 章节标题+正文，命中章节高亮/仅列命中章）；esc 与遮罩点击关闭 | addendum §6.1 字面形态；"？"常驻是唯一入口要求 | 布局微调不改逻辑 |
| R4 | tour 状态 = `localStorage["snowel.tour.done"]`：欢迎卡仅当无此键时首开显示；"跳过"与最后一步"完成"均 set；手册弹窗底部常驻"重看操作导览"按钮（清键并立即启动 tour）；tour 运行中 esc = 中止并 set 键 | addendum §6.2 字面；一个键管两个出口语义最简 | 键拆分（跳过≠完成）无产品收益 |
| R5 | SH-② 修法 = mcp_server 四 op 分派前 `_require_params(p, [...])` 同款守卫（缺失键 → ValueError 中文文案，经既有错误映射返回工具错误——与 Web 400 语义对齐）；RW-② 修法 = cli mcp 命令与 mcp_server.main 双入口对 host `strip("[]")` 规范化（防御二次包裹，守卫集合匹配在 strip 后进行） | 与 Web 缺参 400 语义对齐；strip 后守卫语义不弱化 | 文案打磨无行为风险 |
| R6 | **手册 12 章定稿**（§4.1 要点表）——文件名 `NN-slug.md` 双位序号保目录序；每章 30–80 行，含 RW-③ 必写内容 | addendum §6.1 章节范围全覆盖 + Step 5 遗留手册事项归位 | 增删章 = 一文件 + 目录自动生成 |
| R7 | **tour 6 步定稿**：①三栏布局（App main 容器）②流程树（FlowTree）③生成表单（GenerateForm）④提案确认（ProposalPanel）⑤正文编辑（ProseEditor）⑥聊天侧栏（ChatSidebar）——每步标题+一句指引文案（labels.ts），气泡文案含"保存与租约"要点（第 5/6 步文案内提及 readonly 语义） | addendum §6.2 建议 5–6 步的全量覆盖排布 | 步骤增删改 steps 数组一处 |

### 4.1 手册 12 章要点表（R6，行文归实现者，要点为验收对照）

| # | 文件 | 章节 | 内容要点（验收对照） |
|---|---|---|---|
| 01 | 01-getting-started.md | 快速上手 | `pip install -e . -e ./shell`、`snowel init`、`snowel web`/`snowel mcp` 入口、三栏布局一览、建议第一步（灵感雪核） |
| 02 | 02-flow.md | 雪花五层流程 | 灵感雪核→一段式摘要→一页纸大纲→角色血肉→场景脉络→正文绽放；FlowTree 进度与待办；生成表单七类 artifact |
| 03 | 03-proposals.md | 提案与确认 | 提案队列、confirm/reject/rewrite、结构化面板是唯一确认口（铁律4）、auto 入典与人工提案分级 |
| 04 | 04-writeback.md | 回写与镜像 | extract 抽取、auto 直入与哨兵、正文镜像 reconcile、deviation 对账 |
| 05 | 05-seal-retcon.md | 封卷与 retcon | seal 冻结线、retcon 改设、二者与提案的关系 |
| 06 | 06-chat.md | 聊天侧栏 | 对话发起、search 工具环、聊天检索走统一检索管线 |
| 07 | 07-viz.md | 可视化四件 | PovChart/ForeshadowMap/RelationsGraph/PacingBars 各自读什么 |
| 08 | 08-lease.md | 租约与多端 | 写租约单写者、readonly 降级呈现、心跳续租、CLI/Web/MCP 三端入口、`snowel mcp --http`（**RW-③：默认 127.0.0.1、通配地址强制 --token、错 token 401**） |
| 09 | 09-inspiration.md | 灵感层 | 保存原话、列表、从灵感 derive 生成（生成表单选灵感）、DERIVED_FROM 边 |
| 10 | 10-beats.md | 拍编辑 | 拍侧栏、合并（伏笔迁移预览）、删除（被引用拒绝呈现）、merge 到承接拍的语义 |
| 11 | 11-extensions.md | 扩展包 | 双位置发现、`snowel ext` 四命令、挂载/卸载/升级语义（不自动跟随须 re-mount）、指向 `extensions/SKILL.md` 与预制包 |
| 12 | 12-retrieval.md | 检索与偏好 | hybrid 检索、**RW-③：`retrieval.rewrite` 默认开与关闭方法（config 表）、无 LLM key 环境建议关闭**、config 表直改 |

## 5. 文件结构总表

| 文件 | 动作 | 任务 |
|---|---|---|
| `web/src/manual/01..12-*.md` | 新建 12 章（R6 要点表） | T1 |
| `web/src/components/Markdown.tsx` | 新建渲染器（react-markdown + remark-gfm，Tailwind components 映射） | T2 |
| `web/src/components/ManualModal.tsx` | 新建弹窗（目录/过滤/esc/遮罩） | T2 |
| `web/src/App.tsx` | 顶栏"？"按钮 + ManualModal 挂载 + tour 状态接线 | T2 / T3 |
| `web/src/components/Tour.tsx` | 新建欢迎卡 + 步骤高亮气泡（R2） | T3 |
| `web/src/components/labels.ts` | 手册/tour 文案登记 | T2 / T3 |
| `web/src/components/ManualModal.test.tsx` / `Tour.test.tsx` / `Markdown.test.tsx` + 既有测试适配 | 新建/扩展 | T2 / T3 |
| `shell/src/snowel/mcp_server.py` + `cli.py` | SH-② 守卫 + RW-② strip("[]")（R5） | T4 |
| `web/src/components/GenerateForm.tsx` / `InspirationPanel.tsx` | SH-③ role=group + 容错红条 | T4 |
| `web/src/components/Viz.test.tsx` + 对应组件 | 硬编码 320/3.5 常量解耦 | T4 |
| `docs/v1.0.0/testcases.md` + `tests/README.md` | TC-SH-13/14 落锚（81→83 例）+ 反向索引 | T4 |

## 6. 任务清单

### Task 1: 手册内容 12 章（R6）

**实现**：按 §4.1 要点表撰写 `web/src/manual/` 12 个 md——内容权威 = 实现现状（组件真实行为、命令真实名称），扩展包章对照 `extensions/SKILL.md` 与预制包，RW-③ 三事项分别落在第 8/12 章。语法用 GFM 全集（表格鼓励用于对照类内容）。**验收 = 要点表逐章对照 + 命令/键名/组件名与实现一致（抽查 grep）**；本任务无代码，报告附每章要点覆盖打勾表。

### Task 2: 手册弹窗（TC-SH-13 / R1+R3）

**实现**：Markdown.tsx（R1 子集渲染器，纯函数转换安全转义——**不自造 HTML，React 元素树**，无 dangerouslySetInnerHTML）；ManualModal.tsx（R3 结构：目录树 = 章节锚点列表点击滚动定位、过滤框输入 → 标题+正文 includes 匹配过滤目录与内容高亮、esc/遮罩关闭、focus 管理照 ConfirmDialog 先例）；App.tsx 顶栏"？"按钮 + 状态接线；labels.ts 文案。

**测试**（vitest，TC-SH-13 锚）：
```tsx
// Markdown.test.tsx——渲染器子集逐项（标题层级/列表/代码块/行内代码/粗体/普通段落）
// ManualModal.test.tsx
"？"按钮打开弹窗；目录渲染 12 章并可点击定位；过滤框输入关键词 → 目录与内容过滤命中；
esc 关闭；遮罩点击关闭；内容渲染 markdown 元素（h2/列表/代码块真实来自 md 源）
```

### Task 3: 操作指引 tour（TC-SH-14 / R2+R4）

**实现**：Tour.tsx（R2 自写：欢迎卡组件 + 步骤引擎——steps 数组含 target testid/标题/文案，getBoundingClientRect 定位遮罩高亮环与气泡，resize/滚动重算可简化为每步打开时计算一次）；App.tsx 接线（首开无 localStorage 键显欢迎卡；手册弹窗底部"重看操作导览"按钮 = 清键+关弹窗+启动）；labels.ts 六步文案。

**测试**（vitest，TC-SH-14 锚）：
```tsx
// Tour.test.tsx
首开无键 → 欢迎卡显示（含开始/跳过）；跳过 → localStorage 记忆 + 消失；
开始导览 → 第 1 步气泡与高亮出现 → 前进/后退推进 6 步 → 完成记 localStorage；
运行中退出（esc/退出按钮）→ 记忆 + 消失
// App.test.tsx 扩
有键 → 欢迎卡不出现；手册"重看导览"按钮 → 清键 + tour 启动
```
（jsdom 无真实布局——getBoundingClientRect 返回 0 矩形，断言以"气泡文案/testid 出现与推进"为准，定位样式断言不做，报告注明。）

### Task 4: minor 包 + 落锚收口（R5）

| 子项 | 落点 | 修法 | 锚 |
|---|---|---|---|
| SH-② | mcp_server.py 四 op 分派 | `_require_params(p, [...])` 守卫（缺失 → ValueError 中文文案走既有错误映射）；测试 3 例（save 缺 text/merge 缺 target/delete 缺 beat_id → 错误响应含文案） | 工具错误响应断言 |
| SH-③ | GenerateForm / InspirationPanel | chips 容器 `role="group"` + aria-label；列表取数 error 红条（照 beatsError 范式） | vitest 各一断言 |
| RW-② | cli.py + mcp_server.py 入口 | host `strip("[]")` 规范化（守卫在 strip 后） | cli 测试一例（"[::1]" + token 不崩且守卫语义不变） |
| Viz.test 解耦 | Viz.test.tsx + 对应组件 | grep 320/3.5 定位硬编码 → 组件导出常量 import（先 grep 再动，报告附定位） | vitest 全绿不变 |
| TC-SH-13/14 落锚 | testcases.md §9 + §11 联动 + tests/README | 照 Step 4/5 先例；grep 实证 | — |

### 收尾（dev-workflow §7 全流程）

终审（全分支独立评审）→ 修复波 + 定向复审 → 合并 `dev-1.0.0`（合并结果主仓库全量重跑：pytest + vitest + `npm run build`；worktree 需 `npm ci`）→ 删 worktree/feat 分支 → ledger 归档 `plans/2026-08-28-manual-tour/ledger.md`（SH-②③/RW-②③ 关闭登记）→ 更新 AGENTS.md 阶段指针（Step 6 完成 → Step 7 终核+走查）→ 推送 dev。**Step 7 的覆盖终核随后执行；人工走查与 Step 8 PR 须用户发话。**

## 7. 执行参数

| 项 | 值 |
|---|---|
| 模式 | Subagent-Driven（4 任务串行 T1→T2→T3→T4；两席评审/任务；controller 不写码） |
| worktree | `D:\Code\snowel-manual-tour`（兄弟目录，从 dev-1.0.0 切；需 `npm ci`） |
| 分支 | `feat/manual-tour` → merge --no-ff 回 `dev-1.0.0` |
| 测试基线 | 合并前 328 + 91 + build 绿为底（预计前端净增 ~15、后端净增 ~3） |
| 修环上限 | 5 轮（R1-3 原实现者，R4-5 换强模型新派） |
| Step 7 接口 | 覆盖终核（81+2 例锚点全量 grep 核对）由控制器在合并后执行；人工走查清单（handoff §2.3 + 新增面）整理后交用户主刀 |
