# v1.0.0 范围扩容 Step 4：壳端暴露（Web 灵感/拍操作 + MCP advanced）

> 日期：2026-08-28。来源：范围增补 `requirements-addendum.md` §4 / §8（Step 4 行）——8 step 链第 4 步；承接跨计划挂账 L25 壳端暴露部分（Step 1 已清 core 部分）。
> 性质：壳层接线计划——core 门面全备（save_inspiration/inspirations/merge_beats/delete_beat/ai_generate derive_from 均已落地并有测试锚），本步把它们接进 Web 与 MCP；唯一 core 增量是一个只读查询门面（R1，架构铁律所迫）。
> 上游素材：`plans/2026-08-28-infinite-flow/ledger.md`（preflight 挂账）；现状调查结论已内化进 §4–§6（web 三栏布局、路由范式、mock 模式、MCP 目录机制）。

## 1. 背景与范围

| 项 | 内容 | 黑盒锚 |
|---|---|---|
| Web 灵感面板 | 保存原话（POST）/ 列表 / 从灵感发起 derive 生成（GenerateForm 灵感多选 → `derive_from` 透传） | TC-SH-09 |
| Web 拍操作 | 正文编辑页拍列表（新只读端点）+ 合并到相邻拍（ConfirmDialog + 伏笔迁移预览）/ 删除空拍（被引用时 400 detail 拒绝原因红条呈现） | TC-SH-10 |
| MCP advanced | `snowel_advanced` 新增 `inspiration_save / inspiration_list / beat_merge / beat_delete` 四 op（写操作前置 `require_write`）；六工具签名不变 | TC-SH-11 |
| 扩展包 | 不做 Web 面、不做 MCP 面（裁决 6）——`extension_packs` 目录占位更新为"仅 CLI 管理" | — |
| 文档落锚 | testcases.md §9 壳域 +3 例（TC-SH-09/10/11，76→79 例）+ §11.2 范围 01–08→01–11 | — |

不在范围：扩展包任何壳面（裁决 6）；`valid_until_beat` 边级迁移明细预览（addendum 字面只要求伏笔迁移预览，R2）；MCP streamable HTTP（Step 5）；rewrite_query（Step 5）；Web 手册扩展包/新面板章节（Step 6）。

## 2. Global Constraints

- 领域逻辑只在 snowel-core：web_server/mcp_server 零 SQL 零领域逻辑，一比一转发门面（design §10）。
- MCP 六工具不变式（TC-SH-01 `test_exactly_six_tools`）不动；新能力走 `snowel_advanced` op（"接通后工具签名不变"既定约定）。
- 前后端契约双侧手写：Python 侧路由契约测试（httpx ASGITransport 范式）+ vitest 组件测试（vi.mock api 层、断言调用参数与渲染），两侧各自对齐响应形状（types.ts 一比一注释惯例）。
- 写操作双保险：后端 `Depends(_require_write)`（409 只读文案）+ 前端 `readonly` 禁用；错误经 api.ts Error(detail) 红条呈现（ProseEditor doSave 范式）。
- 触 db 端点一律 `async def`（跨线程 sqlite 崩先例，web_server.py L183 注释）。
- 每任务 TDD、conventional commits、测试落就近文件；testcases.md 落锚与 tests/README 反向索引 grep 实证。
- 全量基线：dev-1.0.0 @ 9fb10a1，后端 309 + 前端 vitest 74 + build 绿。

## 3. Preflight 挂账裁决（同版本已归档 ledger 全量双查）

| 挂账 | 内容 | 裁决 | 去向 |
|---|---|---|---|
| **EX-③** | discovery 警告池归因漂移 + per-instance 注册表决策 | **不携带**——两次计划预告的触发条件（长驻进程触碰 `api.list_extensions/extensions_status`）经本步设计核实不成立：Web/MCP 不加扩展管理面（裁决 6 定死），`extension_warnings` 消费面仍仅 CLI 单命令进程。挂账条件精确化为"**任何壳扩展包面落地之日**"（替代原"Step 4 必查"表述） | 挂账保留，条件已更新 |
| **L25** | 壳端暴露部分（Web 灵感/拍操作、MCP advanced） | **携带——本步主体，完成后 L25 全关** | Task 1–4 |
| TC-SH-09/10/11 | addendum §4 建议用例 | **携带**——转正落锚 testcases.md | Task 5 |
| extension_packs 占位 | mcp_server.py ADVANCED_CATALOG 中 `{"wired": False, "planned_in": "E4"}` | 携带——按裁决 6 更新文案为"不做 Web/MCP 面，仅 CLI（snowel ext）" | Task 1 |
| L16 / L26 / L27 | 发布债 / 记录性 / 卫生项 | 不携带 | Step 8 / — / 专门时机 |

任务间共享文件冲突：T1 独占 mcp_server.py + test_mcp_server.py；T2 独占 web_server.py + api.py（只读门面一处）+ test_web_server.py；T3/T4 共享 App.tsx/types.ts/api.ts（串行，T4 基于 T3 提交）；T5 独占文档。无并行冲突。

## 4. 计划级设计裁决（预登记 Ruling，随计划批准生效）

| # | 裁决 | 理由 | 若错的成本 |
|---|---|---|---|
| R1 | 拍列表数据面走 **core 新只读门面** `api.beats_of(chapter_id) -> list[dict]`（仿 inspirations() 内联 SQL 手法，按 types 含 MicroBeat + address.chapter 过滤，story_order 稳定序；字段最小集 id/显示名/story_order，实现者按 queries.py 现状定），Web 端点 `GET /api/chapters/{chapter_id}/beats` 薄转发 | 壳零 SQL 是架构铁律（design §10）；拍列表无任何现有端点可复用 | 字段增删改一处 SQL + 契约断言 |
| R2 | 伏笔迁移预览 = 前端过滤既有 `GET /api/stats/foreshadow`（`planted_at === source` 的清单随 ConfirmDialog 展示"将迁移 N 个伏笔：…"），**零 core 改动**；`valid_until_beat` 边级明细不做预览 | addendum §4 字面只要求"含伏笔迁移预览"；stats/foreshadow 已返回 planted_at 全集 | 若要边明细，core 补一个查询门面同 R1 模式 |
| R3 | MCP **不加新工具**：ADVANCED_CATALOG 登记四项（`inspiration_save/inspiration_list` → snowel_advanced op 分派 `api.save_inspiration/inspirations`，`beat_merge/beat_delete` → `api.merge_beats/delete_beat`；写 op 前置 `ctx.require_write()`）；`extension_packs` 占位文案改"不做 Web/MCP 面（裁决 6），仅 CLI `snowel ext` 管理" | 六工具不变式（TC-SH-01）与 mcp_server 头注释"接通后工具签名不变"既定；CLI 独占扩展管理（裁决 6） | 拆新工具则动 test_exactly_six_tools 与 TC-SH-01 契约，无收益 |
| R4 | 灵感面板挂右栏提案 tab（workspaceTab='proposals'，`GenerateForm` 与 `ProposalList` 之间），derive 联动做在 GenerateForm 内（灵感多选 chip → body.derive_from），**不新开 tab** | derive 数据流（列表→表单）在同一 tab 内闭环，改动面最小；VizPanel tab 机改是 UI 扩张 | 面板拥挤则后移独立 tab，组件不用重写 |
| R5 | 拍操作 UI 落 `ProseEditor` 章编辑区（拍侧栏或编辑区头，按 UI 空间实现者裁量）；合并走 `ConfirmDialog` 二次确认（危险操作先例 doSeal）；删除被引用的后端 400 detail 直接红条呈现；成功后 `onMutated` 刷新 | 全部复用现成范式（doSave/doSeal/onMutated/ConfirmDialog），零新机制 | 挪位置不重写逻辑 |

## 5. 文件结构总表

| 文件 | 动作 | 任务 |
|---|---|---|
| `src/snowel_core/api.py` | 新只读门面 `beats_of(chapter_id)`（R1） | T2 |
| `shell/src/snowel/mcp_server.py` | ADVANCED_CATALOG 四项登记 + extension_packs 文案 + `snowel_advanced` op 分派（R3） | T1 |
| `shell/src/snowel/web_server.py` | 新端点：`GET/POST /api/inspirations`、`GET /api/chapters/{id}/beats`、`POST /api/beats/merge`、`POST /api/beats/delete`；`/api/generate` 透传 `derive_from` | T2 |
| `web/src/components/InspirationPanel.tsx` | 新建：保存原话 + 列表（R4） | T3 |
| `web/src/components/GenerateForm.tsx` | 灵感多选 chip → `derive_from` | T3 |
| `web/src/types.ts` / `web/src/api.ts` | InspirationItem 等类型 + 新端点封装 | T3 / T4 |
| `web/src/App.tsx` | InspirationPanel 挂载（R4） | T3 |
| `web/src/components/ProseEditor.tsx` | 拍列表 + 合并/删除操作（R5） | T4 |
| 测试 | `tests/shell/test_mcp_server.py`（T1）；`tests/shell/test_web_server.py`（T2）；`web/src/components/InspirationPanel.test.tsx` + `GenerateForm.test.tsx` 扩 + `App.test.tsx` 扩（T3）；`ProseEditor.test.tsx` 扩（T4） | — |
| `docs/v1.0.0/testcases.md` | §9 壳域 +TC-SH-09/10/11、§11.2 范围 01–08→01–11（76→79 例） | T5 |
| `tests/README.md` | 反向索引同步（shell 行） | T5 |

## 6. 任务清单

### Task 1: MCP advanced 四操作（TC-SH-11 / R3）

**实现**：ADVANCED_CATALOG 登记四项（hint 写明对应门面与参数）；`snowel_advanced` op 分派：`inspiration_save`（params `{text}`，require_write）、`inspiration_list`（只读）、`beat_merge`（`{source, target}`，require_write）、`beat_delete`（`{beat_id, reason?}`，require_write）——照既有 op 分派形状返回 `{"wired": True, ...结果}`；`extension_packs` 占位文案更新（R3）。

**测试**（`tests/shell/test_mcp_server.py`）：
```python
def test_advanced_new_ops_catalog()            # 目录含四新项 wired 标志/参数提示；
                                               # extension_packs 文案为"仅 CLI"（TC-SH-11 锚）
def test_advanced_inspiration_save_and_list()  # op 全流程：save→list 见条目；空文本 400 语义
def test_advanced_beat_merge_delete_ops()      # 造两拍 merge 成功 / delete 空拍成功 /
                                               # delete 被引用拍 → 错误响应含拒绝文案
def test_advanced_write_ops_require_lease()    # readonly 会话下写 op 被拒（require_write 路径）
```
既有 `test_advanced_catalog_and_rebuild` 的 wired 集合断言同步扩展；`test_exactly_six_tools` 必须原样保持绿（不变式）。

### Task 2: Web API 路由 + 拍列表门面（TC-SH-09/10 数据面 / R1）

**实现**：
- `api.beats_of(chapter_id)`：内联 SQL（仿 inspirations() 手法）`WHERE types LIKE '%MicroBeat%' AND json_extract(address,'$.chapter')=?` 按实现者核实的 address 真实键名，`ORDER BY story_order`；返回 `[{"id", "name", "story_order"}]`（显示名取 name 列，实现者按 schema.sql 节点表现状定）。
- web_server 新端点：`GET /api/inspirations`、`POST /api/inspirations {text}`（`_require` 守卫 + `_require_write`）、`GET /api/chapters/{chapter_id}/beats`、`POST /api/beats/merge {source, target}`、`POST /api/beats/delete {beat_id, reason?}`（皆 `async def` + `_require_write`）；`/api/generate` body 透传 `derive_from`（仅 list[str] 时传门面，缺席不传——保持既有调用零变化）。

**测试**（`tests/shell/test_web_server.py`，ASGITransport 范式）：
```python
def test_inspirations_endpoints()          # POST 保存 → GET 列表见条目；空 text → 400 detail 文案；
                                           # readonly 下 POST → 409 只读文案
def test_chapter_beats_endpoint()          # seed 两拍 → GET 按序返回 id/name/story_order
def test_beat_merge_delete_endpoints()     # merge 成功（事件落库）/ delete 空拍成功 /
                                           # delete 被 planted_at 引用拍 → 400 + 拒绝文案（TC-SH-10 后半锚）
def test_generate_accepts_derive_from()    # body 带 derive_from → ai_generate 收到；不带来调用同旧
```

### Task 3: Web 灵感面板（TC-SH-09 / R4）

**实现**：`InspirationPanel.tsx`（textarea 保存原话 → POST；useApi 列表渲染 id/text/序号；空文本/只读禁用、错误红条——doSave 范式）挂 App 右栏提案 tab（GenerateForm 之上）；`GenerateForm` 加灵感多选（chips 勾选 → `derive_from: string[]`，灵感列表复用同端点数据；无灵感时多选区隐藏）；types.ts 加 `InspirationItem {id, name, text}`。

**测试**（vitest，vi.mock api 范式）：
```tsx
// InspirationPanel.test.tsx
render 保存原话 → api.post("/api/inspirations", {text}) 参数断言 + 列表渲染条目
空文本/只读 → 按钮禁用；POST 失败 → 红条 detail 呈现
// GenerateForm.test.tsx 扩
勾选灵感 → api.post("/api/generate", body) 含 derive_from=[...]；未勾选 body 不含该键
```

### Task 4: Web 拍操作（TC-SH-10 / R5）

**实现**：`ProseEditor` 章编辑区加拍侧栏（`useApi(/api/chapters/{id}/beats)` 列表：序号+名称）：每拍"合并"按钮（点选目标相邻拍 → ConfirmDialog，对话框内列出**伏笔迁移预览**"将迁移 N 个伏笔：<名称…>"，数据 = `stats/foreshadow` 过滤 `planted_at === source`）→ `POST /api/beats/merge`；每拍"删除"按钮 → ConfirmDialog → `POST /api/beats/delete`；400 detail（"该拍承载 N 个伏笔引用…"）红条呈现。操作成功 `onMutated` 刷新。

**测试**（vitest，`ProseEditor.test.tsx` 扩 + mockPaths 喂 beats 数据）：
```tsx
拍侧栏渲染章内拍列表（按 story_order）
合并流：选源拍→点合并→ConfirmDialog 含伏笔预览条目→确认→api.post("/api/beats/merge",{source,target})
删除流：点删除→确认→api.post("/api/beats/delete",{beat_id})
拒绝呈现：post 抛 Error("该拍承载 1 个伏笔引用…")→ 红条文案呈现
只读：合并/删除按钮禁用
```

### Task 5: 黑盒落锚与收口核对（TC-SH-09/10/11 转正）

- `testcases.md` §9 壳域表 +3 例（给定/操作/预期/覆盖照 §4 语义写：09 灵感闭环、10 拍操作含拒绝呈现、11 MCP advanced 目录项）；§11.2 壳域范围 `TC-SH-01–08`→`01–11`。
- `tests/README.md` shell 行反向索引同步。
- 收口 grep 实证：三例编号在 testcases.md、对应测试锚（test_web_server/test_mcp_server/vitest）grep 可见，防虚登记。

### 收尾（dev-workflow §7 全流程）

终审（全分支独立评审）→ 修复波 + 定向复审 → 合并 `dev-1.0.0`（合并结果主仓库全量重跑：pytest + vitest + `npm run build`；worktree 需 `npm ci` 装 web 依赖后验前端）→ 删 worktree/feat 分支 → ledger 归档 `plans/2026-08-28-shell-exposure/ledger.md`（**L25 全关**登记）→ 更新 AGENTS.md 阶段指针（Step 4 完成 → Step 5 rewrite+HTTP；EX-③ 挂账条件措辞已更新）→ 推送 dev。

## 7. 执行参数

| 项 | 值 |
|---|---|
| 模式 | Subagent-Driven（5 任务：T1 独立、T2→T3→T4 串行依赖、T5 收口殿后；两席评审/任务；controller 不写码） |
| worktree | `D:\Code\snowel-shell-exposure`（兄弟目录，从 dev-1.0.0 切；web 依赖需 `npm ci`） |
| 分支 | `feat/shell-exposure` → merge --no-ff 回 `dev-1.0.0` |
| 测试基线 | 合并前 309 + 74 + build 绿为底（预计后端净增 ~12、前端净增 ~10） |
| 修环上限 | 5 轮（R1-3 原实现者，R4-5 换强模型新派） |
| Step 5 接口 | rewrite_query + streamable HTTP（addendum §5）；minor 池 shell 侧（reject_auto 注释纠错）随 Step 5 分摊 |
