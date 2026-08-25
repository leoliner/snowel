# Web 三栏创作界面（FastAPI + React + core 聊天代理）实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 落地需求 §7.1 与 TC-SH-03/04/06/08：Web 三栏创作界面（左流程树 / 中正文编辑页 / 右工作区 + 常驻聊天侧栏完整工具代理），FastAPI 薄壳 + React 前端，聊天代理引擎进 core；并清偿挂账 L15/L17/L18，关闭 L19（伴生项随本计划交付形态自然解决）。

**Architecture:** 领域编排（聊天代理循环、统计查询）进 snowel-core（`llm/chat.py` 代理引擎 + `storage/queries.py` 统计四件）；FastAPI 后端为纯转发薄壳（`shell/src/snowel/web_server.py`，一比一映射 api 门面，铁律 1）；React 前端独立工程（顶层 `web/`，Vite + TS，构建产物由后端静态 serve）。代理协议为 JSON 指令循环（每轮 LLM 返回 `{"tool":..., "args":...}` 或 `{"reply":...}`，core 执行工具并回注观察，轮次上限 8），不依赖 litellm 原生 function-calling。

**Tech Stack:** 后端 FastAPI + uvicorn + httpx（测试，ASGITransport）；前端 React 18 + Vite + TypeScript + vitest + @testing-library/react；LLM 复用 core `GenerationBackend`（测试注入 FakeBackend，零真网调用）。

**Spec:** `docs/v1.0.0/requirements.md`（§7.1 Web 界面、§7.2 项目绑定、§8 技术栈、铁律 1–5）、`docs/v1.0.0/design.md`（§5 模块划分、§7 三口、§10 对外壳约束）、`docs/v1.0.0/testcases.md`（TC-SH-03/04/06/08）

## Global Constraints

- Python ≥3.12；领域逻辑只在 snowel-core；Web 后端只 import `snowel_core.api`（铁律 1）；Web 路由映射 api 门面一比一，无编排逻辑（design §10）。
- 确认动作永远落在结构化面板（§7.1 红线）：**聊天代理工具集不含任何确认/否决类动作**（confirm/reject/confirm_retcon/seal 均排除），代理只可生成提案。
- LLM 调用唯一实现处是 core/llm（铁律 2）；全部测试确定性（FakeBackend 队列驱动，零真网、零真 LLM）。
- 项目绑定：一个 server 进程绑定一个项目工作区（启动参数指定，TC-SH-06）；租约获取失败 → 降级只读并明确提示（TC-SH-04，C10）。
- 投影器是物化唯一写入口（E2）；Web 端点只经 api 门面写，不直连 storage 写。
- conventional commits；每任务一提交；后端测试进 `tests/shell/`（web_server 同属壳），core 测试进对应模块目录，均在 `tests/README.md` 登记；前端测试在 `web/` 内（vitest）。
- 沿用现有代码风格：sqlite3.Row、dict 返回、中文 docstring、文件首行 `# src/...` 路径注释。
- 基线：dev-1.0.0 @ fcc3947，全量 194/194。

## Preflight 挂账裁决（同版本已归档 ledger）

| # | 挂账 | 裁决 | 落点 |
|---|---|---|---|
| L15 | 零事实章 appeared 丢失 | **携带，Task 2 修复**（extract 返回保真） | writeback/extract.py |
| L17 | inactive 实体反查口径统一（edges_of 无 active 过滤、get_node 无 active 过滤、fts limit=20、snowflake is_dead 行隐式列耦合、dependents 提示面含已撤回边） | **携带，Task 1 统一** | storage/queries.py + consistency/rules.py docstring |
| L18 | 测试锚与守卫补强包（空 retcon 无守卫、MCP confirm retcon 分派无协议测试、TC-CC-04 三类统一跑无接线锚、撤回边/拍地址微裁决无锚、retraction→edge 反查无锚） | **携带，Task 2 补齐** | 对应测试文件 |
| L19 | Web 面板伴生（多键矛盾折叠展开、_last_cascade 单槽窗口） | **关闭**：Web 面板直接展示 confirm 响应携带的 `cascade.violations` 全量（多键天然展开，不经 diff_proposal 折叠）；_last_cascade 窗口在 Web 单用户场景不可达（confirm 端点响应即时内嵌 cascade，与 MCP 同形态，单槽缓存非 Web 数据源） | — |
| L16 | Windows 扩展加载/发包 | 不携带（发布债，发版前） | — |

## 计划级设计裁决（预登记 Ruling，执行期可依证修订）

| # | 裁决 | 理由 | 若错的成本 |
|---|---|---|---|
| W1 | **聊天代理引擎进 core**：`snowel_core/llm/chat.py`，JSON 指令循环协议——每轮 LLM 返回 `{"tool": name, "args": {...}}` 或 `{"reply": text}`；core 执行工具 → 观察结果（JSON 截断至 4000 字符）回注下一轮；轮次上限 8 超限强制收束为 reply；工具集 = `generate`（ai_generate）/`expand_chapter`/`expand_volume`/`query`（search/find_nodes/get_node/state_at）/`register_foreshadow`；确认类动作永不在工具集（§7.1 红线） | 铁律 1：意图路由是领域编排；GenerationBackend 是纯文本口，自建 JSON 协议与 parse_llm_json 围栏容忍模式一致且测试确定 | 协议表达力弱于原生 function-calling——提示词工程可补，v1 够用 |
| W2 | **布局**：后端 `shell/src/snowel/web_server.py`（app 工厂 + `snowel web` CLI 子命令，uvicorn 程序内启动）；前端顶层 `web/`（Vite + TS）；`web/dist` 由后端静态 serve，目录缺失时跳过挂载（无 node 环境跑后端测试不破） | 三壳平铺现状 + node 工程不进 Python 包（用户裁决 2） | 无 |
| W3 | **测试策略**：后端 pytest + httpx AsyncClient（ASGITransport，不真起端口）+ FakeBackend；前端 vitest + testing-library 关键交互薄锚（API 层 mock）；TC-SH-08 的端到端锚在 API 级（各端点组合断言），浏览器级 E2E 不做（豁免登记） | 黑盒用例描述的是"界面打开加载项目"的可观察行为，API 级组合 + 前端组件锚已覆盖断言面 | 浏览器渲染回归可能漏——v1.0.0 验收人工走查补 |
| W4 | **可视化四件 = core 统计查询 + 前端轻量 SVG**：`queries.stats_pov/stats_foreshadow/stats_relations/stats_pacing` 进 core（纯统计非 AI），api 门面暴露，端点一比一转发；前端不引重型图库（手写 SVG/简单条形） | 铁律 1（图谱查询是领域）+ 依赖最小化 | 视觉朴素——统计信息完整，可接受 |
| W5 | **租约**：`snowel web` 启动即 `acquire_lease("web:<pid>")`，失败 → 只读会话（`/api/session` 返回 `{"readonly": true, "holder": ...}`，前端顶部横幅；写端点统一 409）；server 退出 release | C10/TC-SH-04；进程级租约与 MCP/CLI 同源 | Web 长开占租约挤占 MCP 写——作者单机单写场景，可接受 |
| W6 | **聊天 SSE 流式（回合级事件流）**：core `chat.run_stream` 为同步生成器逐事件 yield；`POST /api/chat/stream` 以 StreamingResponse 推 SSE（`data: {事件JSON}\n\n` 每事件一行，末尾 `{"type":"done","proposal_ids":[...]}` 收尾），FastAPI 经 `iterate_in_threadpool` 线程池迭代 core 生成器；`POST /api/chat` 非流式聚合版保留（`list(run_stream())`，简单客户端/测试用）；前端 fetch ReadableStream + 行解析消费（EventSource 不支持 POST）；客户端断开 → 生成器 GeneratorExit 自然终止，已入队提案保留（符合语义）。**LLM 生成内部仍整段**（GenerationBackend 不动）：指令协议是 JSON，逐 token 推不完整 JSON 无意义；reply 打字机效果由前端渐显动画承担（纯视觉） | 体验：多轮代理每步实时上屏（最大痛点）；成本：core 生成器化 + SSE 编码，风险低（threadpool 迭代同步生成器是成熟模式） | token 级 LLM 流缺失（豁免登记）——若未来要真 token 流，需给 backend 加 `stream()` 口并重设计输出协议 |
| W7 | **中栏编辑页写路径**：章节编辑保存 = 旧文对账后 `reregister_prose` 或镜像直写经 `reconcile_prose` 状态提示；外部未对账编辑（挂账 manual confirm 覆盖提示）= 确认 prose 提案前面板调 `reconcile_prose()` 展示 changed 清单，作者显式选择 | writeback ledger 挂账"manual 模式 confirm 静默覆盖未对账外部编辑（Web UI 提示面）"的承接 | 无 |

## 文件结构总表

| 文件 | 动作 | 职责 |
|---|---|---|
| `src/snowel_core/storage/queries.py` | 修改 | L17 口径统一 + 统计四件查询 |
| `src/snowel_core/consistency/rules.py` | 修改 | dependents 提示面口径 docstring（L17） |
| `src/snowel_core/writeback/extract.py` | 修改 | L15 appeared 保真 |
| `src/snowel_core/llm/chat.py` | 新建 | 聊天代理引擎（指令循环 + 工具注册表 + 观察回注） |
| `src/snowel_core/api.py` | 修改 | +chat/统计四件门面 |
| `shell/src/snowel/web_server.py` | 新建 | FastAPI app 工厂 + 路由（只读面/写面/聊天/统计/静态） |
| `shell/src/snowel/cli.py` | 修改 | +`snowel web` 子命令 |
| `shell/pyproject.toml` | 修改 | +fastapi/uvicorn/httpx 依赖 |
| `web/` | 新建 | React + Vite + TS 工程（src/ 三栏布局、api client、组件、vitest） |
| `tests/shell/test_web_server.py` | 新建 | 后端 API 测试（httpx ASGITransport） |
| `tests/core 侧测试` | 修改 | L17/L18/chat/统计对应目录追加 |

---

### Task 1: L17——inactive 实体反查口径统一

**Files:**
- Modify: `src/snowel_core/storage/queries.py`（edges_of/get_node）、`src/snowel_core/consistency/rules.py`（dependents docstring）、`src/snowel_core/flow/snowflake.py`（is_dead 行耦合收紧，若可行）
- Test: `tests/storage/test_queries.py`（追加）、`tests/consistency/test_rules_dependency.py`（追加）

**Interfaces:**
- Consumes: 现有 `edges_of(conn, node_id)`、`get_node(conn, node_id)`、`fts.search`、snowflake dead 扫描。
- Produces:
  - `queries.edges_of(conn, node_id, active_only=True)`：新参默认 True——仅返回两端节点均 active=1 且边未撤回的边；`active_only=False` 保留旧行为（终审 Minor 2：dependents 提示面若要含历史可显式关闭）。撤回边判定：边行无 active 列（retraction 对边是软删——以两端节点 active 为准），实现以现有 schema 为准，接口契约以测试为准。
  - `queries.get_node(conn, node_id, active_only=True)`：默认仅 active=1；seal.py 的 `volume_id_of` 等需要读撤回行（前 canon）的调用方显式传 `active_only=False`（**注意：T7 修复波刚把 volume_id_of 改为不过滤 active——统一时不得回退该语义**）。
  - `fts.search` `limit` 参数默认从 20 提到 100（提示面截断收宽；调用方可显式收紧）。
  - snowflake dead 扫描传给 `deathbeat.is_dead` 的行改为仅取所需列（显式 `SELECT id, props`），消除隐式全列耦合。
  - rules.dependents docstring 注明提示面口径（默认仅活跃实体）。

- [ ] **Step 1: 写失败测试**

```python
# tests/storage/test_queries.py 追加
def test_edges_of_active_only(core_conn):
    _confirm(core_conn, [
        {"fact": "node", "id": "a", "types": ["Character"], "name": "a", "props": {}},
        {"fact": "node", "id": "b", "types": ["Concept"], "name": "b", "props": {}},
        {"fact": "edge", "id": "e1", "src": "a", "dst": "b", "kind": "REQUIRES",
         "props": {}},
    ])
    with db.transaction(core_conn):
        events.append_event(core_conn, "retraction",
                            {"target": "node", "target_id": "b"})
    projector.apply(core_conn)
    assert queries.edges_of(core_conn, "a") == []            # 默认仅活跃
    assert len(queries.edges_of(core_conn, "a", active_only=False)) == 1
    # get_node 同口径
    assert queries.get_node(core_conn, "b") is None
    assert queries.get_node(core_conn, "b", active_only=False) is not None
    # seal 的前 canon 读取不受统一影响（L 前修复不回退）
    from snowel_core.consistency import seal
    assert seal.volume_id_of(core_conn, "b") is None        # b 无 address → None（行可读）
```

- [ ] **Step 2: 跑测试确认失败**
- [ ] **Step 3: 最小实现**（默认参数收紧 + 显式豁免点排查：`grep -rn "edges_of\|get_node(" src/` 逐点判断语义——seal/deathbeat/retcon 等读"前 canon"处传 `active_only=False`）
- [ ] **Step 4: 跑测试通过**：`pytest tests/storage tests/consistency tests/flow tests/writeback -v`（全量守卫既有语义不漂）
- [ ] **Step 5: 提交**：`git commit -m "fix(storage): unify inactive-entity lookup semantics with active_only defaults (L17)"`

---

### Task 2: L18 + L15——补强包与 appeared 保真

**Files:**
- Modify: `src/snowel_core/writeback/extract.py`（L15）、`src/snowel_core/consistency/retcon.py`（空 retcon 守卫）
- Test: `tests/consistency/test_retcon.py`、`tests/consistency/test_wiring.py`、`tests/writeback/test_extract.py`、`tests/shell/test_mcp_server.py`（追加）

**Interfaces:**
- Produces:
  - L15：`extract_and_writeback` 在零事实（facts 空）时返回体仍携带 `appeared`（现状丢失）——返回 dict 增补/保真 `appeared` 键（以既有返回结构为准，测试锚定零事实章 appeared 不丢）。
  - 空 retcon 守卫：`propose_retcon` 当 `facts/renames/track_updates` 全空时 `ValueError("retcon 至少需要一项变更（facts/renames/track_updates）")`。
  - TC-CC-04 接线锚：`tests/consistency/test_wiring.py` 追加——confirm 一笔带 `valid_from_beat/valid_until_beat` 重叠边的提案 → `last_cascade()["violations"]` 含 `interval_overlap`；一笔 growth_curve=exponential → 含 `growth_guardrail`（三类检查经接线统一跑）。
  - MCP confirm retcon 分派协议锚：`tests/shell/test_mcp_server.py` 追加——writeback retcon action 建提案 → `snowel_proposal confirm` 走 confirm_retcon 分支返回 `{"seq": ..., "cascade": {...}}`（错路由时 core 抛错 → 测试红）。
  - 微裁决锚：`tests/consistency/test_rules_interval.py` 追加撤回边不触发 interval_overlap、顶层拍地址兜底两例（依 T5 实现的微裁决路径）。

- [ ] **Step 1: 写失败测试**（上述五项各一例，appeared 用例：FakeBackend 返回 facts 空 + appeared 非空 → 断言返回 dict 的 appeared 保真）
- [ ] **Step 2: 确认失败** → **Step 3: 最小实现** → **Step 4: 通过**：`pytest tests/consistency tests/writeback tests/shell -v`
- [ ] **Step 5: 提交**：`git commit -m "fix(writeback/consistency): preserve empty-facts appeared (L15), empty-retcon guard, wiring anchors (L18)"`

---

### Task 3: core 聊天代理引擎（llm/chat.py，W1）

**Files:**
- Create: `src/snowel_core/llm/chat.py`
- Modify: `src/snowel_core/api.py`（+chat 门面）
- Test: `tests/llm/test_chat.py`（新建目录，README 登记）

**Interfaces:**
- Consumes: `GenerationBackend.generate(prompt, model, system)`；api 门面（ai_generate/search/find_nodes/get_node/state_at/register_foreshadow/expand_chapter/expand_volume）；`parse_llm_json` 围栏容忍。
- Produces:
  - `chat.run_stream(api, message: str, history: list[dict] | None = None, backend=None, max_turns: int = 8) -> Iterator[dict]`——**同步生成器**逐事件 yield：`{"type": "tool_call", "tool": ..., "args": ...}`、`{"type": "tool_result", "tool": ..., "ok": bool, "summary": str}`、`{"type": "reply", "text": str}`、末事件 `{"type": "done", "proposal_ids": [...]}`。流程：系统提示（含 flow_state 摘要与工具清单 JSON schema 描述）+ 历史 + 用户消息 → LLM → 解析 `{"tool"/"reply"}`；tool 则执行 → yield 事件 + 观察（结果 JSON 串截断 4000 字符）回注 → 下一轮；reply 则 yield 后接 done 收束。轮次耗尽 → yield 一条 reply 事件说明收束 + done。非法 JSON → 以错误文本为观察回注重试（计一轮）。
  - `chat.run(api, message, history=None, backend=None, max_turns=8) -> dict`——聚合门面：`{"events": [除 done 外全部事件], "proposal_ids": [...]}`（= `list(run_stream())` 加工；W6 非流式兼容口）。
  - 工具注册表 `chat.TOOLS: dict[str, callable(api, args) -> dict]`：`generate` → `{"proposal_id": api.ai_generate(artifact_type, locate, extra)}`；`expand_chapter` → `{"proposal_ids": api.expand_chapter(...)}`（backend 透传）；`expand_volume` 同；`query` → args 含 `kind`（search/find/state_at/node）分派对应只读门面；`register_foreshadow` → `{"proposal_id": api.register_foreshadow(...)}`。**注册表键即白名单——confirm/reject/seal 等确认类永不可达**。
  - `api.chat(message, history=None, backend=None) -> dict` 聚合门面 + `api.chat_stream(message, history=None, backend=None) -> Iterator[dict]` 流式门面（backend 缺省走 `llm.ports.get_backend`）。

- [ ] **Step 1: 写失败测试**

```python
# tests/llm/test_chat.py
import json
from snowel_core.llm import chat


def _seed(api):
    api.proposals.create("t", {"facts": [
        {"fact": "node", "id": "m1", "types": ["Mechanism"],
         "name": "积分兑换", "props": {"mechanism": {"level": 3}}}]})
    # 直接确认种子（绕过级联面，聚焦代理协议）


def test_chat_tool_loop_and_reply(api):
    _seed(api)
    fake = FakeBackend([
        json.dumps({"tool": "generate", "args": {
            "artifact_type": "premise",
            "extra": {"idea": "无限流轮回游戏"}}}, ensure_ascii=False),
        json.dumps({"reply": "已为你生成前提提案，请在右侧面板查看确认。"},
                   ensure_ascii=False),
    ])
    out = api.chat("帮我想个无限流前提", backend=fake)
    kinds = [e["type"] for e in out["events"]]
    assert kinds == ["tool_call", "tool_result", "reply"]
    assert out["events"][0]["tool"] == "generate"
    assert out["events"][1]["ok"] is True
    assert len(out["proposal_ids"]) == 1                  # 提案入队，未确认
    assert api.proposals.get(out["proposal_ids"][0])["status"] == "pending"
    # 流式版：逐事件产出，末事件 done 携带 proposal_ids（W6）
    events = list(api.chat_stream("再想一个", backend=FakeBackend([
        json.dumps({"reply": "好的。"}, ensure_ascii=False)])))
    assert events[-1]["type"] == "done"
    assert events[-1]["proposal_ids"] == []


def test_chat_query_tool_and_turn_cap(api):
    _seed(api)
    fake = FakeBackend([
        json.dumps({"tool": "query", "args": {
            "kind": "find", "types": ["Mechanism"]}}, ensure_ascii=False),
        "这不是合法JSON",                                   # 非法 → 错误观察回注
        json.dumps({"tool": "query", "args": {
            "kind": "find", "types": ["Mechanism"]}}, ensure_ascii=False),
    ] + ['{"tool": "query", "args": {"kind": "find"}}'] * 8)  # 耗尽轮次
    out = api.chat("查一下机制", backend=fake, max_turns=8)
    assert out["events"][-1]["type"] == "reply"            # 轮次耗尽强制收束
    assert all(e["type"] != "tool_call" or e["tool"] != "confirm"
               for e in out["events"])                     # 确认类永不在白名单
```

- [ ] **Step 2: 确认失败** → **Step 3: 最小实现**（系统提示模板 + 注册表 + 循环；工具执行 try/except → `{"ok": False, "summary": str(e)}` 观察回注）
- [ ] **Step 4: 通过**：`pytest tests/llm -v`
- [ ] **Step 5: 提交**：`git commit -m "feat(llm): chat agent engine with JSON tool-call loop and confirm-excluded whitelist (7.1)"`

---

### Task 4: FastAPI 骨架——app 工厂、项目绑定、租约会话、静态 serve（W2/W5）

**Files:**
- Create: `shell/src/snowel/web_server.py`
- Modify: `shell/src/snowel/cli.py`（+`web` 子命令）、`shell/pyproject.toml`（+fastapi、uvicorn、httpx）
- Test: `tests/shell/test_web_server.py`（新建）

**Interfaces:**
- Produces:
  - `web_server.create_app(project_root: str) -> FastAPI`：app 工厂，启动时 `SnowelAPI.open(project_root)` 挂 `app.state.api`；`acquire_lease("web:<pid>")` 成功 → 写会话，失败 → 只读（`app.state.readonly=True`）；shutdown 时 release + close。
  - 端点：`GET /api/session` → `{"project": name, "readonly": bool, "holder": str|None, "flow": flow_state}`；`GET /api/health` → `{"ok": true}`；静态：`web/dist` 存在则挂 `/`（SPA fallback 到 index.html），缺失则跳过（无 node 环境测试不破）。
  - 写端点统一守卫：readonly 会话收到写请求 → 409 `{"detail": "只读会话：写租约由 {holder} 持有"}`。
  - CLI：`snowel web --project PATH [--port 8642] [--host 127.0.0.1]` → uvicorn.run(create_app(...))；非项目目录启动 → 明确报错退出（TC-SH-06 绑定语义）。
- 测试模式：`httpx.AsyncClient(transport=ASGITransport(app=create_app(tmp)), ...)`) + `pytest.anyio`/asyncio 标记（沿 pytest-asyncio 或 anyio 既有可用项；若两皆无，加 `pytest-asyncio` 依赖并 `asyncio_mode=auto`）。

- [ ] **Step 1: 写失败测试**

```python
# tests/shell/test_web_server.py
import pytest
from httpx import ASGITransport, AsyncClient
from snowel_core.api import SnowelAPI
from snowel.web_server import create_app


@pytest.fixture
def project(tmp_path):
    api = SnowelAPI.init_project(tmp_path)
    api.close()
    return tmp_path


async def test_session_and_binding(project):
    app = create_app(str(project))
    async with AsyncClient(transport=ASGITransport(app=app),
                           base_url="http://t") as c:
        r = await c.get("/api/session")
        assert r.status_code == 200
        body = r.json()
        assert body["readonly"] is False and "flow" in body
        assert (await c.get("/api/health")).json() == {"ok": True}


async def test_readonly_session_blocks_writes(project, monkeypatch):
    api = SnowelAPI.open(project)          # 抢占租约：模拟他端持锁（TC-SH-04）
    api.acquire_lease("mcp:test-holder")
    app = create_app(str(project))
    async with AsyncClient(transport=ASGITransport(app=app),
                           base_url="http://t") as c:
        sess = (await c.get("/api/session")).json()
        assert sess["readonly"] is True and sess["holder"] == "mcp:test-holder"
        r = await c.post("/api/proposal/xxx/confirm")
        assert r.status_code == 409 and "只读" in r.json()["detail"]
    api.release_lease("mcp:test-holder")
    api.close()
```

- [ ] **Step 2: 确认失败** → **Step 3: 最小实现**（lifespan 管理 api 生命周期 + 租约；写守卫依赖注入或路由装饰器，保持壳零领域逻辑——守卫只查 `app.state.readonly` 布尔）
- [ ] **Step 4: 通过**：`pytest tests/shell -v`
- [ ] **Step 5: 提交**：`git commit -m "feat(shell): FastAPI web skeleton with project binding, lease session and static serve (7.1/TC-SH-04/06)"`

---

### Task 5: 只读 API 面——流程树/提案/检索/审计/对账状态

**Files:**
- Modify: `shell/src/snowel/web_server.py`
- Test: `tests/shell/test_web_server.py`（追加）

**Interfaces:**
- Consumes: api 门面只读面（flow_state/proposals.list/get/search/state_at/get_node/audit_recent/reconcile_prose/list_auto/deviation/sealed_volumes/graph_stats）。
- Produces（全部 GET，一比一转发 + 404 统一）：
  - `GET /api/flow` → flow_state；`GET /api/proposals?status=` → list；`GET /api/proposals/{pid}` → get + `{"payload": parsed}`（payload 解析为对象供面板直接用）；`GET /api/proposals/{pid}/cascade_preview` → `api.cascade_check(payload.facts)`（预演，不入队）。
  - `GET /api/search?q=&kind=` → search；`GET /api/nodes/{id}` → get_node + edges_of；`GET /api/state?at=` → state_at。
  - `GET /api/audit` → audit_recent；`GET /api/writeback/auto` → list_auto；`GET /api/writeback/deviation/{chapter}` → deviation；`GET /api/reconcile` → reconcile_prose()（中栏对账状态：返回 changed/missing 清单）；`GET /api/sealed` → sealed_volumes。

- [ ] **Step 1: 写失败测试**（种子项目建提案/节点后逐端点断言 200 + 语义字段；pid 不存在 → 404；readonly 会话 GET 全部照常——只读降级读不限，TC-SH-04 断言）。代表性用例：

```python
# tests/shell/test_web_server.py 追加
async def test_proposal_read_surface(project):
    api = SnowelAPI.open(project)
    pid = api.proposals.create("t", {"facts": [
        {"fact": "node", "id": "n1", "types": ["Concept"], "name": "x",
         "props": {}}]})
    api.close()
    app = create_app(str(project))
    async with AsyncClient(transport=ASGITransport(app=app),
                           base_url="http://t") as c:
        lst = (await c.get("/api/proposals", params={"status": "pending"}))
        assert lst.status_code == 200 and any(
            p["id"] == pid for p in lst.json())
        one = (await c.get(f"/api/proposals/{pid}")).json()
        assert one["kind"] == "t" and one["payload"]["facts"][0]["id"] == "n1"
        assert (await c.get("/api/proposals/nope")).status_code == 404
        prev = (await c.get(f"/api/proposals/{pid}/cascade_preview")).json()
        assert "violations" in prev            # 预演返回，队列长度不变
```
- [ ] **Step 2: 确认失败** → **Step 3: 最小实现**（路由注册；`/api/proposals/{pid}` 顺手带 `kind` 字段供前端分派确认入口——retcon 提案确认按钮路由到 confirm_retcon 端点，与 MCP 同逻辑但壳侧零分派：前端读 kind）
- [ ] **Step 4: 通过**：`pytest tests/shell -v`
- [ ] **Step 5: 提交**：`git commit -m "feat(shell): read-only web API surface (flow/proposals/search/audit/reconcile)"`

---

### Task 6: 写 API 面——确认/否决/改写/生成/封卷/retcon/伏笔/回写

**Files:**
- Modify: `shell/src/snowel/web_server.py`
- Test: `tests/shell/test_web_server.py`（追加）

**Interfaces:**
- Produces（POST，全部过 Task 4 的 readonly 守卫）：
  - `POST /api/proposals/{pid}/confirm` → `{"seq", "cascade": api.last_cascade()}`（retcon kind 由前端经 `GET /api/proposals/{pid}.kind` 分派到此或下一端点——**壳零分派**：本端点调 `api.confirm`，retcon 提案会收到 core 的 ValueError，前端据 kind 预路由）；`POST /api/proposals/{pid}/confirm_retcon` → confirm_retcon + cascade 同形态；`POST /api/proposals/{pid}/reject` → `{"ok": true}`；`POST /api/proposals/{pid}/rewrite` body `{"instruction": str}` → 新 pid（rewrite reason 语义重载 UI 面：指令作为一等输入字段呈现）。
  - `POST /api/generate` body `{"artifact_type", "locate"?, "extra"?}` → `{"proposal_id"}`（后端从 config 取默认 backend：`llm.ports.get_backend`；测试注入——app.state.llm_backend 可覆盖）；`POST /api/expand/chapter` / `POST /api/expand/volume` 同理。
  - `POST /api/seal` body `{"volume_id"}`；`POST /api/retcon` body `{facts?, renames?, track_updates?, reason}` → `{"proposal_id", "impact"}`；`POST /api/foreshadow` body `{name, planted_at, origin?, payoff_beat?, note?}`。
  - `POST /api/writeback/extract` body `{"chapter_id"}` → 完整 extract 返回（含 cascade 键）；`POST /api/writeback/reject_auto` body `{"entries": [[target, id], ...]}`；`POST /api/writeback/reregister` body `{"proposal_id"}`。
  - `POST /api/revision` body `{node_id, new_address, reason}` → propose_revision。
- TC-SH-03 锚：Web 端 confirm 后 `api.proposals.get(pid)["status"] == "confirmed"`（与 MCP 共库一致性——测试里直接开 SnowelAPI 查同一项目库验证三端视图一致）。

- [ ] **Step 1: 写失败测试**（FakeBackend 注入 app.state；种子提案 → confirm 返回 cascade 键；retcon 提案 confirm 走 confirm_retcon 端点返回 impact；seal 重复 → 400 带"已封"；readonly → 409）
- [ ] **Step 2: 确认失败** → **Step 3: 最小实现**（ValueError → 400 `{"detail": str(e)}` 统一映射；SealedVolumeError 同）
- [ ] **Step 4: 通过**：`pytest tests/shell -v`
- [ ] **Step 5: 提交**：`git commit -m "feat(shell): write web API surface with cascade responses and error mapping (TC-SH-03)"`

---

### Task 7: 统计四件查询进 core + 端点（W4）

**Files:**
- Modify: `src/snowel_core/storage/queries.py`（+stats_pov/stats_foreshadow/stats_relations/stats_pacing）、`src/snowel_core/api.py`（+四门面）、`shell/src/snowel/web_server.py`（+四端点）
- Test: `tests/storage/test_queries.py`（追加）、`tests/shell/test_web_server.py`（追加）

**Interfaces:**
- Produces（全部纯 SQL/JSON 聚合，只读，零 LLM）：
  - `queries.stats_pov(conn) -> {"by_volume": [{volume_id, volume_name, counts: {pov_name: n}}]}`：Chapter/Scene/MicroBeat 节点 props.pov（或 props.address.pov）字段频次，按卷分组；无 pov 字段不计入。
  - `queries.stats_foreshadow(conn) -> {"items": [{id, name, planted_at, payoff_beat, status}]}`：Foreshadow 节点全集，status = "planted"（payoff_beat 空）| "paid"（非空且目标拍存在且 active）| "stale"（目标拍不可达）。
  - `queries.stats_relations(conn) -> {"nodes": [Character 节点], "edges": [两端均为活跃 Character 的边]}`：角色关系图数据。
  - `queries.stats_pacing(conn) -> {"chapters": [{chapter_id, name, beats: n, paragraphs: n}]}`：拍数查节点表、段落数查 mirror FTS 表（chapter_id 分组计数）。
  - 端点：`GET /api/stats/{pov|foreshadow|relations|pacing}` 一比一转发。

- [ ] **Step 1: 写失败测试**（core 侧四函数语义断言——种子含双 POV 章节、已回收/未回收伏笔、角色边、拍/段落计数；shell 侧端点转发断言）
- [ ] **Step 2: 确认失败** → **Step 3: 最小实现** → **Step 4: 通过**：`pytest tests/storage tests/shell -v`
- [ ] **Step 5: 提交**：`git commit -m "feat(storage): pov/foreshadow/relations/pacing stats queries with web endpoints (7.1 visualization)"`

---

### Task 8: 聊天端点（W6 SSE 流式 + 非流式聚合）

**Files:**
- Modify: `shell/src/snowel/web_server.py`、`src/snowel_core/api.py`（chat_stream 门面已建于 T3）
- Test: `tests/shell/test_web_server.py`（追加）

**Interfaces:**
- Produces:
  - `POST /api/chat/stream` body `{"message": str, "history": [...] | None}` → `StreamingResponse(media_type="text/event-stream")`：生成器经 `starlette.concurrency.iterate_in_threadpool` 逐事件拉取 `api.chat_stream(...)`，每事件编码 `data: {json}\n\n` 一行；done 事件后流自然结束。backend 注入同 T6（app.state.llm_backend 透传给 chat_stream）。空 message → 400（进流前校验）。
  - `POST /api/chat` 非流式聚合版保留（一比一 `api.chat`，测试与简单客户端用）。
- 测试锚：FakeBackend 两轮（tool + reply）→ httpx `client.stream("POST", ...)` 消费，断言响应行序列恰为 4 条 SSE data 行（tool_call/tool_result/reply/done），done 行含 proposal_ids；非流式端点返回聚合 events。

- [ ] **Step 1: 写失败测试**（含流式行格式断言与聚合版对照）
- [ ] **Step 2: 确认失败** → **Step 3: 最小实现**（SSE 编码辅助 `_sse(event) -> str`；流式生成器内 try/except 把 core 异常转为 `data: {"type":"error","text":...}` 行后收束——不让连接吊死）
- [ ] **Step 4: 通过**：`pytest tests/shell -v`
- [ ] **Step 5: 提交**：`git commit -m "feat(shell): SSE chat stream endpoint with aggregate fallback (7.1)"`

---

### Task 9: React 工程骨架——三栏布局壳 + API client + 只读横幅（W2/W3）

**Files:**
- Create: `web/`（`package.json`、`vite.config.ts`、`tsconfig.json`、`index.html`、`src/main.tsx`、`src/App.tsx`、`src/api.ts`、`src/types.ts`、`src/components/*.tsx`、`src/App.test.tsx`）
- Test: `web/src/App.test.tsx`（vitest + testing-library）

**Interfaces:**
- Produces:
  - Vite + React 18 + TS 工程（无路由库——单页状态切换，YAGNI）；`npm run dev`（vite proxy `/api` → `127.0.0.1:8642`）与 `npm run build`（产物 `web/dist`）。
  - `src/api.ts`：`api.get/post` 薄封装（fetch + JSON + 错误 detail 抛出）；类型面 `src/types.ts`（Session/FlowState/Proposal/Violation/ChatEvent 等与后端响应一比一）。
  - `App.tsx` 三栏布局壳：左 `FlowTree`（T10 实现）/ 中 `ProseEditor`（T11）/ 右 `Workspace`（T10）+ 常驻 `ChatSidebar`（T12）+ 顶部 `SessionBanner`（readonly=true 时黄条"只读模式：写租约由 {holder} 持有"）。
  - 组件数据获取模式：`useApi(path)` 简易 hook（loading/error 态）。
- 测试锚：App 壳渲染三栏骨架（mock api 后断言三容器存在）；SessionBanner 对 readonly=true 显示提示文案。

- [ ] **Step 1: 写失败测试**（`web/src/App.test.tsx`：vi.mock('./api') 后 render(<App/>)，断言 `data-testid="col-flow/workspace/prose/chat"` 四容器与横幅行为）
- [ ] **Step 2: 确认失败**（`npx vitest run`）→ **Step 3: 最小实现**（`npm create vite@latest` 起步 + 手工裁剪；node ≥18 前提写入 web/README.md）
- [ ] **Step 4: 通过**（`npx vitest run` + `npm run build` 产出 dist）
- [ ] **Step 5: 提交**：`git commit -m "feat(web): React+Vite+TS scaffold with three-column shell, api client, readonly banner"`

---

### Task 10: 左栏流程树 + 右栏工作区（表单/提案面板/级联呈现）

**Files:**
- Create: `web/src/components/FlowTree.tsx`、`ProposalList.tsx`、`ProposalPanel.tsx`（diff 视图 + 确认/否决/改写 + cascade 结果 + reconcile 提示）、`GenerateForm.tsx`（各层表单）
- Test: `web/src/components/*.test.tsx`

**Interfaces:**
- Consumes: `GET /api/flow`、`GET/POST /api/proposals*`、`POST /api/generate`、`GET /api/proposals/{pid}/cascade_preview`、`GET /api/reconcile`（W7：prose 提案确认前若 reconcile changed 非空 → 面板黄条列出外部改动，确认按钮二次确认文案）。
- Produces:
  - `FlowTree`：LAYERS 七层进度（done/todo）+ current_layer 高亮 + 卷→章两级树（flow.volumes）。
  - `ProposalList`：按 status 过滤（pending/stale 优先展示）；点击选中进 `ProposalPanel`。
  - `ProposalPanel`：payload facts 的 diff 视图（新增/变更节点-键-旧值→新值表格式呈现）；kind=="retcon" 时确认按钮调 confirm_retcon 端点并展示 impact（violations 全量——**L19 多键天然展开**）；确认后展示 cascade.violations（level 分色 major/minor）；stale 提案展示 stale_hint；改写框（instruction 一等输入）。
  - `GenerateForm`：artifact_type 选择（premise/synopsis/summary/beat_sheet/characters/scenes/prose）+ locate/extra 附加字段（JSON 文本域）→ POST generate → 跳转新提案面板。
- 测试锚：FlowTree 渲染层状态与卷章树（mock /api/flow）；ProposalPanel 对含 contradiction violation 的 confirm 响应渲染 major 行；retcon kind 按钮走 confirm_retcon；prose 提案 + reconcile changed 非空 → 显示外部改动警告。

- [ ] **Step 1: 写失败测试**（四组件各一例，vi.mock api）→ **Step 2: 确认失败** → **Step 3: 最小实现** → **Step 4: 通过**（vitest + build）
- [ ] **Step 5: 提交**：`git commit -m "feat(web): flow tree, proposal panel with diff/cascade/reconcile warning, generate form (7.1/TC-SH-08)"`

---

### Task 11: 中栏正文编辑页

**Files:**
- Create: `web/src/components/ProseEditor.tsx`（章节列表 + 编辑区 + 对账状态 + 抽取入口 + deviation 面板）
- Modify: `shell/src/snowel/web_server.py`（+`POST /api/prose` 端点：一比一 `api.proposals.create("prose", {chapter_id, content})` → `{"proposal_id"}`）
- Test: `web/src/components/ProseEditor.test.tsx`、`tests/shell/test_web_server.py`（追加 prose 端点锚）

**Interfaces:**
- Consumes: `GET /api/flow`（卷章树）、`GET /api/reconcile`（changed/missing）、`GET /api/writeback/deviation/{chapter}`、`POST /api/writeback/extract`、`POST /api/writeback/reregister`、prose 提案确认面（Task 10 的 ProposalPanel 承担，编辑页提供跳转）。
- Produces:
  - 章节列表（flow.volumes[].chapters + reconcile missing 提示"镜像中存在但库内无章"）；选中章 → 段落编辑（textarea 按 mirror 段落切分；保存 = 写本地文件经后端？**裁决：v1 编辑保存路径 = 生成 prose 提案走确认**——编辑区产出 prose 草稿提案（api.proposals.create 经新端点 `POST /api/prose` body `{chapter_id, content}`，core 侧复用既有 prose 提案 kind），确认后 reregister 落盘；外部编辑（编辑器外改文件）由 reconcile 面板展示并引导 reregister）。
  - `POST /api/prose` 端点（T11 顺带加壳：一比一 `api.proposals.create("prose", {chapter_id, content})`）。
  - 抽取入口：选中章 + `POST /api/writeback/extract` → 结果面板（appeared/warnings/cascade/偏差 deviation 链接）。
- 测试锚：章节渲染 + missing 提示；编辑保存创建 pending prose 提案（mock）；抽取结果面板字段。

- [ ] **Step 1: 写失败测试** → **Step 2: 确认失败** → **Step 3: 最小实现** → **Step 4: 通过**
- [ ] **Step 5: 提交**：`git commit -m "feat(web): prose editor with reconcile status, proposal-based save, extract panel (7.1)"`

---

### Task 12: 聊天侧栏前端（SSE 消费 + 渐显）

**Files:**
- Create: `web/src/components/ChatSidebar.tsx`、`web/src/sse.ts`（fetch 流式 SSE 行解析 util，~30 行）
- Test: `web/src/components/ChatSidebar.test.tsx`

**Interfaces:**
- Consumes: `POST /api/chat/stream`（T8，SSE）。
- Produces:
  - `sse.ts`：`streamSSE(url, body, onEvent, signal)`——fetch + `response.body.getReader()` + TextDecoder 按 `\n\n` 切事件、剥 `data: ` 前缀 JSON.parse；AbortController 支持中断。
  - `ChatSidebar`：消息历史（本地态 + 传入 history）；发送 → **事件到达即渲染**（tool_call 卡片"调用 generate…"、tool_result 成败、reply 气泡带渐显打字机动画——纯前端 CSS/JS 效果，W6）；done 事件 proposal_ids 非空 → 尾部提示"已入队 N 个提案" + 点击跳转 ProposalList；error 事件/网络失败 → 红条；发送中可中断（断开按钮 → abort）。
- 测试锚：mock `sse.ts`（vi.mock）按序喂四事件 → 断言三类渲染块、跳转链接与中断按钮存在；reply 渐显不断言动画帧（断言最终文本渲染）。

- [ ] **Step 1: 写失败测试** → **Step 2: 确认失败** → **Step 3: 最小实现** → **Step 4: 通过**
- [ ] **Step 5: 提交**：`git commit -m "feat(web): chat sidebar consuming SSE stream with typing effect and proposal links (7.1)"`

---

### Task 13: 可视化四件（W4 轻量 SVG）

**Files:**
- Create: `web/src/components/Viz*.tsx`（PovChart/ForeshadowMap/RelationsGraph/PacingBars 四组件 + 入口标签页）
- Test: `web/src/components/Viz.test.tsx`

**Interfaces:**
- Consumes: `GET /api/stats/*`（T7）。
- Produces: PovChart 堆叠条形（按卷）；ForeshadowMap 时间线（planted_at → payoff_beat 区间条 + status 色）；RelationsGraph 邻接矩阵或圆环（节点+边，手写 SVG）；PacingBars 每章拍数/段落数双条形。入口：右栏工作区顶部"可视化"标签页（纯统计区，与提案面板互斥切换）。
- 测试锚：每组件 mock 数据断言 SVG 元素数量/文本（如 ForeshadowMap 渲染 status=planted 的条数）。

- [ ] **Step 1: 写失败测试** → **Step 2: 确认失败** → **Step 3: 最小实现** → **Step 4: 通过**（vitest + build）
- [ ] **Step 5: 提交**：`git commit -m "feat(web): pov/foreshadow/relations/pacing visualizations (7.1)"`

---

### Task 14: 收尾——TC-SH-08 API 级端到端 + README 登记 + 全量回归

**Files:**
- Modify: `tests/README.md`（§1 加 `llm/`（test_chat）行 + shell 行补 test_web_server；`web/` 前端测试说明行）
- Test: `tests/shell/test_web_server.py`（追加端到端）、全量

**Interfaces:**
- Produces:
  - TC-SH-08 API 级端到端：一个测试内串起——init 项目 → 种子一层 → `GET /api/flow`（层进度+卷章树）→ `GET /api/proposals`（面板数据源）→ `GET /api/reconcile`（中栏识别镜像章节）→ `POST /api/chat`（FakeBackend：发起提案）→ 断言提案 pending 且**响应不含任何已确认动作**（确认只落结构化面板）→ `POST /api/proposals/{pid}/confirm`（结构化确认路径）。四断言面（流程树/工作区/编辑页/聊天约束）各至少一句。
  - 全量：`pytest`（后端全绿）+ `npx vitest run` + `npm run build`（前端全绿产物在）。

- [ ] **Step 1: 补端到端测试与 README 行**（沿既有表格风格；覆盖 TC-SH-03/04/06/08）
- [ ] **Step 2: 全量回归**：后端预期 ≥194 + 本计划新增全绿；前端 vitest 全绿；输出干净
- [ ] **Step 3: 提交**：`git commit -m "docs: register web/llm test surfaces with TC-SH reverse index; e2e anchor"`

---

## 覆盖矩阵（用例 ↔ 任务）

| 黑盒用例 | 任务 | 备注 |
|---|---|---|
| TC-SH-08 三栏界面（流程树/工作区/编辑页/聊天约束） | 9+10+11+12+14 | API 级端到端 + 组件锚；浏览器 E2E 豁免（W3） |
| TC-SH-03 Web 端确认三端一致 | 6+14 | confirm 端点 + 共库断言 |
| TC-SH-04 租约降级只读 | 4 | 409 守卫 + 横幅（9） |
| TC-SH-06 进程绑定项目 | 4 | CLI 启动指定工作区 |
| §7.1 聊天完整工具代理（确认落结构化面板红线） | 3+8+12 | 工具白名单排除确认类 |
| §7.1 只读可视化四件 | 7+13 | 纯统计零 AI |
| L15/L17/L18 | 2/1/2 | 挂账清偿 |
| L19 | — | 关闭（W 裁决：violations 全量呈现 + 响应内嵌 cascade） |

**豁免登记**：token 级 LLM 流（W6：LLM 生成内部整段，reply 打字机为前端渐显动画；真 token 流需 backend `stream()` 口 + 输出协议重设计，后续版本）；浏览器级 E2E（W3，验收人工走查）；`rewrite_query` 检索改写（E3 v1 未启用沿用）；扩展包 E4（后续版本）；MCP 面新增 Web 相关工具（无——Web 不改 MCP）。

## 执行注意

1. worktree 执行先 `pip install -e . -e ./shell` + `cd web && npm install`（node ≥18；无 node 环境可跑 Task 1–8 后端全量，Task 9 起需 node）。
2. Task 4 的异步测试基建：若 pytest-asyncio 未在依赖，shell/pyproject.toml 加 `pytest-asyncio` 并确认 `asyncio_mode` 配置——写在 Task 4 内一次搞定。
3. Task 9 的 vite 工程用 `npm create vite@latest web -- --template react-ts` 起步后裁剪（删除默认演示页/CSS）；依赖仅 react/react-dom + vitest/@testing-library/react + @types/*，不加 UI 组件库与路由库。
4. Task 10/11/12/13 的组件测试全部 vi.mock('./api')（不真起后端）；端到端只在 Task 14 后端侧做。
5. 双库坑（conftest api fixture 在 tmp_path/api、core_conn 在 tmp_path 根）与 props 覆写时序（分析需 old 值必在事务前读）继续有效。
6. SSE 调试：`curl -N -X POST localhost:8642/api/chat/stream -H "Content-Type: application/json" -d '{"message":"..."}'` 逐行看事件；测试断言用 httpx `client.stream`。
7. 计划缺陷执行期发现：控制器 Ruling 落 ledger 后继续，不停摆。
