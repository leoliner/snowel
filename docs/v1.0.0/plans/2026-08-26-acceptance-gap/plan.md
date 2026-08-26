# v1.0.0 验收补丁计划（三缺口 + L22 小补包）

> 日期：2026-08-26。来源：66 例黑盒终核（`handoff-acceptance-01.md` §2.1）发现 3 例真缺口，用户裁决"拆小计划现在补"；顺带承接 L22 小补包全部六项与 L20/L21 挂账。
> 性质：补丁计划——无新领域概念，全部功能在 requirements/design 既有裁决内（D6 / §4.7 / §6.3）。

## 1. 背景与范围

| 项 | 内容 |
|---|---|
| 缺口 1 | TC-ON-08（D6）：`beat_merged` 拍合并事件 + 伏笔引用自动迁移，源码零实现、计划未豁免 |
| 缺口 2 | TC-ON-12（§4.7 原则 7）：灵感原话永久保留 + 提炼物 `DERIVED_FROM` 边，源码零实现、计划未豁免 |
| 缺口 3 | TC-RT-05（§6.3 第 3 条）：低重要章节批量抽取/小模型路由，源码零实现、README 反向索引虚登记 |
| 顺带 | L22 六小修（favicon / reject_auto / onGoGenerate / chat to_thread / ForeshadowMap / sse.ts）；L20 心跳线程；L21 检索 limit；tests/README 登记 `test_vec.py`；弱覆盖补锚（ON-13 / ON-14）；"66 例"→"75 例"口径统一 |

不在范围：TC-EX 扩展包（计划内豁免，v1.1）；`beat_deleted`（D6 另一半，新挂账 L23）；ON-11 显式拒绝锚（结构性满足，见 §3 备注）；壳端（MCP/CLI/Web）灵感层与拍合并的操作暴露（用例只要求 api 门面可观察，壳面挂 v1.1）。

## 2. Global Constraints

- 领域逻辑只在 snowel-core；壳（shell/、web/）不含领域逻辑。
- 事件日志 append-only：新功能一律走新事件 kind，禁止改写历史事件。
- 铁律 3（提案-diff-确认）只约束 AI 产物；作者手输内容（灵感原话、重要性标记、拍合并指令）是作者显式操作，直接追加事件，不走提案。
- 每任务 TDD：先写失败测试再实现；conventional commits，每任务一提交。
- 新测试落 `tests/<module>/` 同名子目录并更新 `tests/README.md` 反向索引。

## 3. Preflight 挂账裁决（同版本已归档 ledger）

| 挂账 | 内容 | 裁决 | 去向 |
|---|---|---|---|
| L16 | Windows python.org 构建扩展加载崩 + 发包方案 | 不携带（环境/发布债，与本计划代码面无关） | 发版前单独处置 |
| L20 | daemon 心跳线程泄漏至进程退出（良性） | 携带 | Task 4 |
| L21 | api.search 门面 limit=20 与 fts 100 不一致 | 携带（统一为 100） | Task 4 |
| L22 | 六项终审 triage park 小修 | 携带 | Task 4 / Task 5 |

新挂账预登记（本计划产生，归档时编号顺延）：

| 新挂账 | 内容 | 承接 |
|---|---|---|
| L23 | `beat_deleted` 事件（D6 后半：拍删除显式事件 + 伏笔引用处置策略） | v1.1 |
| L24 | TC-EX-01~05 扩展包机制（E4 目录式发现/项目覆盖/卸载校验/hooks 隔离） | v1.1 |
| L25 | 灵感层与拍合并的壳端暴露（MCP advanced / Web 面板 / CLI） | v1.1 |

备注（不挂账）：TC-ON-11 轨道"可增不可删改"为**结构性满足**——api 无任何删除/重命名轨道的写入口，唯一通道是 retcon 的 `track_updates`（显式 retcon 语义），黑盒"无路径可删改"成立；v1.1 若加壳端暴露再补显式拒绝锚。

## 4. 计划级设计裁决（预登记 Ruling，执行期可依证修订）

| # | 裁决 | 理由 | 若错的成本 |
|---|---|---|---|
| R1 | `beat_merged` 事件载荷自含迁移结果：`{source_beat_id, target_beat_id, moved_foreshadows: [{foreshadow_id, old, new}]}`；api 追加事件前预查受影响伏笔写入载荷，投影器按载荷执行（源拍 active=0 + 伏笔 planted_at 改指目标拍） | 设计 §事件表要求载荷含"受影响伏笔引用及迁移结果"；事件自含则复盘可读、rebuild 可重放 | 若预查与投影不一致需改为投影器自算，一个 handler 内局部重写 |
| R2 | 灵感原话 = **Inspiration 节点**（types=["Inspiration"]，全文存 props.inspiration.text），不建独立表 | 一等图公民：DERIVED_FROM 边天然可连（edges.kind 枚举已预留）、find_nodes/edges_of 反查免费、rebuild 语义统一 | 若全文过长影响 props JSON 性能，迁移到旁挂大文本表，投影层一处改动 |
| R3 | TC-RT-05 "批量抽取**或**小模型"取**小模型路由**承载成本语义（`extract_and_writeback` 的 `model` 参数通道已有），批量 = `extract_many` 循环便捷入口（省操作不省调用） | 需求原文二者是"或"关系；单章一次调用是抽取提示词的结构约束（分级后校按章落库），拼多章反而放大上下文成本 | 若验收坚持"多章一次调用"，在 extract_many 内聚合提示词，分级逻辑不变 |
| R4 | 低重要标记走事件 `chapter_importance_set`（append-only 铁律），投影更新 chapter 节点 props.importance；config 键 `extraction.small_model`（默认空 = 行为不变，向后兼容） | 元数据改动也必须事件化，否则 rebuild 后漂移 | 无实质风险 |
| R5 | ON-13 补锚 = "Chapter 节点定位的伏笔在 stats_foreshadow 视图与 MicroBeat 定位一致"；ON-14 补锚 = `register_foreshadow(origin="ai")` 确认入典 + 否决不入典闭环 | 弱覆盖最小补法，不造结构性满足的死测试（ON-11 教训） | — |

## 5. 文件结构总表

| 文件 | 动作 | 任务 |
|---|---|---|
| `src/snowel_core/storage/projector.py` | HANDLERS 注册 `beat_merged` / `chapter_importance_set` | T1 / T3 |
| `src/snowel_core/api.py` | `merge_beats` / `save_inspiration` / `inspirations` / `set_chapter_importance` / `extract_many`；`ai_generate` 透传 `derive_from` | T1 / T2 / T3 |
| `src/snowel_core/flow/generate.py` | `ai_generate` payload 增加 `derive_from`；confirm 后建 DERIVED_FROM 边 | T2 |
| `src/snowel_core/writeback/extract.py` | 低重要章节读 config `extraction.small_model` 路由 | T3 |
| `shell/src/snowel/web_server.py` | reject_auto 400 校验；`/api/chat` iterate_in_threadpool | T4 |
| `src/snowel_core/api.py`（search） | limit 默认 20→100（L21） | T4 |
| `tests/conftest.py` | L20 autouse fixture（session 级停心跳线程）；FakeBackend 记录 model 参数 | T3 / T4 |
| `web/public/favicon.svg` | 模板紫 → 琥珀 token 系 | T5 |
| `web/src/App.tsx` + `ProseEditor.tsx` | onGoGenerate 接线（空态"去生成"） | T5 |
| `web/src/components/ForeshadowMap.tsx` | slot 上限化，高拍数不溢出 | T5 |
| `web/src/sse.ts` | 非 2xx 文本回落顺序理顺 | T5 |
| 测试 | `tests/storage/test_projector.py` 追加（T1）；`tests/flow/test_inspiration.py` 新建（T2）；`tests/writeback/test_extract.py` 追加（T3）；`tests/shell/test_web_server.py` + `tests/`（T4）；`web/src` vitest 追加（T5） | 全部 |

## 6. 任务清单

### Task 1: beat_merged 拍合并（TC-ON-08 / D6）

**实现**：
- `api.merge_beats(source_beat_id, target_beat_id)`：校验两节点存在、均含 MicroBeat 类型、id 不同 → 预查 `nodes` 中 props.foreshadow.planted_at == source 的 Foreshadow 节点 → 单事件 `beat_merged`（载荷见 R1）→ 投影。
- projector handler：源拍 active=0；按 `moved_foreshadows` 改伏笔 planted_at（UPDATE nodes props）；目标拍不动；水位线照常推进。
- 实现者验证：源拍失效后同 scene 后续拍的 story_order 重算不漂移（派生序机制既有；若有缺口最小修复并记 ledger）。

**测试**（`tests/storage/test_projector.py` 追加，或随伏笔语义就近放 `tests/consistency/test_foreshadow.py`）：

```python
def test_beat_merged_migrates_foreshadow(api):  # TC-ON-08
    # 拍 b1(ch2,sc1,3) b2(ch2,sc1,4) 已确认；伏笔 planted_at=b1 已确认
    api.merge_beats("b1", "b2")
    # 恰一条 beat_merged 事件；b1 active=0；伏笔 planted_at=="b2"（不漂移不报死链）
    # R1：事件载荷 moved_foreshadows 含该伏笔 old/new

def test_foreshadow_chapter_location_view_consistent(api):  # ON-13 补锚
    # planted_at=Chapter 节点 id 注册伏笔 → stats_foreshadow 可查（与 MicroBeat 定位同视图）
```

### Task 2: 灵感层 + DERIVED_FROM（TC-ON-12 / §4.7）+ ON-14 补锚

**实现**：
- `api.save_inspiration(text)`：直接追加 `inspiration_saved` 事件 {facts:[Inspiration 节点]}（作者手输不走提案，见 §2 约束）→ 投影建节点。
- `api.inspirations()`：列表查询（find_nodes(type="Inspiration") 即可，门面方法包装）。
- `ai_generate(..., derive_from: list[str] | None)`：校验 id 均为 Inspiration 节点 → payload.derive_from 透传；confirm 路径在产物节点物化后建 DERIVED_FROM 边（src=产物节点，dst=灵感节点）。
- 查询面复用既有 `edges_of(insp_id)`（反向反查免费），不新增。

**测试**（`tests/flow/test_inspiration.py` 新建）：

```python
def test_inspiration_preserved_and_derived(api, fake_backend):  # TC-ON-12
    iid = api.save_inspiration("Brainstorm 原话全文……")
    pid = api.ai_generate("premise", derive_from=[iid])
    api.confirm(pid)
    assert api.inspirations()[0]["text"] == "Brainstorm 原话全文……"  # 永久保留
    kinds = {e["kind"] for e in api.edges_of(iid)}                    # DERIVED_FROM 指回
    assert "DERIVED_FROM" in kinds

def test_foreshadow_ai_origin_lifecycle(api):  # ON-14 补锚
    pid = api.register_foreshadow("怀表", planted_at=beat_id, origin="ai")
    api.confirm(pid)   # 入典 origin=="ai"
    pid2 = api.register_foreshadow("信笺", planted_at=beat_id, origin="ai")
    api.reject(pid2, reason="重复")  # 不入典（提案否决既有语义回归）
```

### Task 3: 低重要章节小模型路由 + 批量入口（TC-RT-05 / §6.3）

**实现**：
- `api.set_chapter_importance(chapter_id, importance)`：`"low"|"normal"` → 事件 `chapter_importance_set` → 投影更新 chapter 节点 props.importance。
- `extract_and_writeback`：读 chapter props.importance=="low" 且 config `extraction.small_model` 非空 → `backend.generate(prompt, model=small_model)`；分级逻辑零改动。
- `api.extract_many(chapter_ids, backend)`：循环便捷入口（R3）。
- `conftest.py` FakeBackend：记录调用 model 参数（供断言）。

**测试**（`tests/writeback/test_extract.py` 追加）：

```python
def test_low_importance_routes_small_model(api, fake_backend, tmp_path):  # TC-RT-05
    api.set_chapter_importance("ch1", "low")
    config.set(conn, "extraction.small_model", "qwen-small")
    api.extract_and_writeback("ch1", fake_backend)
    assert fake_backend.calls[-1]["model"] == "qwen-small"   # 成本控制生效
    # 分级语义不变：high→提案、low→auto_canonized（既有断言复跑）

def test_small_model_unset_keeps_default(...):  # 向后兼容
    # 未标记/未配置 → model=None，行为与现状逐字节一致
```

### Task 4: 后端小修包（L22#2/#4 + L20 + L21 + README 登记）

| 子项 | 落点 | 修法 | 锚 |
|---|---|---|---|
| L22#2 reject_auto 500→400 | `web_server.py:315` | 路由 try/except ValueError → HTTPException(400) | `test_web_server.py` 追加畸形二元组得 4xx 一例 |
| L22#4 /api/chat 阻塞事件循环 | `web_server.py:382` | `fastapi.concurrency.iterate_in_threadpool` 包裹阻塞调用 | 既有 chat 测试回归 |
| L20 心跳线程泄漏 | `tests/conftest.py` | session 级 autouse fixture 停 daemon 线程 | 无新断言（进程干净退出即可） |
| L21 limit 不一致 | `api.py:86` search | 默认 limit 20→100（与 fts 门面统一） | `test_api.py` 追加默认值断言一例 |
| README 漏登记 | `tests/README.md` §1 | 补 `storage/test_vec.py` 行（TC-RT-06 + L8 原子性回归） | 文档 |

### Task 5: 前端小修包（L22#1/#3/#5/#6）

| 子项 | 落点 | 修法 | 锚 |
|---|---|---|---|
| L22#1 favicon 模板紫 | `web/public/favicon.svg` | 换 ui-design-01 琥珀 token 系单色 SVG | 目检 |
| L22#3 空态死按钮 | `App.tsx` → `ProseEditor` | 传 `onGoGenerate={() => setWorkspaceTab('proposals')}`（对齐现有 tab 状态名） | `ProseEditor.test.tsx` 追加点击回调一例 |
| L22#5 高拍数溢出 | `ForeshadowMap.tsx:49` | slot 去下限 8 / 上限化（`Math.min(Math.max(...), 24)` 方向），>30 拍不超画布宽 | `Viz.test.tsx` 追加 35 拍宽度断言 |
| L22#6 sse 非 2xx 回落 | `sse.ts:18-26` | 先读 text 再 JSON.parse（或删误导注释），错误消息含响应体 | `sse.test.ts` 追加非 JSON 错误体一例 |

### 收尾（dev-workflow §7 全流程）

终审（全分支独立评审）→ 修复波 → 合并 `dev-1.0.0`（合并结果重跑全量：pytest + vitest + `npm run build`）→ 删 worktree/feat 分支 → ledger 归档 `plans/2026-08-26-acceptance-gap/ledger.md` → 更新 AGENTS.md 阶段指针 + **"66 例"→"75 例"口径统一**（AGENTS.md / handoff-acceptance-01.md / 终核结论三处）→ 推送 dev。

## 7. 执行参数

| 项 | 值 |
|---|---|
| 模式 | Subagent-Driven（5 任务，两席评审/任务） |
| worktree | `D:\Code\snowel-acceptance-gap`（兄弟目录，从 dev-1.0.0 切） |
| 分支 | `feat/acceptance-gap` → merge 回 `dev-1.0.0` |
| 测试基线 | 合并前 252/252 + 71/71；每任务聚焦跑，提交前全量 |
| 修环上限 | 5 轮（R1-3 原实现者，R4-5 换强模型新派） |
