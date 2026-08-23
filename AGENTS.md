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
- 黑盒测试用例：`docs/v1.0.0/testcases.md`（10 域 66 例，覆盖矩阵含 C1~C12/D1~D8/E1~E5）。
- 实现计划存储于 `docs/v1.0.0/plans/`；落地顺序：core（本体+事件溯源+基础查询）→ MCP/CLI 壳 → 回写环+混合检索 → Web 三栏界面。
- 当前阶段：snowel-core 阶段一已实现完成并合入 dev-1.0.0（12 提交，37/37 测试通过）。下一步：拆 MCP + CLI 薄壳实现计划（需用户发话）。
- **跨计划遗留（新计划 preflight 必须携带）**：L1 `groups.validate` 畸形 `_schema` 版本串抛 ValueError（违背 D3 降级，接线属性组校验时修）；L2 `completeness.derive(props)` 无测试且文档签名漂移（接线前先补测试统一签名）；L3 `api.open()` 不校验库存在（壳计划承接）；L4 `descendants` 无边时效过滤、kinds 未消费（级联检查计划承接）。完整明细：`plans/2026-08-23-snowel-core/ledger.md`（SDD 执行归档）与同目录 `plan.md` 执行结果节。
