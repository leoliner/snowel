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
- 黑盒测试用例：`docs/v1.0.0/testcases.md`（9 域 76 例——历史文档"66 例/10 域""75 例"口径过时，TC-ON-17 随 Step 1 落锚；覆盖矩阵含 C1–C12/D1–D8/E1–E5）。
- 实现计划存储于 `docs/v1.0.0/plans/`；落地顺序：core（本体+事件溯源+基础查询）→ MCP/CLI 壳 → 回写环+混合检索 → Web 三栏界面 → 验收补丁 → 8 step 范围扩容链（Step 1 core 功能债已完成）。
- 当前阶段：**范围扩容 8 step 链执行中——Step 1 core 功能债已完成并合入 dev-1.0.0**（e388269，后端 280/280 + 前端 74/74 + build 绿；beat_deleted/L23/TOCTOU/两阶段恢复 + core 侧 minor 池清空）。**下一步：Step 2 扩展包机制方案 C（addendum §3.1：事件化挂载 + CLI 管理 + TC-EX-01~05 转正，minor 分摊 conftest fastapi 条件化）→ Step 3 预制包+skill → Step 4 壳端暴露 → Step 5 rewrite+HTTP → Step 6 手册+tour → Step 7 终核+人工走查（用户主刀）→ Step 8 L16 发布+PR 需发话）**；新会话执行入口：addendum §3–§4（Step 2 需求细则）+ `plans/2026-08-27-core-debt/ledger.md`（preflight 挂账必读）+ dev-workflow skill。
- **跨计划遗留**：L16 Windows python.org 构建扩展加载崩 + core/壳同步发包（发版前发布债，开放，Step 8）；L24 扩展包机制 TC-EX 全域（开放，Step 2/3）；L25 壳端暴露部分（Web 灵感/拍操作、MCP advanced，开放，Step 4——core 部分已随 Step 1 关闭）；L26 chat 召回界 hybrid 默认 20 是有意上限（显式记录，非 bug）；L27 全量套件 pydantic_settings 警告（卫生项，新登记）。L1–L23、L25 core 部分已修复关闭。完整明细：`plans/2026-08-27-core-debt/ledger.md`（4 任务 + 终审 Ruling 全录 + triage），历史见 `plans/2026-08-26-acceptance-gap/ledger.md` 及 `plans/2026-08-23-snowel-core/`、`plans/2026-08-24-mcp-cli-shell/`、`plans/2026-08-24-writeback-retrieval-flow/`、`plans/2026-08-25-cascade-check/`、`plans/2026-08-25-web-ui/` 各自的 ledger.md。
