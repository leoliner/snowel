# Snowel 项目指令

## 项目说明

- Snowel：AI 小说生成引擎（雪花法），小说创作辅助工具——当前开发重点。

## 架构说明

- 当前重点是开发 Snowel 小说创作辅助工具。
- 总架构：一个引擎核心（snowel-core，纯 Python）+ 三个薄外壳：MCP Server（stdio，供 AI 客户端）、CLI（typer，本地管理）、FastAPI + React Web UI（最终面向作者的主创作界面）。
- 领域逻辑（雪花流程、图谱、级联检查、回写）只写在 snowel-core，外壳不得包含领域逻辑。

## 文档与工作流状态

- 需求上游：模拟推演 `docs/v1.0.0/details/sim-walkthrough-01.md`（示范小说走查，问题清单 #0–#31 + 技术决议）；需求定稿：`docs/v1.0.0/requirements.md`（C1–C12 裁决并入正文）；设计定稿：`docs/v1.0.0/design.md`（D1–D8 + E1–E5）；**范围增补定稿：`docs/v1.0.0/requirements-addendum.md`（2026-08-26，13 裁决 + 8 step——v1.1 移后事项全部移入 v1.0.0 + Web 指引/手册新需求，冲突处以增补为准）**；其余过程文档在 `docs/v1.0.0/details/`。
- 工作流遵循全局 skill 链：spec-workflow（`~/.agents/skills/spec-workflow/`：simulation → requirements → design → testcases → plans）+ dev-workflow（`~/.agents/skills/dev-workflow/`：计划批准后执行、ledger 归档、收尾与 PR 规约）。
- 黑盒测试用例：`docs/v1.0.0/testcases.md`（9 域 76 例——历史文档"66 例/10 域""75 例"口径过时；TC-ON-17 随 Step 1、TC-EX-01~05 随 Step 2 已全部有实现测试锚；覆盖矩阵含 C1–C12/D1–D8/E1–E5）。
- 实现计划存储于 `docs/v1.0.0/plans/`；落地顺序：core（本体+事件溯源+基础查询）→ MCP/CLI 壳 → 回写环+混合检索 → Web 三栏界面 → 验收补丁 → 8 step 范围扩容链（Step 1 core 功能债、Step 2 扩展包机制、Step 3 预制包+skill 双落、Step 4 壳端暴露、Step 5 rewrite+HTTP 已完成）。
- 当前阶段：**范围扩容 8 step 链执行中——Step 5 rewrite_query + streamable HTTP 已完成并合入 dev-1.0.0**（6858af9，后端 328/328 + 前端 91/91 + build 绿；检索改写默认开三入口统一+失败回落审计、`snowel mcp --http` 保守分层+通配强制 token+401；TC-RT-07/TC-SH-12 落锚 81 例口径）。**下一步：Step 6 Web 手册弹窗 + tour（addendum §6：手册居中大窗+目录+搜索，章节依赖 Step 1–5 定稿现已齐备；tour 欢迎卡+手动启动+localStorage；TC-SH-13/14；minor 分摊 web 侧 Viz.test 常量解耦 + SH-②③ polish + RW-②③ 手册事项）→ Step 7 终核+人工走查（用户主刀）→ Step 8 L16 发布+PR 需发话（含 RW-① mcp 依赖下限）**；新会话执行入口：addendum §6（Step 6 需求细则）+ `plans/2026-08-28-rewrite-http/ledger.md`（preflight 挂账必读：RW-①～④、SH-②③）+ dev-workflow skill。
- **跨计划遗留**：L16 Windows python.org 构建扩展加载崩 + core/壳同步发包 + **mcp 依赖下限提版（RW-①：`mcp>=1.2` 陈旧，新 SDK 面需 `>=1.29`）**（发版前发布债，开放，Step 8）；L26 chat 召回界 hybrid 默认 20 是有意上限（显式记录，非 bug）；L27 pydantic_settings 'lifespan' 前向引用警告（第三方库内部路径，卫生项，专门时机处理）；EX-③ 警告池归因漂移（挂账条件"任何壳扩展包面落地之日"，当前无触发面）；RW-②③④/SH-②③ 见 rewrite-http ledger（Step 6/7 承接）。L1–L25 已全部修复关闭。完整明细：`plans/2026-08-28-rewrite-http/ledger.md`（3 任务 + R 系列与执行期 Ruling + ride triage），先前见 `plans/2026-08-28-shell-exposure/ledger.md`、`plans/2026-08-28-infinite-flow/ledger.md`、`plans/2026-08-27-ext-pack/ledger.md`、`plans/2026-08-27-core-debt/ledger.md` 及 `plans/2026-08-26-acceptance-gap/ledger.md`、`plans/2026-08-23-snowel-core/`、`plans/2026-08-24-mcp-cli-shell/`、`plans/2026-08-24-writeback-retrieval-flow/`、`plans/2026-08-25-cascade-check/`、`plans/2026-08-25-web-ui/` 各自的 ledger.md。
