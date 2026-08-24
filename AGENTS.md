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
- 当前阶段：阶段三前半（回写环 + 混合检索，计划 Task 1–12）已实现完成并合入 dev-1.0.0（2026-08-24，20 提交 + merge，全量 121/121 测试通过；交付 writeback/retrieval/llm 三模块 + storage 扩展：镜像对账 D8/C1、FTS5+jieba、sqlite-vec C6、compose_context+审计 E3、抽取分级 §5.3、hook 三模式、active 判定 D5、偏离报告 C12、auto 否决 C2/C11；挂账 L1/L2/L5 已修复关闭）。计划后半（T13–T17 生成环 flow/ai_generate + T18 壳接线）待用户验收前半后执行——用户裁决分两波放行。
- **跨计划遗留（新计划 preflight 必须携带）**：L4 `descendants` 无边时效过滤、kinds 未消费（级联检查计划承接）；L6 confirm 两事务窗口的恢复入口（后半 T18 壳接线）；L7 心跳 renew 抛异常静默杀循环（后半多端并发必修）；L8 rebuild_embeddings 非原子（接线层包事务）；L9 hook/compose fallback 查询词用章节 id 无召回意义（T14 接线时改章关键词）；L10 fts paragraphs 返回分词串、引用提示需回查原文（T18 必带）；L11 零事实章 appeared 丢失（接受边）；L12 Windows python.org 构建 sqlite3 无 enable_load_extension（发布文档债）。L1/L2/L3/L5 已修复关闭。完整明细：`plans/2026-08-24-writeback-retrieval-flow/ledger.md`（含全部 Ruling 与随行小项 triage），历史见 `plans/2026-08-23-snowel-core/ledger.md` 与 `plans/2026-08-24-mcp-cli-shell/ledger.md`。
