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
- 黑盒测试用例：`docs/v1.0.0/testcases.md`（9 域 83 例——历史文档"66 例/10 域""75 例""76 例"口径过时；覆盖矩阵含 C1–C12/D1–D8/E1–E5）。
- 实现计划存储于 `docs/v1.0.0/plans/`；落地顺序：core（本体+事件溯源+基础查询）→ MCP/CLI 壳 → 回写环+混合检索 → Web 三栏界面 → 验收补丁 → 8 step 范围扩容链（Step 1 core 功能债、Step 2 扩展包机制、Step 3 预制包+skill 双落、Step 4 壳端暴露、Step 5 rewrite+HTTP、Step 6 手册+tour 已完成）。
- 当前阶段：**v1.0.0 收尾——Step 7 人工走查中途转入 Web 重构设计环（2026-08-29）**。走查发现 W-1~W-8 已复现落盘（`details/walkthrough-findings-01.md`）；用户裁决 Web 重新设计：设计稿 `details/web-redesign/demo.html`（交互式）+ `design-notes-01.md`（三项裁决 + R-1/R-2 + 11 块后端缺口基线），**屏 A/B/C/切换器/设置已确认，D~H 待用户过目；定稿前不改实现代码**。新会话执行入口：**`details/handoff-web-redesign-01.md`**（设计环）+ `details/handoff-v1-final.md`（Step 8 发布债：RW-① mcp>=1.29 + Release 打包，均需发话）。
- **跨计划遗留**：L16 Windows python.org 构建扩展加载崩**已验证证伪关闭**（2026-08-29，`details/l16-windows-verification.md`——官方构建带 `enable_load_extension`，jieba/sqlite-vec/`SnowelAPI` 全链路通过）+ core/壳同步发包 + **mcp 依赖下限提版（RW-①：`mcp>=1.2` 陈旧，新 SDK 面需 `>=1.29`）**（发版前发布债，开放，Step 8）；L26 chat 召回界 hybrid 默认 20 是有意上限（显式记录，非 bug）；L27 pydantic_settings 'lifespan' 前向引用警告（第三方库内部路径，卫生项，专门时机处理）；EX-③ 警告池归因漂移（挂账条件"任何壳扩展包面落地之日"，当前无触发面）；RW-④/SH-②③ 已分别随 Step 5/6 关闭；MT-①～④ 走查候选池见 manual-tour ledger。L1–L25 已全部修复关闭。完整明细：`plans/2026-08-28-manual-tour/ledger.md`（4 任务 + R 系列与执行期 Ruling + ride triage），先前见 `plans/2026-08-28-rewrite-http/ledger.md`、`plans/2026-08-28-shell-exposure/ledger.md`、`plans/2026-08-28-infinite-flow/ledger.md`、`plans/2026-08-27-ext-pack/ledger.md`、`plans/2026-08-27-core-debt/ledger.md` 及更早各 ledger。
