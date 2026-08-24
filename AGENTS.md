# Snowel 项目指令

## 项目说明

- Snowel：AI 小说生成引擎（雪花法），小说创作辅助工具——当前开发重点。

## 架构说明

- 当前重点是开发 Snowel 小说创作辅助工具。
- 总架构：一个引擎核心（snowel-core，纯 Python）+ 三个薄外壳：MCP Server（stdio，供 AI 客户端）、CLI（typer，本地管理）、FastAPI + React Web UI（最终面向作者的主创作界面）。
- 领域逻辑（雪花流程、图谱、级联检查、回写）只写在 snowel-core，外壳不得包含领域逻辑。

## 文档与工作流状态

- 需求上游：模拟推演 `docs/v1.0.0/details/sim-walkthrough-01.md`（示范小说走查，问题清单 #0–#31 + 技术决议）；需求定稿：`docs/v1.0.0/requirements.md`（C1–C12 裁决并入正文）；设计定稿：`docs/v1.0.0/design.md`（D1–D8 + E1–E5）；其余过程文档在 `docs/v1.0.0/details/`。
- 工作流遵循全局 skill 链：spec-workflow（`~/.agents/skills/spec-workflow/`：simulation → requirements → design → testcases → plans）+ dev-workflow（`~/.agents/skills/dev-workflow/`：计划批准后执行、ledger 归档、收尾与 PR 规约）。
- 黑盒测试用例：`docs/v1.0.0/testcases.md`（10 域 66 例，覆盖矩阵含 C1–C12/D1–D8/E1–E5）。
- 实现计划存储于 `docs/v1.0.0/plans/`；落地顺序：core（本体+事件溯源+基础查询）→ MCP/CLI 壳 → 回写环+混合检索 → Web 三栏界面。
- 当前阶段：**阶段三（回写环 + 混合检索 + 生成环）全部完成并合入 dev-1.0.0**（前半 T1–T12 于 2026-08-24、后半 T13–T18 于 2026-08-25 两波合入，全量 160/160 测试；交付 writeback/retrieval/llm/flow 四模块 + storage 扩展：镜像对账、FTS5+jieba、sqlite-vec、compose_context+审计、抽取分级、hook 三模式、active/偏离报告、auto 否决、ai_generate 生成环、小雪花/卷展开、revision，MCP 五面接线 + CLI export，not_wired 体系清空）。下一步：拆级联检查计划或 Web 三栏界面计划（需用户发话；级联计划 preflight：L4+L13+retcon stale 面+依赖图分析）。
- **跨计划遗留（新计划 preflight 必须携带）**：L4 `descendants` 无边时效过滤（级联检查计划）；L13 dead 单扫与 state_at 口径分叉+重复实现（级联计划同族统一）；L14 C5 stale 循环事务外标记（多端并发硬化）；L15 零事实章 appeared 丢失（接受边）；L16 Windows python.org 构建扩展加载崩 + core/壳同步发包（v1.0.0 发版前发布债）。L1–L12 已全部修复关闭。完整明细：`plans/2026-08-24-writeback-retrieval-flow/ledger.md`（两波 Ruling 全录 + 随行小项 triage），历史见 `plans/2026-08-23-snowel-core/ledger.md` 与 `plans/2026-08-24-mcp-cli-shell/ledger.md`。
