# v1.0.0 范围扩容 Step 1：core 功能债（beat_deleted + L23 + TOCTOU + 两阶段恢复）

> 日期：2026-08-27。来源：范围扩容裁决（`requirements-addendum.md` §2 / 裁决 3）——8 step 链第 1 步。
> 性质：功能债清偿计划——全部语义已在 addendum §2 定稿（TC-ON-17 用例与 beat_deleted 载荷 `{beat_id, reason?}` 勿重开裁决），本计划只做工程拆解。
> 上游恢复：`details/handoff-scope-extension-01.md` §3（Step 1 开箱上下文）。

## 1. 背景与范围

| 项 | 内容 |
|---|---|
| beat_deleted | `api.delete_beat(beat_id, reason=None)`：严格拒绝语义（被 planted_at 引用即拒）+ `beat_deleted` 事件 + 投影 active=0（TC-ON-17） |
| L23 全家 | `merge_beats` 两端 active 校验（重复合并自然拒绝）；`valid_until_beat` 指向源拍时随 merge 迁移到目标拍 |
| TOCTOU | `merge_beats` 伏笔预查移入追加事件的同一事务（web 暴露后双进程可达，SQLite 不防） |
| 两阶段恢复 | confirm 与 `derived_from_registered` 两事务间崩溃窗口：core 幂等自愈 API + 壳层可写会话接线（L6 reregister 同型） |
| derive_from 补强 | 校验错误路径自动化测试（非 Inspiration id / 缺失 id）+ 重复 id 去重（防平行边） |
| core 侧 minor | inspirations 排序、save_inspiration 空文本校验、extract_many 异常类型并入消息、门面 json.loads 防御、路由组合测试 |

不在范围：壳端功能暴露（Web/MCP 的灵感面板、拍操作——Step 4）；conftest fastapi 条件化（Step 2 minor）；L24 扩展包（Step 2/3）；L16 发布债（Step 8）。

## 2. Global Constraints

- 事件日志 append-only：新功能走新事件 kind（`beat_deleted`），禁止改写历史事件。
- 铁律 3 只约束 AI 产物；拍删除/合并是作者显式操作，直接追加事件不走提案（与 merge_beats 同款）。
- 领域逻辑只在 snowel-core；壳（shell/）只接线（project.py 一行调用），不含逻辑。
- 每任务 TDD：先写失败测试再实现；conventional commits，每任务一提交。
- 新测试落 `tests/<module>/` 就近文件；`tests/README.md` 反向索引与 `testcases.md` 落锚同步——grep 实证，防虚登记（终核教训）。

## 3. Preflight 挂账裁决（同版本已归档 ledger 全量双查）

| 挂账 | 内容 | 裁决 | 去向 |
|---|---|---|---|
| L16 | Windows python.org 扩展加载崩 + 同步发包 | 不携带（环境/发布债） | Step 8 |
| L23 | beat_deleted + 拍 active 语义（本计划 §1 前两行） | 携带 | Task 1 / Task 2 |
| L24 | TC-EX 扩展包机制全域 | 不携带 | Step 2/3 |
| L25 | core 部分（TOCTOU + 两阶段恢复 + derive_from 测试）；壳端暴露部分 | core 部分携带；暴露部分不携带 | Task 3 / Step 4 |
| L26 | chat 召回 20 有意上限（记录性） | 不动（勿当 bug 修） | — |
| minor 池 | core 侧 5 项（§1 末行）；shell 侧（reject_auto 注释纠错）与 web 侧（Viz.test 常量）分摊 Step 5/6 | core 侧携带 | Task 4 |

## 4. 计划级设计裁决（预登记 Ruling，执行期可依证修订）

| # | 裁决 | 理由 | 若错的成本 |
|---|---|---|---|
| R1 | `delete_beat` 严格按 addendum 字面：引用检查只查 `planted_at`；**不校验 active**（已失效拍可再显式删除——merge 失效 ≠ 显式删除，事件历史区分两种意图）；`valid_until_beat` 指向被删拍的边由 recompute 自然变开放区间（valid_until=NULL），不扩需求 | 改动最小；TC-ON-17"迁移伏笔后 delete 成功"场景在 merge 失效源拍后仍走得通 | 补 active 校验一行 + 拒绝文案；悬挂边语义若需拒绝，加一条预查即可 |
| R2 | `valid_until_beat` 迁移沿用 R1 载荷自含模式：`beat_merged` 载荷增 `moved_valid_until: [{edge_id, old, new}]`，投影按载荷执行 | 与 moved_foreshadows 同构；复盘可读、rebuild 可重放 | 载荷与投影不一致则 handler 局部重写 |
| R3 | TOCTOU 修法 = 预查 SELECT 移入 `BEGIN IMMEDIATE` 事务内（写锁串行化双进程），不加重试 | 事务原子性是既有一等机制；重试引入复杂度无收益 | 无实质风险 |
| R4 | 两阶段恢复 = core 幂等 API `recover_derived_from()` + 壳层 `open_project` 拿到写租约后调用（失败记警告不阻断打开，下次重试）；**不挂 core `open()`**——readonly 是壳层守卫（F2），core 入口写库会绕过它 | L6 reregister_prose 同型（core 显式 API + 壳层择机调用）；补边逻辑与 confirm 抽公共私有函数，单一实现 | 若验收要求启动必愈，把调用点前移到各壳 main 入口，一行 |
| R5 | derive_from 重复 id 在生成入口去重（`dict.fromkeys` 保序），confirm/恢复路径不再重复防御 | 单点防御最薄；平行边一旦落库只能靠 retcon 清理 | 无实质风险 |

## 5. 文件结构总表

| 文件 | 动作 | 任务 |
|---|---|---|
| `src/snowel_core/api.py` | 新 `delete_beat`；`merge_beats` active 校验 + 预查入事务 + 载荷增键；`confirm` 补边抽私有函数 + 新 `recover_derived_from`；minor 四处（inspirations 排序/防御、save_inspiration 空文本、extract_many 异常类型） | T1 / T2 / T3 / T4 |
| `src/snowel_core/storage/projector.py` | 新 `_beat_deleted` handler；`_beat_merged` 按 `moved_valid_until` 迁移边 | T1 / T2 |
| `src/snowel_core/flow/generate.py` | derive_from 去重 | T3 |
| `shell/src/snowel/project.py` | `open_project` 可写分支接线一行 | T3 |
| `docs/v1.0.0/testcases.md` | ON 域 +1：TC-ON-17（75→76 例） | T1 |
| `tests/README.md` | 反向索引同步（foreshadow 行、project 行） | T1 / T3 |
| 测试 | `tests/consistency/test_foreshadow.py` 追加（T1/T2）；`tests/flow/test_inspiration.py` 追加（T3）；`tests/shell/test_project.py` 追加（T3）；`tests/writeback/test_extract.py` 追加（T4） | 全部 |

**共享文件冲突扫描**（顺序执行，后任务基于前任务提交）：

| 文件 | 触及任务 | 裁决 |
|---|---|---|
| `api.py` | T1/T2/T3/T4 | 触及方法互不重叠；T3 对 confirm 是行为等价重构（既有测试守护），无兼容层 |
| `projector.py` | T1（新增）/T2（扩展现有） | 无重叠行 |
| `test_foreshadow.py` | T1/T2 同文件追加 | 顺序执行无冲突 |
| `testcases.md` / `tests/README.md` | T1/T3 | 收尾统一 grep 实证核对 |

## 6. 任务清单

### Task 1: beat_deleted 事件面（TC-ON-17 / addendum §2.1）

**实现**：
- `api.delete_beat(beat_id: str, reason: str | None = None) -> int`：校验节点存在、types 含 MicroBeat（照 merge_beats 校验风格，不查 active——R1）→ 事务内预查 planted_at 引用（与 merge_beats 同款 json_extract 查询）：>0 → `ValueError("该拍承载 N 个伏笔引用，先 merge_beats 到承接拍或迁移伏笔")`（N 为实际数）→ 通过则单事务追加 `beat_deleted`（载荷 `{beat_id}`，reason 非 None 时加 `reason` 键）+ 投影。
- projector `_beat_deleted`：`UPDATE nodes SET active=0 WHERE id=?`（照 `_beat_merged` 源拍失效同款；story_order 清 NULL 由 apply 尾部 recompute 既有机制处理）。
- `testcases.md` ON 域落 TC-ON-17（16→17 例，总数 75→76）；`tests/README.md` foreshadow 行补反向索引。

**测试**（`tests/consistency/test_foreshadow.py` 追加）：
```python
def test_delete_beat_rejects_foreshadow_reference(api):  # TC-ON-17 前半
    # 伏笔 planted_at=mb1 已确认 → delete_beat("mb1") ValueError
    # 且 events 总数不变（拒绝不留半事件，事务原子）
def test_delete_beat_empty_succeeds(api):  # TC-ON-17 后半
    # merge_beats(mb1, mb2) 迁移伏笔 → delete_beat("mb1") 成功
    # 恰一条 beat_deleted；mb1 active=0、story_order NULL；reason 透传入载荷
def test_delete_beat_validates(api):  # 校验面
    # 不存在 id / 非 MicroBeat → ValueError；事件日志无新事件
```

### Task 2: L23 merge 语义 + TOCTOU（addendum §2.1 伴生项 + §2.2）

**实现**：
- `merge_beats` 校验循环改 `WHERE id=? AND active=1`，row None 报"拍节点不存在或已失效: {nid}"——两端任一失效即拒；重复合并同一源拍（首次已失效）自然拒绝，无新错误分支。
- `valid_until_beat` 迁移（R2）：事务内预查 `SELECT id FROM edges WHERE json_extract(props,'$.valid_until_beat')=?`（=source）→ 载荷增 `moved_valid_until: [{edge_id, old, new}]`。
- TOCTOU（R3）：`moved` 伏笔预查与 `moved_valid_until` 边预查**全部移入** `db.transaction` 块内、`append_event` 之前。
- `_beat_merged` handler 扩展：按 `moved_valid_until` 读改写边 props（照 moved_foreshadows 同款"目标不存在静默跳过"幂等风格）；apply 尾部 recompute 自动重算物化 valid_until。

**测试**（`tests/consistency/test_foreshadow.py` 追加）：
```python
def test_merge_rejects_inactive_source(api):  # 重复合并自然拒绝
    # merge(mb1→mb2) 成功后 merge(mb1→mb3) → ValueError（mb1 已失效）
def test_merge_rejects_inactive_target(api):
    # 目标拍先被合并失效 → merge(mb3→mb2) → ValueError
def test_merge_migrates_valid_until(api):
    # 边 props.valid_until_beat=mb1（seed 时 edge fact 带 valid_until_beat）
    # merge(mb1, mb2) → 载荷 moved_valid_until 含该边 old/new；
    # 边 props.valid_until_beat=="mb2"；物化 valid_until==mb2 的 story_order
```
既有 `test_beat_merged_migrates_foreshadow` / `test_merge_beats_validates` 全量回归（载荷增键不破坏既有断言；"不存在"文案语义扩为"不存在或已失效"需同步该用例 match 模式）。

### Task 3: derived_from 两阶段恢复 + 补强（addendum §2.2 / L25 core 部分）

**实现**：
- `api.py` 抽私有函数 `_register_derived_edges(conn, pairs)`（confirm 内 205-216 行的补边逻辑原样搬移，confirm 改调用——行为等价重构）。
- `api.recover_derived_from() -> int`：扫描 `status='confirmed' AND payload LIKE '%"derive_from"%'` 提案 → json 解析精筛 → 对每个 (产物 node id × derive_from id) 组合：两端节点均存在且 DERIVED_FROM 边缺失 → 单事务一条 `derived_from_registered` 补录全部缺边 → 返回补录事件数；无缺口返回 0（幂等，被 exclude 的 fact 节点未物化、自然跳过）。
- 壳层接线（R4）：`shell/project.py` `open_project` 在 `got` 为真后调用 `api.recover_derived_from()`，异常捕获记 stderr 警告不阻断打开。
- `flow/generate.py`：`payload["derive_from"] = list(dict.fromkeys(derive_from))`（R5 去重）。

**测试**：
```python
# tests/flow/test_inspiration.py 追加
def test_derive_from_validation_errors(api):  # §2.2 伴生测试
    # derive_from=["nope"] → ValueError；derive_from=[mb1（MicroBeat）] → ValueError
def test_derive_from_duplicate_ids_dedup(api):
    # derive_from=[iid, iid] → confirm 后 src→dst 恰一条 DERIVED_FROM（无平行边）
def test_recover_derived_from_heals_window(api):
    # save_inspiration → ai_generate(derive_from) → api.proposals.confirm(pid)
    # （直调 queue.confirm 绕过 api.confirm = 天然制造两事务间崩溃窗口）
    # → 产物节点已物化、无边；recover_derived_from() 返回 1 且边补上；再跑返回 0（幂等）
def test_recover_derived_from_noop_when_complete(api):
    # 正常 api.confirm 全流程后 recover → 0

# tests/shell/test_project.py 追加
def test_open_project_writable_heals_window(tmp_path):
    # 构造缺口项目 → open_project(want_write=True) → DERIVED_FROM 边已补
def test_open_project_readonly_skips_heal(tmp_path):
    # 同缺口 → open_project(want_write=False) → 边保持缺失（F2：readonly 不写库）
```

### Task 4: core 侧 minor 包（addendum §8 Step 1 minor 分摊）

| 子项 | 落点 | 修法 | 锚 |
|---|---|---|---|
| inspirations 无排序 | `api.py` inspirations() | 内联 SQL `ORDER BY created_event`（先保存先显示；find_nodes 不支持排序） | 多条灵感稳定序断言一例 |
| save_inspiration 空文本 | `api.py` save_inspiration() | `if not (text or "").strip(): raise ValueError("灵感文本不能为空")` | 空串/纯空白 → ValueError 一例 |
| extract_many 异常类型 | `api.py` extract_many() | `f"{type(e).__name__}: {e}"` 并入 error | 既有 `test_extract_many_collects_per_chapter_failures` 断言 error 含异常类型名（追加或改写） |
| 门面 json.loads 防御 | `api.py` inspirations() | `(json.loads(props).get("inspiration") or {}).get("text", "")` 兜底；实现者另 grep 门面层 json.loads 对用户可控数据的无防御点，发现即修并记 ledger（minor 池"等"字兜底） | 手工构造无 inspiration 键的 Inspiration 节点 → 列表返回不崩 |
| 路由组合测试 | `tests/writeback/test_extract.py` | 补"config 已设 small_model + 章未标 low"→ model=None 不路由（现有三例缺此组合） | 一例 |

### 收尾（dev-workflow §7 全流程）

终审（全分支独立评审）→ 修复波 + 定向复审 → 合并 `dev-1.0.0`（合并结果主仓库全量重跑：pytest + vitest + `npm run build`；worktree 干过活后先 `pip install -e . -e ./shell` 校 editable 指向）→ 删 worktree/feat 分支 → ledger 归档 `plans/2026-08-27-core-debt/ledger.md` → 更新 AGENTS.md 阶段指针（L23 关闭、L25 core 部分关闭、75→76 例口径、minor 池 core 侧清空）→ 推送 dev。

## 7. 执行参数

| 项 | 值 |
|---|---|
| 模式 | Subagent-Driven（4 任务，两席评审/任务；体量与独立性均适配 SDD，controller 不写码） |
| worktree | `D:\Code\snowel-core-debt`（兄弟目录，从 dev-1.0.0 切） |
| 分支 | `feat/core-debt` → merge --no-ff 回 `dev-1.0.0` |
| 测试基线 | 合并前 264/264 + 74/74 + build 绿；每任务聚焦跑，提交前全量 |
| 修环上限 | 5 轮（R1-3 原实现者，R4-5 换强模型新派） |
