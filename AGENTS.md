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
- 当前阶段：**Web 三栏界面计划（FastAPI + React + core 聊天代理）全部完成并合入 dev-1.0.0**（2026-08-25 单会话完成 T1–T14 + 终审修复波；后端 252/252 + 前端 vitest 71/71 + build；交付 core 聊天代理引擎 llm/chat.py——JSON 指令循环 + 五工具白名单、确认类永排除（§7.1 红线），统计四件，reconcile dry_run，db 线程安全 fail-fast；FastAPI 薄壳 web_server.py——租约心跳 + 失租翻只读、只读面/写面/SSE 聊天流式/统计转发 + CLI `snowel web`；React 前端 web/——Tailwind 暗色 tokens（ui-design-01 规约）、三栏壳、流程树/提案面板/生成表单、正文编辑页、聊天侧栏（SSE + IME 守卫）、可视化四件；挂账 L15/L17/L18/L19 关闭）。**v1.0.0 全部四步计划（core → MCP/CLI 壳 → 回写环+检索+级联 → Web）完成**。下一步：v1.0.0 验收（66 例终核 + L22 小补包：favicon/WCAG/分辨率走查等 → 发版前 L16 发布债）→ dev → main PR（需用户发话）。
- **跨计划遗留（验收/发版前处置）**：L16 Windows python.org 构建扩展加载崩 + core/壳同步发包（发版前发布债）；L20 测试卫生债（daemon 心跳线程泄漏至进程退出，良性）；L21 检索统一（api.search 门面 limit=20 与 fts 100 不一致）；L22 联调/验收小补包（favicon 模板紫、reject_auto 形状校验、onGoGenerate 接线、聚合端点 to_thread、ForeshadowMap 高拍数溢出、sse 非 2xx 回落、WCAG 对比度与 1280/1920 人工走查）。L1–L19 已全部修复关闭。完整明细：`plans/2026-08-25-web-ui/ledger.md`（14 任务 Ruling 全录 + 终审 triage 全表），历史见 `plans/2026-08-23-snowel-core/ledger.md`、`plans/2026-08-24-mcp-cli-shell/ledger.md`、`plans/2026-08-24-writeback-retrieval-flow/ledger.md` 与 `plans/2026-08-25-cascade-check/ledger.md`。
