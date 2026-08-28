# v1.0.0 范围扩容 Step 5：rewrite_query + streamable HTTP

> 日期：2026-08-28。来源：范围增补 `requirements-addendum.md` §5 / §8（Step 5 行）——8 step 链第 5 步。
> 性质：功能实现计划——语义已定稿（rewrite 默认开+失败回落审计 rewrite_failed；HTTP 保守分层 stdio 默认/127.0.0.1/0.0.0.0 强制 token），本计划做工程拆解与实现级裁决。
> 上游素材：`plans/2026-08-28-shell-exposure/ledger.md`（preflight：SH-① 本步消化）；地基事实——`rewrite_query` 桩已预留于 `llm/ports.py:28-30`（签名含 backend 注入位），三路检索收敛于 `hybrid.search`，FastMCP 原生 `streamable-http` + `token_verifier`（SDK 自动 401）。

## 1. 背景与范围

| 项 | 内容 | 黑盒锚 |
|---|---|---|
| rewrite_query | config `retrieval.rewrite` 默认 **true**；改写层前置到所有查询入口（api.search、compose_context 兜底召回、聊天检索——三路全收敛于 `hybrid.search`，前置一次即三处统一）；改写 LLM 异常/超时 → 回落原始查询 + `retrieval_audit` 记 `rewrite_failed`；测试注入确定性改写端 | TC-RT-07 转正 |
| streamable HTTP | MCP 默认 stdio 不变；`snowel mcp --http` 显式开启（默认绑 127.0.0.1、`--port` 可配）；绑 `0.0.0.0`/`::` 强制 `--token <bearer>` 否则拒绝启动；token 校验失败 401（FastMCP 原生 BearerAuth） | TC-SH-12 转正 |
| minor 分摊 | SH-① 拍操作响应键名统一（web `moved`/`deleted` vs MCP `event_seq` + delete 丢 seq）；reject_auto 注释纠错（"→ 500"应为"→ 200（假成功）"，acceptance-gap ledger） | — |
| 文档落锚 | testcases.md §7 RT 域 +TC-RT-07、§9 SH 域 +TC-SH-12（79→81 例）+ §11 联动 | — |

不在范围：Web/MCP 的扩展包面（EX-③ 触发条件不成立）；rewrite 的 UI 配置面（config 表直改即可，手册 Step 6）；FTS 8-token 截断 nit（历史挂账不携带）。

## 2. Global Constraints

- 领域逻辑只在 snowel-core：rewrite 层实现于 core（ports 桩 + hybrid 前置）；CLI/MCP 壳只接线。
- MCP 六工具不变式不动；stdio 默认路径零变化（回归锚 `test_exactly_six_tools` + 既有全量）。
- `hybrid.search(conn, q, limit, mode)` 对外位置签名不可变（既有 monkeypatch 锚 `tests/api/test_api.py:67` 约束）——backend 以**带默认值的关键字参**追加。
- 检索热路径性能：开关关闭时零 LLM 调用、仅一次 config 读（`config.get(conn, "retrieval.rewrite", True)` 早退）；关闭 = 纯确定性路径（审计零新增行）。
- 每任务 TDD、conventional commits、测试就近落文件；testcases.md 落锚 grep 实证。
- 全量基线：dev-1.0.0 @ 34703dd，后端 318 + 前端 vitest 91 + build 绿。

## 3. Preflight 挂账裁决（同版本已归档 ledger 全量双查）

| 挂账 | 内容 | 裁决 | 去向 |
|---|---|---|---|
| **SH-①** | 拍操作响应键名两壳不对称（web `moved` vs MCP `event_seq`；web delete 丢 seq） | **携带**——统一为 `event_seq`（merge/delete 双端点补齐），前端不消费响应体零影响，同步 Web 契约断言 | Task 3 |
| reject_auto 注释 | web_server.py:330-331 "→ 500" 应为 "→ 200（假成功）"（acceptance-gap ledger minor 池，e11e14a nit） | **携带** | Task 3 |
| SH-②③④ | MCP 缺参文案 / a11y 与容错 polish / TC-SH-02 枚举与预览新鲜度 | 不携带 | Step 6 / Step 7 |
| EX-③ | 警告池归因漂移 | 不携带（触发条件未变） | 条件触发之日 |
| L16 / L26 / L27 | 发布债 / 记录性 / 卫生项 | 不携带 | Step 8 / — / 专门时机 |
| TC-RT-07 / TC-SH-12 | addendum §5 建议用例（未列入 testcases.md） | **携带**——转正落锚 | Task 3 |

任务间共享文件冲突：T1 独占 core 检索侧（ports/hybrid/audit/context）+ tests/retrieval、tests/llm、tests/api；T2 独占 cli.py + mcp_server.py（main 函数）+ tests/shell/test_cli.py、test_mcp_server.py；T3 独占 web_server.py（注释+两端点键名）+ test_web_server.py + testcases.md + tests/README.md。无并行冲突。

## 4. 计划级设计裁决（预登记 Ruling，随计划批准生效）

| # | 裁决 | 理由 | 若错的成本 |
|---|---|---|---|
| R1 | rewrite 实现翻转 `llm/ports.py` 预留桩：`rewrite_query(query, context, backend=None) -> str \| None`（None/异常 = 失败回落信号）；开关与模型键 `config.get(conn, "retrieval.rewrite", True)` / `retrieval.rewrite_model`（仿 extraction.small_model 先例，不设走 backend 默认模型）；prompt 要求输出改写后查询词，产出经 strip 非空校验 | 桩签名与本需求同构（context 放检索词原文、backend 放注入位）；零新文件 | 改签名则同步桩测试翻转一处 |
| R2 | 三入口统一 = **`hybrid.search` 内部前置**：追加带默认关键字参 `backend=None`（None 时惰性 `ports.get_backend(conn)`，保持既有位置签名与 monkeypatch 锚兼容）；关闭开关时早退零 LLM 调用。**api.search 不加每次审计**——仅当改写实际发生（生效或失败）时落一条 `strategy="search"` 审计行（bundle 增 `"rewrite": {"original", "rewritten"}` 或 `{"failed": true, "original"}`，零 schema 变更）；compose_context 既有审计行天然携带同一 rewrite 键 | 三路收敛点唯一，前置一次即全覆盖；高频 search 全量落审计会让审计表膨胀，"检索词变化可见于审计"只要求改写发生的场合可见 | 若要全量检索审计，去掉条件一行 |
| R3 | MCP HTTP 用 **FastMCP 原生**：`FastMCP("snowel", host=..., port=..., token_verifier=<常量比较 verifier 小类>)` + `mcp.run("streamable-http")`（SDK 自动装 BearerAuthMiddleware，失败 401 invalid_token——不自写 middleware）；host/port 经构造器 settings 传入；`main(http=False, host, port, token=None)` 参数化，stdio 路径零变化 | SDK 原生能力即为本需求设计；自写 middleware 是重复造轮子 | token 机制若不满足再换 auth=AuthSettings |
| R4 | CLI 新增 `snowel mcp` 子命令，完全仿 `web` 命令形状：`--project`、`--http` flag、`--host` 默认 "127.0.0.1"、`--port` 默认 8642、`--token` Optional；**启动守卫在 shell 侧**：`--http` 且 host ∈ {"0.0.0.0","::"} 且无 token → RED secho + Exit(1)（仿 cli.py web 先例）；无 `--http` 直接调 `mcp_server.main()` 保持 stdio 默认 | `snowel mcp --http` 是 addendum 字面入口；web 命令是同构先例 | 挪入口则同步文档 |
| R5 | SH-① 统一方案：Web `beats/merge` 响应键 `moved` → `event_seq`、`beats/delete` 返回补 `event_seq`（对齐 MCP 形状）；同步 Web 契约测试断言（前端组件不消费响应体零影响）；reject_auto 注释按 acceptance-gap ledger 执行-1 裁决改"→ 200（假成功）" | 同门面同语义应同形状；成本 2 端点 + 2 断言 | 前端将来消费时再改成本更高 |

## 5. 文件结构总表

| 文件 | 动作 | 任务 |
|---|---|---|
| `src/snowel_core/llm/ports.py` | 翻转 `rewrite_query` 桩为实现（R1） | T1 |
| `src/snowel_core/retrieval/hybrid.py` | `search` 前置改写层 + `backend=None` 关键字参（R2） | T1 |
| `src/snowel_core/retrieval/audit.py` | bundle 增 `rewrite` 键的写入支持（若需 helper） | T1 |
| `src/snowel_core/api.py` | search 路径的条件审计（若落点在门面而非 hybrid 内，实现者依测试可注入性裁量并在报告说明） | T1 |
| `shell/src/snowel/cli.py` | 新 `snowel mcp` 子命令 + 启动守卫（R4） | T2 |
| `shell/src/snowel/mcp_server.py` | `main()` 参数化 http/host/port/token + FastMCP 构造器传参 + 常量比较 verifier（R3） | T2 |
| `shell/src/snowel/web_server.py` | beats/merge/delete 响应键统一 + reject_auto 注释纠错（R5） | T3 |
| 测试 | `tests/llm/test_backend.py`（桩翻转）、`tests/retrieval/test_context.py` 或新 `test_rewrite.py`、`tests/api/test_api.py`（search 审计）、`tests/shell/test_cli.py` + `test_mcp_server.py`（T2）、`tests/shell/test_web_server.py`（T3） | — |
| `docs/v1.0.0/testcases.md` | §7 +TC-RT-07、§9 +TC-SH-12、§11 联动（79→81 例） | T3 |
| `tests/README.md` | 反向索引同步 | T3 |

## 6. 任务清单

### Task 1: rewrite_query（TC-RT-07 / R1+R2）

**实现**：
- `ports.rewrite_query` 翻转：backend 非 None 且开关开 → `backend.generate(prompt, model=config.get(conn, "retrieval.rewrite_model") or None)`；产出 strip 非空且 != 原文才算改写生效；任何异常（含超时）→ 返回 None。**签名需补 `conn` 参数**（读 config 必需）——桩签名扩一处，同步桩测试翻转。
- `hybrid.search(conn, q, limit=20, mode="hybrid", backend=None)`：开头改写段——开关关（config False）→ 原样直查零开销；开关开 → rewrite → 生效（非 None 且非空）以改写词检索 + 条件审计；失败（None/异常）以原词检索 + `rewrite_failed` 条件审计。条件审计 = strategy `"search"`、locate 记原文、bundle.rewrite 记明细。
- 审计写入：扩 `audit.record` 调用形状或加 helper（bundle JSON 自由键，零 schema 变更）。

**测试**（addendum §5.1 断言清单逐条 + FakeBackend 注入）：
```python
# tests/llm/test_backend.py——桩翻转
def test_rewrite_query_rewrites_with_backend()   # FakeBackend 返回改写词 → 生效
def test_rewrite_query_failure_returns_none()    # FakeBackend 抛异常 → None（回落信号）
# tests/retrieval/test_rewrite.py（新文件）
def test_rewrite_changes_search_terms_visible_in_audit()   # TC-RT-07 前半：改写生效、
                                                           # 审计可见 original→rewritten
def test_rewrite_failure_falls_back_with_marker()          # 失败回落：结果仍出 + 审计
                                                           # rewrite_failed 标记
def test_rewrite_disabled_pure_deterministic()             # 关闭开关：零审计行、检索直查、
                                                           # backend.calls 为空
def test_compose_context_fallback_recalls_rewritten()      # 入口 B：compose_context 兜底召回
                                                           # 走改写词（经 audit bundle 或
                                                           # FakeBackend.calls 断言）
```
既有 `test_rewrite_query_stub_returns_none` 翻转；`tests/api/test_api.py` monkeypatch 锚回归（hybrid 位置签名不变）；全量回归 318 绿。

### Task 2: streamable HTTP（TC-SH-12 / R3+R4）

**实现**：
- `mcp_server.main(http=False, host="127.0.0.1", port=8642, token=None)`：http=False 走既有 stdio 路径零变化；http=True → 构造 FastMCP 时传 host/port/token_verifier（token 非 None 时；verifier = 小类 `verify_token` 用 `secrets.compare_digest` 常量比较，返回 AccessToken 或 None）→ `mcp.run("streamable-http")`。
- `cli.py` 新 `snowel mcp` 子命令（R4 形状）：启动守卫（0.0.0.0/:: 无 token → RED + Exit 1）→ 转 `main(...)`。

**测试**（addendum §5.2 断言清单）：
```python
# tests/shell/test_cli.py
def test_mcp_command_wildcard_requires_token()   # --http --host 0.0.0.0 无 token → exit 1 + RED 文案；
                                                 # 带 token / 默认 host → 通过守卫（mock main 捕获参数）
# tests/shell/test_mcp_server.py
def test_stdio_regression_unchanged()            # 既有全量即回归锚（显式跑 test_exactly_six_tools
                                                 # 与目录断言，零新断言也登记在报告）
def test_http_app_tool_enumeration_matches_stdio()  # streamable_http_app() + httpx ASGITransport
                                                    # （lifespan 处理：session_manager.run 手动起停或
                                                    # LifespanManager，实现者按依赖现状裁量并报告）→
                                                    # 工具枚举与 stdio 内存直连同集（TC-SH-01 同断言）
def test_http_wrong_token_401()                  # token_verifier 注入后无/错 Authorization → 401
```
守卫测试与 HTTP app 测试不启真端口（ASGITransport 足够；如 lifespan 处理需要新依赖，STOP 报告控制器裁决是否引入 asgi-lifespan）。

### Task 3: minor 包 + 落锚收口（SH-① / R5）

| 子项 | 落点 | 修法 | 锚 |
|---|---|---|---|
| SH-① 键名统一 | `web_server.py` beats/merge、beats/delete | `moved`→`event_seq`、delete 返回补 `event_seq`；同步 test_web_server 断言 | 契约测试一例 + MCP 侧既有断言对照 |
| reject_auto 注释 | `web_server.py:330-331` | "→ 500" 第二分支改 "→ 200（假成功）"（acceptance-gap ledger 执行-1 口径） | 注释即锚（评审核语义） |
| TC-RT-07 落锚 | testcases.md §7 RT 表 | 按实现语义写行（给定：config 开+改写端；操作：检索；预期：改写生效见于审计/失败回落+标记/关闭纯确定性） | — |
| TC-SH-12 落锚 | testcases.md §9 SH 表 | 同上（stdio 默认/--http 127.0.0.1/0.0.0.0 强制 token/错 token 401） | — |
| §11 联动 + README | testcases.md §11、tests/README.md | 范围行更新 + 反向索引；grep 实证防虚登记 | — |

### 收尾（dev-workflow §7 全流程）

终审（全分支独立评审）→ 修复波 + 定向复审 → 合并 `dev-1.0.0`（合并结果主仓库全量重跑：pytest + vitest + `npm run build`；worktree 干活后先 editable 重装校正指向）→ 删 worktree/feat 分支 → ledger 归档 `plans/2026-08-28-rewrite-http/ledger.md` → 更新 AGENTS.md 阶段指针（Step 5 完成 → Step 6 手册+tour）→ 推送 dev。

## 7. 执行参数

| 项 | 值 |
|---|---|
| 模式 | Subagent-Driven（3 任务：T1 core 检索、T2 壳传输、T3 minor+落锚；T1/T2 无共享文件可并行评审但派发仍串行——SDD 纪律；两席评审/任务；controller 不写码） |
| worktree | `D:\Code\snowel-rewrite-http`（兄弟目录，从 dev-1.0.0 切） |
| 分支 | `feat/rewrite-http` → merge --no-ff 回 `dev-1.0.0` |
| 测试基线 | 合并前 318 + 91 + build 绿为底（预计后端净增 ~10） |
| 修环上限 | 5 轮（R1-3 原实现者，R4-5 换强模型新派） |
| Step 6 接口 | 手册+tour（addendum §6）；SH-②③④ 与 rewrite 开关说明进手册章节 |
