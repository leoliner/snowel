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
- 当前阶段：**级联检查计划（consistency 引擎 + 冻结线 + retcon）全部完成并合入 dev-1.0.0**（2026-08-25 经两个会话完成 T1–T11 + 终审修复波，全量 194/194 测试；交付 consistency 六模块 engine/rules/wiring/seal/retcon/foreshadow：三类检查+护栏+棘轮、全量/轻量两档、四写入点接线、封卷与冻结线拦截（联合语义+撤回复活堵漏）、retcon 流程（P5 提案时分析+P4 精确 stale+P3 改轨）、伏笔注册，storage 扩展 deathbeat/sealed_volumes，MCP writeback 三 action + CLI seal + confirm cascade 键；挂账 L4/L13/L14 清偿）。下一步：Web 三栏界面计划（v1.0.0 最后一块，需用户发话；preflight 携带 L15/L17/L18/L19）。
- **跨计划遗留（新计划 preflight 必须携带）**：L15 零事实章 appeared 丢失（接受边）；L16 Windows python.org 构建扩展加载崩 + core/壳同步发包（v1.0.0 发版前发布债）；L17 inactive 实体反查口径统一（edges_of/get_node/fts/snowflake 列耦合/dependents 含已撤回边）；L18 测试锚与守卫补强包（微裁决锚、空 retcon 守卫、MCP retcon 分派协议测试、TC-CC-04 接线锚）；L19 Web 面板伴生（多键矛盾折叠展开、_last_cascade 单槽窗口改读 payload）。L1–L14 已全部修复关闭。完整明细：`plans/2026-08-25-cascade-check/ledger.md`（两会话 Ruling 全录 + 终审 triage 全表），历史见 `plans/2026-08-23-snowel-core/ledger.md`、`plans/2026-08-24-mcp-cli-shell/ledger.md` 与 `plans/2026-08-24-writeback-retrieval-flow/ledger.md`。
