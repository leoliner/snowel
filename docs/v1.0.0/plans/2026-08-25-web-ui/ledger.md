# Web 三栏界面计划 · 归档 Ledger

> 计划：`docs/v1.0.0/plans/2026-08-25-web-ui/plan.md`（14 任务 + W1–W9 裁决 + SSE 流式与暗色 UI 规约增补，2026-08-25 用户批准）。
> 分支：`feat/web-ui`（基于 dev-1.0.0 @ b954971）→ 合并 `351e75a` 系（--no-ff）。
> 本文件由 live ledger（`.superpowers/sdd/plan/progress.md`）收尾归档；live 副本随 worktree 删除销毁。

## 1. 执行总览

| 项 | 值 |
|---|---|
| 执行模式 | Subagent-Driven：每任务实现者 + 两席评审（spec 合规 + 质量）+ scoped re-review；终审独立席 + 一次修复波 + 定向复审 |
| 执行期 | 2026-08-25 单会话连续执行（T1–T14 + 终审修复波） |
| 测试基线 | 194/194（b954971）→ 后端 252/252 + 前端 vitest 71/71 + build 绿（351e75a） |
| 任务 | T1–T14 全部 complete；修环 7 轮（T1×1、T3×1、T5×1、T6×1、T8×1、T9×1、T11×1、T12×1——全部 R1 闭环）；终审 2 项 fix-before-merge 修复波全过 |
| 交付 | core：llm/chat.py 聊天代理引擎（JSON 指令循环 + 五工具白名单，确认类永排除）、queries 统计四件、mirror.reconcile dry_run、db check_same_thread+threadsafety fail-fast、L17 active_only 口径、L15/L18 补强。壳：web_server.py（会话/租约心跳+失租翻只读/12+ 只读端点/14+ 写端点/SSE 聊天/prose 端点/统计转发）+ CLI `snowel web`。前端 web/：Tailwind 暗色 tokens（ui-design-01 §2 逐值）、三栏壳、FlowTree/ProposalPanel（diff 着色+危险确认+L19 多键全展开）/GenerateForm、ProseEditor（正文加载+切章护栏+在途污染丢弃+失败基线重置）、ChatSidebar（SSE 消费+IME 守卫+打字机+refreshKey）、可视化四件 SVG |
| 提交链 | b954971 → 3bc6dd6(T1) → a9c37ae(T2) → 0634f43(T3) → e606b8a(T4) → b0e8174(T5) → 59dfeaa(T6) → a6f213e(T7,重派) → 6a18aa7(T8) → f5f0895(T9) → 71f4a06(T10) → 15eaccf(T11) → 04c88e1(T12) → ba94fa4(T13) → e5e1ae6(T14) → 351e75a(终审修复波) |

## 2. Preflight（控制器双查）

挂账裁决（继承计划）：L15+L18→T2；L17→T1；L19→关闭（裁决随计划）；L16 不携带。执行侧核对无漏。
冲突扫描表：T1↔存量调用方（active_only 排查清单）、T2↔test_hook 精确断言（预判未触发——appeared 已含）、T1/T7↔queries.py 顺序、T3↔T6/T8 门面与注入约定、T4-T8↔web_server.py 连续追加、T9-T13↔web/ 共享 api/types、T10↔T11 面板-编辑页耦合、T14↔全部。
执行前 Ruling：模型分级不可用（统一 general-purpose + 两席补偿）；T1 语义歧义点补锚不改语义；T4 异步基建条件分支。

## 3. Ruling 全录（决策—理由—若错的成本）

| # | 阶段 | Ruling | 若错的成本 |
|---|---|---|---|
| T1 | 评审 | brief 自带 seal 锚点弱守卫（is None 不可区分读到/过滤）→ 修正：b 挂 address 断言返回卷 id | 无 |
| T2 | 执行 | L15 前提不成立（appeared 已保真，cde7a1b 起）→ 关闭 + 锚钉住；"激活滞后"面维持接受边 | 无 |
| T3 | 执行 | 计划缺陷：brief 测试 fake 队列漏 ai_generate 内部调用 → 工具签名统一 (api,args,backend) 透传 + 补第三条响应 | 无 |
| T3 | 评审 | test 2 的 11 响应队列不钉 8 轮上限 → 缩至恰 8 条 + generate/tool_call 双计数断言（实现者纠正评审算术：8=7+1） | 无 |
| T5 | 评审 | /api/reconcile 挂只读面但 core 两分支写库（写穿透）→ **dry-run 方案**：mirror.reconcile(dry_run) + Web 端点纯状态读（MCP/hook 默认不变） | dry-run 状态滞后（下次可写对账自愈） |
| T6 | 评审 | reject 端点零覆盖 → 补锚（独立句柄读回 + reason 事件断言） | 无 |
| T8 | 执行 | ①chat 挂写守卫（工具含产提案写路径，C10 穿透）；②sqlite 线程冲突 → db.connect check_same_thread=False（threadsafety=3 serialized），**评审须核实 fail-fast 防线** | 非标准构建静默竞争——防线兜住 |
| T8 | 评审 | threadsafety 校验缺失（两席 Important）→ 显式 RuntimeError fail-fast | 无 |
| T9 | 评审 | tsconfig 缺 strict（模板默认疑似丢弃，T10-T13 护栏）→ 补齐 | 无 |
| T11 | 评审 | **flawed-brief：正文加载面缺失**（chapter_prose 可读无端点；空文本开局+保存=默认覆盖）→ 补 GET /api/chapters/{id}/prose + 编辑区加载 + savedText 基线=已加载正文；切章静默丢稿 → 三入口 ConfirmDialog 护栏；在途污染（质量席 Minor 同族）→ ref 比对丢弃（同修切章状态机） | 无 |
| T12 | 评审 | IME 组合态 Enter 误发送（中文主场景高频）→ isComposing 守卫 + 非空虚测试 | 无 |
| T12 | 执行 | onGoProposals refresh-only（无 tab 结构）→ T13 建 tab 后接线（已闭环） | 无 |
| 终审 | 评审 | 修复波范围 = Important 1（租约心跳）+ 2（prose 失败边缘）；search limit 统一 park 留检索计划；一行修复族（onGoGenerate/to_thread）park | 无 |
| 终审 | 收尾 | 人工走查（favicon/WCAG/分辨率/暗色一致）随 v1.0.0 验收由用户执行，清单归档；favicon 替换归验收前小补 | 视觉小瑕疵随验收发现 |

## 4. 任务完成记录（deferred minors 摘要）

- **T1** L17 口径统一（active_only 默认 + retraction 豁免 + fts 100 + snowflake 显式列）。minor×5（门面无锚/fts 无锚/docstring/冗余守卫/valid_until 哨兵）。
- **T2** L15 关闭 + L18 补强（空 retcon 守卫 + 7 锚）。minor×3。
- **T3** 聊天代理引擎（W1/W6：JSON 指令循环 + run/run_stream）。minor×5（resp 未截断/TypeError/4001/优先级/type 单数）。
- **T4** FastAPI 骨架（工厂同步 open+acquire、lifespan、守卫、SPA、CLI web、anyio）。实证教训（T5-T8 沿用）：触 db 端点必须 async def；starlette 基类捕获。minor×6。
- **T5** 12 只读端点 + reconcile dry-run Ruling。minor×3。
- **T6** 14 写端点 + 统一错误映射 + llm_backend 注入约定 + TC-SH-03 锚。minor×5。
- **T7** 统计四件（重派——首派 30.6 分钟超时零落盘）。解释性裁决：POV=props.pov.name、段落=prose_paragraph 行、beat 键 (volume,ch) 跨卷消歧（自抓串数 bug）。minor×4。
- **T8** SSE 聊天端点 + 聚合 + 写守卫 + threadsafety fail-fast。minor×4。
- **T9** React 骨架（Tailwind tokens 11 色逐值 + 三栏壳 + api/types 一比一 + strict）。自裁决采纳：vitest 4、色键非前缀。minor×6。
- **T10** 流程树/提案面板（diff 着色/危险确认/L19 全展开）/生成表单。minor×6（③⑦ 由 T11/T12 闭环）。
- **T11** 正文编辑页（修环补齐加载面+护栏+污染丢弃——**flawed-brief 最大补丁**）。minor×8（①失败边缘升级为终审 F2 已修）。
- **T12** 聊天侧栏（sse.ts/SSE 消费/IME 守卫/refreshKey 机制闭环 T10③）。minor×7。
- **T13** 可视化四件 + VizPanel tab + T12 携带项接线。minor×6。
- **T14** TC-SH-08 四面端到端 + README 登记 + 全量回归。双席一次过。

## 5. 终审与修复波

- **终审结论**：With fixes——W1-W9 全落地、测试声明实测属实、挂账清偿与 L19 关闭理由核实、跨任务零漂移、工程细节出色（threadsafety 配套/基类捕获注释/dry-run 双断言）。
- **fix-before-merge ×2**：①Web 租约无心跳 30s 静默过期（C10 破，测试盲区）②prose GET 失败错章覆盖（数据完整性）。
- **修复波**（351e75a，复审全过）：①daemon 心跳线程（独立连接、stale_after/3、失租翻只读+holder 快照、L5 终态无重抢、lifespan 先停后放；0.5s 真窗口偷租测试镜像 test_project.py）②proseError 消费 + 失败/错章/过渡帧三路基线重置 + 重试接线 + 判别力测试。
- **复审新观察**：测试套件 ~32 条 daemon 心跳线程泄漏至进程退出（per-test 隔离良性）→ 卫生债 L20。
- **Deferred triage 全表**：accept×~30 / park×9（见 live 记录；归档于本节摘要）。

## 6. 挂账表（跨计划 L 系列）

| # | 挂账 | 状态 | 承接 |
|---|---|---|---|
| L15 | 零事实章 appeared | **关闭**（T2 锚定） | — |
| L17 | inactive 反查口径 | **关闭**（T1） | — |
| L18 | 测试锚补强包 | **关闭**（T2） | — |
| L19 | Web 面板伴生 | **关闭**（violations 全量呈现 + 响应内嵌） | — |
| L16 | Windows 扩展/发包 | 开放 | v1.0.0 发版前发布债 |
| **L20**（新） | 测试卫生债：~32 daemon 心跳线程泄漏至进程退出（良性）；建议 session 级 autouse fixture 统一停线程 | 开放 | 下一计划/补丁 preflight |
| **L21**（新） | 检索统一：api.search 门面 limit=20 与 fts 默认 100 不一致；fts limit 收宽未达 API 层 | 开放 | 检索/补丁计划 |
| **L22**（新） | 联调/验收小补包：favicon 模板紫替换、reject_auto 条目形状校验（畸形 500）、onGoGenerate 死按钮接线、聚合端点 to_thread、ForeshadowMap 高拍数溢出、sse 非 2xx 回落清理、对比度 WCAG 核对与 1280/1920 走查（人工） | 开放 | v1.0.0 验收前小补 |

## 7. 验收

- 后端 252/252（基线 194 + 本计划 58）+ 前端 vitest 71/71 + build 绿；主目录合并后复验。
- 覆盖矩阵：TC-SH-03/04/06/08 全有锚（端到端 + 独立句柄 + 只读 409 + 绑定退出码）；§7.1 全要素落地（聊天红线三处锚定）。
- 豁免登记（计划 + 终审增补）：token 级 LLM 流；浏览器级 E2E（W3，验收人工走查）；rewrite_query；E4 扩展包。
