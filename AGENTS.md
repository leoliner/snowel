# Snowel 项目指令

## 项目说明

- Snowel：AI 小说生成引擎（雪花法），小说创作辅助工具——当前开发重点。

## 架构说明

- 当前重点是开发 Snowel 小说创作辅助工具。
- 总架构：一个引擎核心（snowel-core，纯 Python）+ 三个薄外壳：MCP Server（stdio，供 AI 客户端）、CLI（typer，本地管理）、FastAPI + React Web UI（最终面向作者的主创作界面）。
- 领域逻辑（雪花流程、图谱、级联检查、回写）只写在 snowel-core，外壳不得包含领域逻辑。

## 文档与工作流状态

- 需求上游：模拟推演 `docs/v1.0.0/details/sim-walkthrough-01.md`（示范小说走查，问题清单 #0~#31 + 技术决议）；需求定稿：`docs/v1.0.0/requirements.md`（C1~C12 裁决并入正文）；设计定稿：`docs/v1.0.0/design.md`（D1~D8 + E1~E5）；其余过程文档在 `docs/v1.0.0/details/`。
- 工作流遵循全局 spec-workflow skill（~/.agents/skills/spec-workflow/：simulation → requirements → design → testcases → plans → 执行）。
- 实现计划存储于 `docs/v1.0.0/plans/`；落地顺序：core（本体+事件溯源+基础查询）→ MCP/CLI 壳 → 回写环+混合检索 → Web 三栏界面。
- 当前阶段：设计与需求已完成交叉审计，下一步从 requirements.md + design.md 归纳黑盒测试用例文档（`docs/v1.0.0/testcases.md`），然后拆 snowel-core 实现计划（均需用户发话）。
