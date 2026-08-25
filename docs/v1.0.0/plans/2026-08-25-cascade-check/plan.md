# 级联检查（consistency 引擎 + 冻结线 + retcon）实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 落地需求 §5.5/§5.6 与设计 E5：级联检查规则引擎（三类检查 + 护栏，全量/轻量两档，四写入点统一接线）、冻结线与封卷（volume_sealed + 已封卷拦截）、显式 retcon 流程（影响分析 + 确认 + C5 依赖图精确 stale）、伏笔注册门面与壳接线；并修复挂账 L4/L13（承接）与 L14（顺带）。

**Architecture:** 领域逻辑全部进新模块 `snowel_core/consistency/`（规则注册表 + 运行器 + retcon + 密封线）；规则为纯函数 `Rule(change_set, graph) -> [Violation]`，核心内置规则注册进 registry（扩展包注册接口预留，E4 机制不在本计划）；四写入点在 api 层接线（不进投影器——级联是业务动作不是物化）；冲突产出确定性 diff 修订提案，不自动改、不阻断。

**Tech Stack:** 纯 Python（无新依赖）；FTS 复用（正文引用提示）；tests 全确定性（无 LLM）。

**Spec:** `docs/v1.0.0/requirements.md`（§5.5 级联、§5.6 冻结线/retcon、C7/C11、§4.8 伏笔）、`docs/v1.0.0/design.md`（§9 级联检查引擎 E5、§2.5 轨道、§3.2 事件清单）、`docs/v1.0.0/testcases.md`（TC-CC-01~08、TC-WB-08、TC-ON-10 后半、TC-ON-16、TC-PR-02 retcon 面）

## Global Constraints

- Python ≥3.12；领域逻辑只在 snowel-core；三端只 import `snowel_core.api`（铁律 1）；本计划零 LLM 调用（级联与 retcon 全确定性）。
- 投影器是物化唯一写入口（E2 红线）：seal/retcon 的状态变更走事件追加 + handler 物化；级联检查本身只读。
- 一次确认 = 单事务（E1）：事件+物化原子；级联分析在事务前（只读），冲突提案产出在事务后（独立提案，不阻断主流程）。
- 事件 payload 结构引用只用稳定 ID。
- conventional commits；每任务一提交；新模块建 `tests/consistency/` 并在 `tests/README.md` §1 登记（含黑盒用例反向索引）。
- 沿用现有代码风格：sqlite3.Row、dict 返回、中文 docstring、文件首行 `# src/...` 路径注释。
- 基线：dev-1.0.0 @ 5134560，全量 160/160。

## Preflight 挂账裁决（同版本已归档 ledger）

| # | 挂账 | 裁决 | 落点 |
|---|---|---|---|
| L4 | `descendants` 无边时效过滤、kinds 未消费 | **携带，Task 1 修复** | storage/queries.py |
| L13 | dead 单扫不查死亡拍 active、死亡判定三处重复实现 | **携带，Task 1 统一** | 抽公共助手，snowflake/state_at/compose 共用 |
| L14 | C5 stale 循环事务外逐条标记 | **携带，Task 8 顺带修复**（retcon 精确 stale 重写时包事务） | api.py |
| L15 | 零事实章 appeared 丢失 | 不携带（接受边维持，与级联无交集） | — |
| L16 | Windows 扩展加载/发包 | 不携带（发布债，发版前） | — |

## 计划级设计裁决（预登记 Ruling，执行期可依证修订）

| # | 裁决 | 理由 | 若错的成本 |
|---|---|---|---|
| P1 | **冲突产出确定性 diff 修订提案**：`proposals.create("cascade_revision", {conflicts: [{node_id, key, old, new, refs}], source_change_seq})`，纯 diff 数据，不调用 LLM | §5.5"冲突时生成 diff 式修订提案"指差异呈现；作者想改写可用既有 rewrite 口 | 作者需手动消化 diff——面板可读，可接受 |
| P2 | **两档规则分配**：轻量档（auto 入典/retraction 后）= 矛盾检测 + 依赖反查（变更集直接相关）；全量档（提案确认/retcon 前）= 三类检查 + growth_curve 护栏 + 冻结线 + 轨道棘轮 | E5"全量/轻量两档"+"向前查矛盾/向后查依赖仅是裁剪优化"；retraction 轻量=C11 语义 | 轻量档漏报跨区间冲突——作者审阅面板可见，下个全量档兜底 |
| P3 | **轨道定义修改入口 = retcon 专用**：普通路径无"改轨道定义"门面；`retcon_applied` 物化扩展 `track_updates: [{track_id, definition}]`（UPDATE tracks SET definition）| C7 棘轮（首次挂载后冻结）+ TC-ON-10"修改必须走显式 retcon"；track_added DO NOTHING 物化使普通 upsert 天然不可改 | 轨道定义笔误也走 retcon——低频操作，可接受 |
| P4 | **C5 依赖图精确分析 v1 = 节点 id 交集**：变更集触及的节点 id 集合 ∩ pending 提案 payload（json 串含该 id）→ 只标受影响提案（替代 T17 的全 pending 保守标记；revision 面同步切换到精确版） | 字符串包含是保守超集（误标不漏标）；真正的语义依赖图属后续优化 | 少数无关提案被误标 stale——作者可强行确认，语义安全 |
| P5 | **retcon 全量分析在确认前**：propose_retcon 时跑全量级联，影响清单（Violations + 引用段落 + 受影响提案）进提案 payload；确认后不重跑（分析与确认间世界变化的窗口由 C5 stale 补偿） | §5.6"级联影响分析 + 确认"顺序；确认后重跑会把分析结果埋进事件日志 | 分析过时窗口——stale 机制兜底，可接受 |

## 文件结构总表

| 文件 | 动作 | 职责 |
|---|---|---|
| `src/snowel_core/consistency/__init__.py` | 新建 | 空包 |
| `src/snowel_core/consistency/engine.py` | 新建 | Violation/Rule 协议、规则注册表、run(conn, change_set, tier) |
| `src/snowel_core/consistency/rules.py` | 新建 | 内置规则：矛盾检测/依赖反查/区间重叠/growth_curve 护栏/冻结线/轨道棘轮 |
| `src/snowel_core/consistency/seal.py` | 新建 | 封卷：volume_sealed 事件追加 + 已封卷判定 + 拦截 |
| `src/snowel_core/consistency/retcon.py` | 新建 | propose_retcon（全量分析+影响清单）/ confirm 路径 / track_updates |
| `src/snowel_core/consistency/foreshadow.py` | 新建 | 伏笔注册门面（origin/planted_at 校验） |
| `src/snowel_core/storage/queries.py` | 修改 | descendants 边时效过滤 + kinds 消费（L4） |
| `src/snowel_core/storage/deathbeat.py` | 新建 | 死亡判定公共助手（L13 统一三处） |
| `src/snowel_core/storage/projector.py` | 修改 | retcon_applied 扩展 track_updates 物化 |
| `src/snowel_core/api.py` | 修改 | +cascade_check/seal/propose_retcon/register_foreshadow 门面；confirm/extract/reject_auto 接线级联 |
| `src/snowel_core/writeback/review.py` | 修改 | reject_auto 后轻量级联（接线点） |
| `src/snowel_core/writeback/extract.py` | 修改 | auto 入典后轻量级联（接线点） |
| `src/snowel_core/flow/snowflake.py` + `retrieval/context.py` | 修改 | 死亡判定助手替换（L13） |
| `shell/src/snowel/mcp_server.py` | 修改 | advanced seal/retcon/foreshadow_register 接线 |
| `shell/src/snowel/cli.py` | 修改 | seal 命令接线 |
| `tests/consistency/` | 新建 | 引擎/规则/冻结/retcon 测试 |

---

### Task 1: L4 + L13——descendants 时效过滤与死亡判定统一

**Files:**
- Modify: `src/snowel_core/storage/queries.py:59-71`（descendants）
- Create: `src/snowel_core/storage/deathbeat.py`
- Modify: `src/snowel_core/retrieval/context.py`（_alive 死亡分支）、`src/snowel_core/flow/snowflake.py`（dead 单扫）、`src/snowel_core/storage/queries.py`（state_at 死亡过滤）
- Test: `tests/storage/test_queries.py`（追加）、`tests/consistency/test_deathbeat.py`

**Interfaces:**
- Consumes: 现有 `descendants`、`state_at`、`_alive`、snowflake dead 扫描。
- Produces:
  - `storage.deathbeat.is_dead(conn, node_row, story_order) -> bool | None`：读节点 props 的 `core.death_beat`，解析死亡拍节点（**校验其 active=1**——L13 口径），死亡拍 story_order 非空且 ≤ story_order → True；death_beat 缺失 → None（非角色/未设死点）；死亡拍不可解析/无序 → False（保守存活）。`dead_at(conn, node_row) -> int | None`：返回死亡拍 story_order（含 None 处理），供 dead 名单与 dead_beat 标记复用。
  - `descendants(conn, node_id, kinds=None, max_depth=10, at_story_order=None)`：新增可选 `at_story_order`——过滤边 `valid_from/valid_until` 时效（None 或 ≤ at ≤ 有效期）；`kinds` 消费（边 kind 白名单）。默认行为不变（kinds=None 全部边、无时效过滤）——向后兼容。
- 三处死亡判定换用 deathbeat 助手；state_at/_alive/snowflake dead 语义不变（active=1 校验并入统一助手后，snowflake 的 dead 名单自动获得 L13 口径修正）。

- [ ] **Step 1: 写失败测试**

```python
# tests/consistency/test_deathbeat.py
import json
from snowel_core.storage import db, deathbeat, events, projector


def _confirm(conn, facts):
    with db.transaction(conn):
        events.append_event(conn, "proposal_confirmed",
                            {"artifact_type": "t", "facts": facts})
    projector.apply(conn)


def _seed(conn):
    _confirm(conn, [
        {"fact": "node", "id": "hero", "types": ["Character"], "name": "林晚",
         "props": {"core": {"death_beat": "mb9"}}},
        {"fact": "node", "id": "mb1", "types": ["MicroBeat"], "name": "早拍",
         "props": {"address": {"volume": 1, "chapter": 1, "scene": 1, "beat": 1}}},
        {"fact": "node", "id": "mb9", "types": ["MicroBeat"], "name": "死亡拍",
         "props": {"address": {"volume": 1, "chapter": 9, "scene": 1, "beat": 1}}},
    ])


def test_deathbeat_helpers(core_conn):
    _seed(core_conn)
    hero = deathbeat.dead_at(core_conn, core_conn.execute(
        "SELECT * FROM nodes WHERE id='hero'").fetchone())
    assert hero == 1                                   # mb1 序 0、mb9 序 1
    assert deathbeat.is_dead(core_conn, _row(core_conn, "hero"), 0) is False
    assert deathbeat.is_dead(core_conn, _row(core_conn, "hero"), 1) is True
    assert deathbeat.is_dead(core_conn, _row(core_conn, "mb1"), 5) is None


def _row(conn, nid):
    return conn.execute("SELECT * FROM nodes WHERE id=?", (nid,)).fetchone()


def test_deathbeat_requires_active_beat(core_conn):  # L13：死亡拍停用→保守存活
    _seed(core_conn)
    with db.transaction(core_conn):
        events.append_event(core_conn, "retraction",
                            {"target": "node", "target_id": "mb9"})
    projector.apply(core_conn)
    assert deathbeat.is_dead(core_conn, _row(core_conn, "hero"), 99) is False
    assert deathbeat.dead_at(core_conn, _row(core_conn, "hero")) is None
```

```python
# tests/storage/test_queries.py 追加
def test_descendants_kinds_and_validity(core_conn):  # L4
    _confirm(core_conn, [
        {"fact": "node", "id": "n1", "types": ["Concept"], "name": "a", "props": {}},
        {"fact": "node", "id": "n2", "types": ["Mechanism"], "name": "b", "props": {}},
        {"fact": "node", "id": "n3", "types": ["Concept"], "name": "c", "props": {}},
        {"fact": "edge", "id": "e1", "src": "n1", "dst": "n2", "kind": "REQUIRES",
         "props": {"valid_from_beat": "mb1", "valid_until_beat": "mb2"}},
        {"fact": "edge", "id": "e2", "src": "n1", "dst": "n3", "kind": "IS_A",
         "props": {}},
        {"fact": "node", "id": "mb1", "types": ["MicroBeat"], "name": "x",
         "props": {"address": {"volume": 1, "chapter": 1, "scene": 1, "beat": 1}}},
        {"fact": "node", "id": "mb2", "types": ["MicroBeat"], "name": "y",
         "props": {"address": {"volume": 1, "chapter": 2, "scene": 1, "beat": 1}}},
    ])
    # kinds 过滤
    got = {r["id"] for r in queries.descendants(core_conn, "n1", kinds=["REQUIRES"])}
    assert got == {"n2"}
    # 时效过滤：e1 有效期 [0,1]，at=5 过期；e2 恒有效
    got2 = {r["id"] for r in queries.descendants(
        core_conn, "n1", at_story_order=5)}
    assert got2 == {"n3"}
    got3 = {r["id"] for r in queries.descendants(
        core_conn, "n1", at_story_order=1)}
    assert got3 == {"n2", "n3"}
    # 默认行为不变
    assert len(queries.descendants(core_conn, "n1")) == 2
```

- [ ] **Step 2: 跑测试确认失败**
- [ ] **Step 3: 最小实现**

```python
# src/snowel_core/storage/deathbeat.py
import json
import sqlite3


def dead_at(conn: sqlite3.Connection, node_row) -> int | None:
    """死亡拍 story_order；death_beat 缺失或死亡拍停用/无序 → None（L13 统一口径）。"""
    props = json.loads(node_row["props"])
    beat = props.get("core", {}).get("death_beat")
    if beat is None:
        return None
    row = conn.execute("SELECT story_order, active FROM nodes WHERE id=?",
                       (beat,)).fetchone()
    if row is None or not row["active"] or row["story_order"] is None:
        return None
    return row["story_order"]


def is_dead(conn: sqlite3.Connection, node_row, story_order: int):
    """True=已死；False=存活（含保守存活）；None=未设死点。"""
    d = dead_at(conn, node_row)
    if d is None:
        beat = json.loads(node_row["props"]).get("core", {}).get("death_beat")
        return None if beat is None else False
    return d <= story_order
```

descendants 改造（kinds 消费 + 时效过滤）：

```python
def descendants(conn, node_id: str, kinds: list[str] | None = None,
                max_depth: int = 10, at_story_order: int | None = None) -> list:
    sql = """
        WITH RECURSIVE walk(id, depth) AS (
            SELECT dst, 1 FROM edges WHERE src=?
            UNION
            SELECT e.dst, walk.depth+1 FROM edges e
            JOIN walk ON e.src = walk.id WHERE walk.depth < ?
        )
        SELECT DISTINCT n.* FROM walk JOIN nodes n ON n.id = walk.id
        WHERE n.active=1 AND n.id != ?
    """
    rows = [r for r in conn.execute(sql, (node_id, max_depth, node_id))]
    if kinds is not None and at_story_order is None:
        return _filter_kinds(conn, rows, set(kinds))
    if at_story_order is not None:
        return _walk_filtered(conn, node_id, max_depth, set(kinds or []),
                              at_story_order)
    return rows
```

（实现时以最简正确为准：kinds+时效组合下建议直接在递归 CTE 的两个锚点/递归臂上加 `kind IN` 与有效期谓词 `AND (valid_from IS NULL OR valid_from <= ?) AND (valid_until IS NULL OR valid_until >= ?)`——执行者可整体重写该函数，接口契约以测试为准。）

state_at / context._alive / snowflake dead 三处死亡分支改调 deathbeat（`json.loads` props 后判定 → `is_dead`/`dead_at`），语义断言由既有测试守卫。

- [ ] **Step 4: 跑测试通过**：`pytest tests/consistency tests/storage tests/retrieval tests/flow -v`
- [ ] **Step 5: 提交**：`git commit -m "feat(consistency): deathbeat helper unification (L13) and descendants kinds/validity (L4)"`

---

### Task 2: consistency 引擎骨架（Violation/Rule/registry/run 两档）

**Files:**
- Create: `src/snowel_core/consistency/__init__.py`、`src/snowel_core/consistency/engine.py`
- Test: `tests/consistency/test_engine.py`

**Interfaces:**
- Consumes: 无（纯新增）。
- Produces:
  - `Violation = dict`：`{"level": "major"|"minor", "rule": str, "message": str, "refs": [节点/边 id]}`。
  - `Rule` 协议（鸭子类型，注册表存函数）：`rule(change: dict, conn) -> list[Violation]`；`change` = `{"kind": "node"|"edge"|"track"|"retraction", "fact": {...}, "seq": int}`（变更集元素）。
  - `engine.TIERS = {"light": {...规则名...}, "full": {...}}`；`engine.register(name, fn, tiers=("full",))`（扩展包注册接口预留）；`engine.run(conn, changes: list[dict], tier: str) -> list[Violation]`——按档位跑注册规则，聚合去重（同 rule+refs）。
  - `engine.diff_proposal(conn, violations, source_seq) -> str | None`：把 major 矛盾类 Violation 组装为 `cascade_revision` 提案（P1 契约：`{"conflicts": [{"node_id","key","old","new","refs"}], "source_change_seq"}`），入队返回 pid，无 major 返回 None。

- [ ] **Step 1: 写失败测试**

```python
# tests/consistency/test_engine.py
from snowel_core.consistency import engine


def test_run_aggregates_and_dedupes(core_conn):
    seen = []

    def rule_a(change, conn):
        seen.append(change["kind"])
        return [{"level": "minor", "rule": "a", "message": "m",
                 "refs": [change["fact"].get("id", "?")] * 1}]

    def rule_b(change, conn):
        return [{"level": "major", "rule": "b", "message": "m", "refs": ["x"]}]

    engine.register("test_a", rule_a, tiers=("full", "light"))
    engine.register("test_b", rule_b, tiers=("full",))
    vs = engine.run(core_conn, [
        {"kind": "node", "fact": {"id": "n1"}, "seq": 1},
        {"kind": "node", "fact": {"id": "n1"}, "seq": 2}], "light")
    assert {v["rule"] for v in vs} == {"a"}          # light 不含 b
    vs2 = engine.run(core_conn, [
        {"kind": "node", "fact": {"id": "n1"}, "seq": 3}], "full")
    assert {v["rule"] for v in vs2} == {"a", "b"}


def test_diff_proposal_creates_cascade_revision(api, core_conn):
    pid = engine.diff_proposal(core_conn, [
        {"level": "major", "rule": "contradiction", "message": "等级冲突",
         "refs": ["m1"], "detail": {"node_id": "m1", "key": "mechanism_level",
                                     "old": 3, "new": 5}}], source_seq=9)
    row = api.proposals.get(pid)
    assert row["kind"] == "cascade_revision"
    import json
    p = json.loads(row["payload"])
    assert p["conflicts"][0]["old"] == 3 and p["source_change_seq"] == 9
    assert engine.diff_proposal(core_conn, [], source_seq=1) is None
```

- [ ] **Step 2: 跑测试确认失败**
- [ ] **Step 3: 最小实现**（registry dict + tier 过滤 + refs 去重键；diff_proposal 过滤 level=="major" 且带 detail 的矛盾项）
- [ ] **Step 4: 跑测试通过**
- [ ] **Step 5: 提交**：`git commit -m "feat(consistency): rule engine skeleton with tiers and diff-proposal output (E5)"`

---

### Task 3: 内置规则集 A——矛盾检测（集合一致性，TC-CC-01）

**Files:**
- Create: `src/snowel_core/consistency/rules.py`
- Test: `tests/consistency/test_rules_contradiction.py`

**Interfaces:**
- Consumes: Task 2 引擎；`queries.state_at`（当前生效集）。
- Produces:
  - `rules.contradiction(change, conn)`：变更 fact 为 node 且 props 含标量数值/等级类字段（扁平键如 `mechanism_level`、`core_level`）时，取当前生效集（state_at 头部）同节点同扁平键的**不同值** → Violation(major, rule="contradiction", detail={node_id, key, old, new}, refs=[node_id])。值相同或键缺失 → 无。注意 state_at 的 flatten 只展开 dict 组值——规则侧同法扁平化变更 fact 的 props 后比对。
  - 注册进两档（light+full）。
- TC-CC-01 断言面：确认"M 等级=5"时当前生效"M 等级=3" → 矛盾命中 + diff 修订提案产出 + **不自动改、不阻断入库**（事件照常落，节点照常 upsert）。

- [ ] **Step 1: 写失败测试**

```python
# tests/consistency/test_rules_contradiction.py
from snowel_core.consistency import engine, rules
from snowel_core.storage import db, events, projector

engine.register("contradiction", rules.contradiction, tiers=("full", "light"))


def _seed_level(conn, level):
    with db.transaction(conn):
        events.append_event(conn, "proposal_confirmed", {
            "artifact_type": "t", "facts": [
                {"fact": "node", "id": "m1", "types": ["Mechanism"],
                 "name": "积分兑换", "props": {"mechanism": {"level": level}}}]})
    projector.apply(conn)


def test_contradiction_detected_and_diff_proposed(api, core_conn):  # TC-CC-01
    _seed_level(core_conn, 3)
    changes = [{"kind": "node", "seq": 2, "fact": {
        "id": "m1", "types": ["Mechanism"], "name": "积分兑换",
        "props": {"mechanism": {"level": 5}}}}]
    vs = engine.run(core_conn, changes, "full")
    hit = [v for v in vs if v["rule"] == "contradiction"]
    assert hit and hit[0]["level"] == "major"
    assert hit[0]["detail"] == {"node_id": "m1", "key": "mechanism_level",
                                "old": 3, "new": 5}
    pid = engine.diff_proposal(core_conn, hit, source_seq=2)
    assert pid is not None                                   # diff 修订提案
    # 主流程不阻断：确认照常入库
    seq = api.confirm(api.proposals.create("t", {"facts": [
        {"fact": "node", "id": "m1", "types": ["Mechanism"],
         "name": "积分兑换", "props": {"mechanism": {"level": 5}}}] }))
    assert seq > 0 and api.get_node("m1") is not None


def test_contradiction_clean_when_same_value(core_conn):
    _seed_level(core_conn, 3)
    vs = engine.run(core_conn, [{"kind": "node", "seq": 3, "fact": {
        "id": "m1", "types": ["Mechanism"], "name": "积分兑换",
        "props": {"mechanism": {"level": 3}}}}], "full")
    assert not [v for v in vs if v["rule"] == "contradiction"]
```

- [ ] **Step 2: 跑测试确认失败**
- [ ] **Step 3: 最小实现**（扁平化比对仅限标量值；old 取当前生效集——用 `state_at(conn, 10**9)` 或直接读节点表当前值，以测试期望为准：直接读物化当前值最简且语义同为"当前生效版"）
- [ ] **Step 4: 跑测试通过**
- [ ] **Step 5: 提交**：`git commit -m "feat(consistency): contradiction rule with diff proposal (TC-CC-01)"`

---

### Task 4: 内置规则集 B——依赖检测（引用反查，TC-CC-02）

**Files:**
- Modify: `src/snowel_core/consistency/rules.py`
- Test: `tests/consistency/test_rules_dependency.py`

**Interfaces:**
- Consumes: `queries.edges_of`、`storage.fts.search`（正文段落引用）、mirror 表。
- Produces:
  - `rules.dependents(change, conn)`：变更 fact 为 node 时——①边反查：所有指向该节点的边（IS_A/REQUIRES/EXPLOITS 等，含对端节点名）→ Violation(minor, rule="dependents", refs=[边 id + 对端 id], message 列对端)；②正文引用：`fts.search(conn, 节点名)` 命中段落 → 并入 message 提示（refs 加 `chapter:para` 形式字符串）。变更 fact 为 edge 时反查 src/dst 两端。无引用 → 无 Violation。
  - 注册进两档（light+full）。
- TC-CC-02 断言面：拍 50 处正文/设定引用机制 M，对 M 提 retcon → 依赖检测反查命中边与正文段落引用，影响清单呈现。

- [ ] **Step 1: 写失败测试**

```python
# tests/consistency/test_rules_dependency.py
import json
from snowel_core.consistency import engine, rules
from snowel_core.storage import db, events, projector
from snowel_core.writeback import mirror

engine.register("dependents", rules.dependents, tiers=("full", "light"))


def _seed(core_conn, tmp_path):
    with db.transaction(core_conn):
        events.append_event(core_conn, "proposal_confirmed", {
            "artifact_type": "t", "facts": [
                {"fact": "node", "id": "sys", "types": ["Concept"],
                 "name": "轮回游戏", "props": {}},
                {"fact": "node", "id": "m1", "types": ["Mechanism"],
                 "name": "积分兑换", "props": {}},
                {"fact": "edge", "id": "e1", "src": "sys", "dst": "m1",
                 "kind": "REQUIRES", "props": {}}]})
    projector.apply(core_conn)
    mirror.write_prose(core_conn, tmp_path, "ch50", "系统面板亮起：积分兑换可用。")


def test_dependents_edges_and_prose(api, core_conn, tmp_path):  # TC-CC-02
    _seed(core_conn, tmp_path)
    vs = engine.run(core_conn, [{"kind": "node", "seq": 2, "fact": {
        "id": "m1", "types": ["Mechanism"], "name": "积分兑换",
        "props": {"level": 9}}}], "full")
    dep = [v for v in vs if v["rule"] == "dependents"]
    assert dep and dep[0]["level"] == "minor"
    assert "e1" in dep[0]["refs"] and "sys" in dep[0]["refs"]   # 边反查
    assert any(r.startswith("ch50:") for r in dep[0]["refs"])    # 正文段落引用
    assert "轮回游戏" in dep[0]["message"]                       # 对端提示
```

- [ ] **Step 2: 跑测试确认失败**
- [ ] **Step 3: 最小实现**（fts.search 段落 → refs "chapter:para_idx"；一条聚合 Violation 即可，不逐段一条）
- [ ] **Step 4: 跑测试通过**
- [ ] **Step 5: 提交**：`git commit -m "feat(consistency): dependents rule with edge and prose reference lookup (TC-CC-02)"`

---

### Task 5: 内置规则集 C——区间检测 + growth_curve 护栏 + 轨道棘轮（TC-CC-03/04、TC-ON-16、TC-ON-10 后半）

**Files:**
- Modify: `src/snowel_core/consistency/rules.py`
- Test: `tests/consistency/test_rules_interval.py`

**Interfaces:**
- Consumes: edges 物化 valid_from/valid_until；props 的 growth_curve；tracks.frozen。
- Produces:
  - `rules.interval_overlap(change, conn)`：变更 fact 为 edge 且带 valid_from_beat/valid_until_beat 时，换算 story_order（查拍节点序）后，与同 (src,dst,kind) 既有边的有效期比对重叠 → Violation(minor, rule="interval_overlap", refs=[两边 id])。空洞检测 v1 简化为：同对端既有边全部失效（valid_until 非空且 < 新 valid_from）且其间无其他边 → 不报（空洞属"提示级"，v1 只做重叠）。注册 full。
  - `rules.growth_guardrail(change, conn)`：变更 node props 的 `mechanism.growth_curve` 值为 "exponential"（或含 "指数"）→ Violation(minor, rule="growth_guardrail", message="指数增长护栏警告（Layer 1）", refs=[node_id])——**警告不阻断**（TC-ON-16）。注册 full。
  - `rules.track_ratchet(change, conn)`：变更 kind=="track"（定义修改，仅 retcon 路径产生——见 Task 8）且该 track frozen=1 且 definition 与现存不同 → Violation(major, rule="track_ratchet", message="轨道已冻结，修改须走显式 retcon（本检查即 retcon 全量档的一部分）", refs=[track_id])。注册 full。（普通路径无改轨入口——P3；此规则为 retcon 全量分析与未来扩展口守门。）注册 full。
- TC-CC-03/04 断言面：区间冲突变更 → 检测命中提示；任意变更集 → 三类检查统一跑（语义等价，"向前/向后"只是性能裁剪不实现）。

- [ ] **Step 1: 写失败测试**

```python
# tests/consistency/test_rules_interval.py
from snowel_core.consistency import engine, rules
from snowel_core.storage import db, events, projector

engine.register("interval_overlap", rules.interval_overlap, tiers=("full",))
engine.register("growth_guardrail", rules.growth_guardrail, tiers=("full",))
engine.register("track_ratchet", rules.track_ratchet, tiers=("full",))


def _seed(conn):
    with db.transaction(conn):
        events.append_event(conn, "proposal_confirmed", {
            "artifact_type": "t", "facts": [
                {"fact": "node", "id": "a", "types": ["Character"], "name": "a",
                 "props": {}},
                {"fact": "node", "id": "b", "types": ["Concept"], "name": "b",
                 "props": {}},
                {"fact": "node", "id": "mb1", "types": ["MicroBeat"], "name": "1",
                 "props": {"address": {"volume": 1, "chapter": 1, "scene": 1,
                                       "beat": 1}}},
                {"fact": "node", "id": "mb5", "types": ["MicroBeat"], "name": "5",
                 "props": {"address": {"volume": 1, "chapter": 5, "scene": 1,
                                       "beat": 1}}},
                {"fact": "node", "id": "mb9", "types": ["MicroBeat"], "name": "9",
                 "props": {"address": {"volume": 1, "chapter": 9, "scene": 1,
                                       "beat": 1}}},
                {"fact": "edge", "id": "old1", "src": "a", "dst": "b",
                 "kind": "PARTICIPATES",
                 "props": {"valid_from_beat": "mb1", "valid_until_beat": "mb5"}}]})
    projector.apply(conn)


def test_interval_overlap_detected(core_conn):  # TC-CC-03
    _seed(core_conn)
    vs = engine.run(core_conn, [{"kind": "edge", "seq": 2, "fact": {
        "id": "new1", "src": "a", "dst": "b", "kind": "PARTICIPATES",
        "props": {"valid_from_beat": "mb5", "valid_until_beat": "mb9"}}}],
        "full")
    hit = [v for v in vs if v["rule"] == "interval_overlap"]
    assert hit and "old1" in hit[0]["refs"] and "new1" in hit[0]["refs"]


def test_growth_guardrail_warns_not_blocks(core_conn):  # TC-ON-16
    vs = engine.run(core_conn, [{"kind": "node", "seq": 1, "fact": {
        "id": "g1", "types": ["Mechanism"], "name": "成长机制",
        "props": {"mechanism": {"growth_curve": "exponential"}}}}], "full")
    hit = [v for v in vs if v["rule"] == "growth_guardrail"]
    assert hit and hit[0]["level"] == "minor"      # 警告不阻断


def test_track_ratchet_frozen(core_conn):  # TC-ON-10 后半
    with db.transaction(core_conn):
        events.append_event(core_conn, "track_added", {
            "track_id": "t1", "name": "现实轨", "definition": {"流速": 1}})
        events.append_event(core_conn, "track_frozen", {"track_id": "t1"})
    projector.apply(core_conn)
    vs = engine.run(core_conn, [{"kind": "track", "seq": 3, "fact": {
        "track_id": "t1", "definition": {"流速": 2}}}], "full")
    hit = [v for v in vs if v["rule"] == "track_ratchet"]
    assert hit and hit[0]["level"] == "major"
    clean = engine.run(core_conn, [{"kind": "track", "seq": 4, "fact": {
        "track_id": "t2", "definition": {"流速": 1}}}], "full")
    assert not [v for v in clean if v["rule"] == "track_ratchet"]  # 未冻结不管
```

- [ ] **Step 2: 跑测试确认失败**
- [ ] **Step 3: 最小实现**（重叠判定：新区间 [f',u'] 与既有 [f,u] 交叠 = f' ≤ u 且 f ≤ u'（None 视为 ±∞）；拍地址→story_order 查节点表）
- [ ] **Step 4: 跑测试通过**
- [ ] **Step 5: 提交**：`git commit -m "feat(consistency): interval overlap, growth guardrail and track ratchet rules (TC-CC-03/04, TC-ON-16, TC-ON-10)"`

---

### Task 6: 四写入点接线（confirm 全量 / auto 轻量 / retraction 轻量，TC-CC-04）

**Files:**
- Modify: `src/snowel_core/api.py`（confirm 接线 + extract 接线 + cascade_check 门面）、`src/snowel_core/writeback/extract.py`、`src/snowel_core/writeback/review.py`
- Create: `src/snowel_core/consistency/wiring.py`（接线助手：变更集构造 + 跑档 + diff 提案）
- Test: `tests/consistency/test_wiring.py`

**Interfaces:**
- Consumes: Task 2–5 引擎与规则；api.confirm/extract/reject_auto 既有流程。
- Produces:
  - `wiring.change_set_from_facts(facts, seq) -> list[dict]`；`wiring.after_commit(conn, facts, seq, tier) -> dict`——跑对应档位 + major 矛盾产 diff 提案，返回 `{"violations": [...], "cascade_proposal_id": str | None}`（P1/P2 契约）。
  - **api.confirm**（proposal_confirmed 事务后）：`if payload facts 非空` → `after_commit(conn, facts, seq, "full")`；confirm 返回值不变（int seq），级联结果写进 `retrieval_audit`？不——级联结果进 **返回 dict？** 保持 int（E2 既有契约）：级联结果通过 `api.last_cascade() -> dict`（实例属性缓存最近一次 confirm 的级联结果）暴露；MCP confirm 响应增补 `"cascade": {...}` 键（壳任务接线）。**revision/retcon 提案不走此处**（retcon 有专属流程 Task 8；revision 的 kind 过滤跳过级联）。
  - **extract**（auto_canonized 事务后）：结果 dict 增 `"cascade": after_commit(conn, low, seq, "light")`（轻量，仅当 low 非空）。
  - **reject_auto**（retraction 事务后）：返回 dict 增 `"cascade": after_commit(conn, retraction 变更集, seq, "light")`（变更集元素 kind="retraction"——依赖反查按被撤目标跑；矛盾检测对 retraction 跳过）。
  - `api.cascade_check(facts, tier="full") -> dict`：独立只读门面（Web/advanced 预演用），跑档返回 Violations + diff 预览（不入队）。
- TC-CC-04 断言面：任意变更集提交 → 三类检查统一全跑（"向前/向后"仅性能裁剪不影响检出——接线层对所有 facts 统一跑全档/轻档即满足）。

- [ ] **Step 1: 写失败测试**

```python
# tests/consistency/test_wiring.py
import json
from snowel_core.consistency import wiring
from snowel_core.storage import db, events, projector
from snowel_core.writeback import mirror


def _seed_level(conn, level=3):
    with db.transaction(conn):
        events.append_event(conn, "proposal_confirmed", {
            "artifact_type": "t", "facts": [
                {"fact": "node", "id": "m1", "types": ["Mechanism"],
                 "name": "积分兑换", "props": {"mechanism": {"level": level}}}]})
    projector.apply(conn)


def test_confirm_runs_full_cascade(api):  # TC-CC-01/04 接线面
    _seed_level(api._conn)
    pid = api.proposals.create("t", {"facts": [
        {"fact": "node", "id": "m1", "types": ["Mechanism"],
         "name": "积分兑换", "props": {"mechanism": {"level": 5}}}]})
    seq = api.confirm(pid)
    assert seq > 0
    last = api.last_cascade()
    assert last["tier"] == "full"
    assert any(v["rule"] == "contradiction" for v in last["violations"])
    assert last["cascade_proposal_id"] is not None      # diff 修订提案已入队


def test_extract_runs_light_cascade(api, tmp_path):  # auto 入典轻量
    mirror.write_prose(api._conn, tmp_path, "ch1", "林晚攒积分。")
    resp = json.dumps({"facts": [
        {"sensitivity": "low", "fact": {
            "fact": "node", "id": "m2", "types": ["Mechanism"],
            "name": "新机制", "props": {}}}], "appeared": []},
        ensure_ascii=False)
    from tests.conftest import FakeBackend
    r = api.extract_and_writeback("ch1", backend=FakeBackend([resp]))
    assert r["cascade"]["tier"] == "light"
    assert isinstance(r["cascade"]["violations"], list)


def test_cascade_check_readonly_preview(api):  # 独立预演门面
    _seed_level(api._conn)
    out = api.cascade_check([
        {"fact": "node", "id": "m1", "types": ["Mechanism"], "name": "积分兑换",
         "props": {"mechanism": {"level": 7}}}])
    assert any(v["rule"] == "contradiction" for v in out["violations"])
    assert len(api.proposals.list("pending")) == 0     # 预演不入队
```

- [ ] **Step 2: 跑测试确认失败**
- [ ] **Step 3: 最小实现**（after_commit 内部 import rules 注册——注意 Task 3–5 测试里已手动 register，wiring 内统一注册全部内置规则一次，幂等；api 实例加 `self._last_cascade = None`）
- [ ] **Step 4: 跑测试通过**：`pytest tests/consistency tests/writeback tests/flow -v`
- [ ] **Step 5: 提交**：`git commit -m "feat(consistency): wire full tier at confirm, light tier at auto-canonize/retraction, preview facade (E5 four write points)"`

---

### Task 7: 冻结线与封卷（TC-CC-05/06/08、WB-08 后半）

**Files:**
- Create: `src/snowel_core/consistency/seal.py`
- Modify: `src/snowel_core/storage/projector.py`（volume_sealed 物化 + 表）、`src/snowel_core/storage/schema.sql`（+sealed_volumes 或复用 tracks 式表）、`src/snowel_core/api.py`（seal 门面 + 冻结拦截接线 confirm）
- Test: `tests/consistency/test_seal.py`

**Interfaces:**
- Consumes: Volume 节点；事件 `volume_sealed`（§3.2 清单：卷 id、封卷时 seq）。
- Produces:
  - schema：`sealed_volumes(volume_id TEXT PRIMARY KEY, sealed_seq INTEGER NOT NULL)`（物化表）。
  - 投影器：`volume_sealed` handler → INSERT sealed_volumes。
  - `seal.seal_volume(conn, volume_id) -> int`：校验 Volume 节点存在且未封 → 事务追加 `volume_sealed` + apply → 返回 seq。已封 → ValueError。
  - **冻结拦截**：`seal.is_sealed(conn, node_id) -> bool`——节点归属卷（节点 address.volume 编号 → 对应 Volume 节点 → 查 sealed_volumes；无 address/无卷 → False）。api.confirm 事务前：变更 facts 中任一 node 且 `is_sealed` → raise `SealedVolumeError`（新异常，文案"卷 {v} 已封卷，设定改动须走显式 retcon"）——**普通确认被拦，retcon 流程豁免**（Task 8 的确认路径不走此拦截）。auto 入典（extract）同样拦截（低敏感自动入典不得穿透冻结线）；**retraction 豁免**（C11：auto 否决不受冻结线约束——既有语义，WB-08）。
  - `api.seal(volume_id)` 门面；未封卷警告（TC-CC-05：卷 2 未封卷在卷 4 写作仅警告不阻断——表现为不拦截 + flow_state 可见未封卷集合；警告面留给壳/Web 展示，core 提供 `api.sealed_volumes() -> list`）。
- TC-CC-05/06/08/WB-08 断言面：未封卷不拦；已封卷直接改设定被拦（提示 retcon）；seal 命令追加事件且三端可见；已封卷下 auto 否决仍可执行。

- [ ] **Step 1: 写失败测试**

```python
# tests/consistency/test_seal.py
import json
import pytest
from snowel_core.consistency import seal as seal_mod
from snowel_core.storage import db, events, projector
from snowel_core.writeback import mirror


def _seed_two_volumes(api):
    with db.transaction(api._conn):
        events.append_event(api._conn, "proposal_confirmed", {
            "artifact_type": "t", "facts": [
                {"fact": "node", "id": "v1", "types": ["Volume"], "name": "卷一",
                 "props": {"address": {"volume": 1, "chapter": 0, "scene": 0,
                                       "beat": 0}}},
                {"fact": "node", "id": "v2", "types": ["Volume"], "name": "卷二",
                 "props": {"address": {"volume": 2, "chapter": 0, "scene": 0,
                                       "beat": 0}}},
                {"fact": "node", "id": "m1", "types": ["Mechanism"],
                 "name": "积分兑换", "props": {}},
                {"fact": "node", "id": "c3", "types": ["Chapter"], "name": "第3章",
                 "props": {"address": {"volume": 1, "chapter": 3, "scene": 0,
                                       "beat": 0}}}]})
    projector.apply(api._conn)


def test_seal_and_freeze_line(api):  # TC-CC-06/08
    _seed_two_volumes(api)
    assert api.seal("v1") > 0
    ev = api._conn.execute(
        "SELECT payload FROM events WHERE kind='volume_sealed'").fetchone()
    assert json.loads(ev["payload"]) == {"volume_id": "v1"}
    # 卷一内设定（m1 挂 address.volume=1 后被拦；此处用 c3 章节——补 address）
    pid = api.proposals.create("t", {"facts": [
        {"fact": "node", "id": "m1", "types": ["Mechanism"], "name": "积分兑换",
         "props": {"address": {"volume": 1, "chapter": 0, "scene": 0,
                               "beat": 0}, "mechanism": {"level": 9}}}]})
    with pytest.raises(Exception, match="封卷"):
        api.confirm(pid)                                  # 冻结线拦截
    with pytest.raises(ValueError, match="已封"):
        api.seal("v1")                                    # 重复封卷拒绝


def test_unsealed_volume_not_blocked(api):  # TC-CC-05
    _seed_two_volumes(api)
    pid = api.proposals.create("t", {"facts": [
        {"fact": "node", "id": "m1", "types": ["Mechanism"], "name": "积分兑换",
         "props": {"address": {"volume": 2, "chapter": 0, "scene": 0,
                               "beat": 0}, "mechanism": {"level": 9}}}]})
    assert api.confirm(pid) > 0                           # 卷二未封，不拦


def test_auto_retraction_ignores_freeze(api, tmp_path):  # TC-WB-08 后半
    _seed_two_volumes(api)
    pid = api.proposals.create("t", {"facts": [
        {"fact": "node", "id": "m1", "types": ["Mechanism"],
         "name": "一命换积分",
         "props": {"address": {"volume": 1, "chapter": 0, "scene": 0,
                               "beat": 0}}}]})
    api.confirm(pid)
    api.seal("v1")
    from snowel_core.writeback import review
    r = review.reject_auto(api._conn, [("node", "m1")])  # C11：否决不受冻结线
    assert r["retracted"] == 1
```

- [ ] **Step 2: 跑测试确认失败**
- [ ] **Step 3: 最小实现**（is_sealed：节点 address.volume → Volume 节点（props.address.volume 同号）→ sealed_volumes 查询；extract 的 auto 分支在事务前对 low facts 做同样拦截）
- [ ] **Step 4: 跑测试通过**
- [ ] **Step 5: 提交**：`git commit -m "feat(consistency): volume seal with freeze-line interception, retraction exempt (C7/C11, TC-CC-05/06/08)"`

---

### Task 8: retcon 流程（TC-CC-07、C5 retcon 面 + 依赖图精确 stale + L14）

**Files:**
- Create: `src/snowel_core/consistency/retcon.py`
- Modify: `src/snowel_core/storage/projector.py`（retcon_applied 扩展 track_updates）、`src/snowel_core/api.py`（propose_retcon/confirm_retcon 门面 + revision 分支的 stale 切精确版）
- Test: `tests/consistency/test_retcon.py`

**Interfaces:**
- Consumes: Task 6 接线（全量档）；Task 7 冻结线（retcon 豁免拦截）。
- Produces:
  - `retcon.propose_retcon(api, facts=None, renames=None, track_updates=None, reason="") -> dict`——**不走提案队列的普通 kind**，而是创建 `kind="retcon"` 提案，payload `{facts, renames, track_updates, reason, impact}`；**创建时跑全量级联**（P5）：changes = facts + renames 对端节点 + track_updates → `engine.run(full)`；影响清单 `impact = {"violations": [...], "affected_proposals": [pid...]}`（依赖图精确分析 P4：变更触及节点 id 集 ∩ pending 提案 payload json 含该 id）。返回 `{proposal_id, impact}`。
  - `api.confirm_retcon(proposal_id) -> int`：仅 kind=="retcon"；事务追加 `retcon_applied`（payload：renames + track_updates）+ `proposal_confirmed`？——**事件序**：retcon 确认落一条 `retcon_applied` 事件（含 facts？§3.2 清单 retcon_applied payload=影响清单、旧→新版事实、关联正文提示——facts 的正典更新经 proposal_confirmed 单独事件还是并入？**裁定：confirm_retcon 单事务内两条事件**——`proposal_confirmed`（facts 物化）+ `retcon_applied`（renames/track_updates 物化 + payload 携带 impact 摘要），保 D1 检查点一致性）；事务后 C5 精确 stale（L14：`with db.transaction` 批量 UPDATE proposals + 逐条 stale_marked 事件）。返回 proposal_confirmed seq。
  - 投影器 `retcon_applied` 扩展：`track_updates` → `UPDATE tracks SET definition=? WHERE id=?`（P3；frozen 保持——retcon 即合法改轨路径，棘轮规则在全量档已提示过作者）。
  - api.confirm 的 revision 分支 stale 切换为 P4 精确版（同助手）。
  - 冻结线豁免：confirm_retcon 不做 is_sealed 拦截（retcon 本身就是冻结线的合法通道，TC-CC-06/07）。
- TC-CC-07 断言面：走完整 retcon 流程确认 → retcon_applied 事件（影响清单、旧→新、正文提示）+ 物化更新 + 旧正文仅提示不自动改（C9 面）。

- [ ] **Step 1: 写失败测试**

```python
# tests/consistency/test_retcon.py
import json
from snowel_core.consistency import retcon
from snowel_core.storage import db, events, projector
from snowel_core.writeback import mirror


def _seed(api, tmp_path):
    with db.transaction(api._conn):
        events.append_event(api._conn, "proposal_confirmed", {
            "artifact_type": "t", "facts": [
                {"fact": "node", "id": "m1", "types": ["Mechanism"],
                 "name": "积分兑换",
                 "props": {"mechanism": {"level": 3}}},
                {"fact": "node", "id": "sys", "types": ["Concept"],
                 "name": "轮回游戏", "props": {}},
                {"fact": "edge", "id": "e1", "src": "sys", "dst": "m1",
                 "kind": "REQUIRES", "props": {}}]})
        projector.apply(api._conn)
    mirror.write_prose(api._conn, tmp_path, "ch50", "积分兑换面板亮起。")


def test_retcon_flow_with_impact_and_precise_stale(api, tmp_path):  # TC-CC-07/C5
    _seed(api, tmp_path)
    other = api.proposals.create("scene", {
        "draft": "无关提案", "facts": [],
        "mention": {"unrelated": "x"}})                 # 不引用 m1 → 不标
    touched = api.proposals.create("scene", {
        "draft": "涉及积分兑换的提案", "facts": [],
        "mention": {"m1": "引用"}})                     # 引用 m1 → 标 stale
    out = retcon.propose_retcon(
        api, facts=[{"fact": "node", "id": "m1", "types": ["Mechanism"],
                     "name": "积分兑换",
                     "props": {"mechanism": {"level": 9}}}],
        reason="等级体系重排")
    assert any(v["rule"] == "dependents" for v in out["impact"]["violations"])
    assert out["impact"]["affected_proposals"] == [touched]
    seq = api.confirm_retcon(out["proposal_id"])
    assert seq > 0
    kinds = [r["kind"] for r in api._conn.execute(
        "SELECT kind FROM events ORDER BY seq")]
    assert "retcon_applied" in kinds
    assert json.loads(api.get_node("m1")["props"])["mechanism"]["level"] == 9
    assert api.proposals.get(other)["status"] == "pending"   # 精确 stale
    assert api.proposals.get(touched)["status"] == "stale"


def test_retcon_sealed_volume_and_track_update(api, tmp_path):  # P3 + 冻结豁免
    _seed(api, tmp_path)
    with db.transaction(api._conn):
        events.append_event(api._conn, "proposal_confirmed", {
            "artifact_type": "t", "facts": [
                {"fact": "node", "id": "v1", "types": ["Volume"], "name": "卷一",
                 "props": {"address": {"volume": 1, "chapter": 0, "scene": 0,
                                       "beat": 0}}}]})
        events.append_event(api._conn, "track_added", {
            "track_id": "t1", "name": "现实轨", "definition": {"流速": 1}})
        events.append_event(api._conn, "track_frozen", {"track_id": "t1"})
        projector.apply(api._conn)
    api.seal("v1")
    out = retcon.propose_retcon(api, track_updates=[
        {"track_id": "t1", "definition": {"流速": 2}}], reason="轨则修正")
    hit = [v for v in out["impact"]["violations"] if v["rule"] == "track_ratchet"]
    assert hit                                        # 全量分析提示棘轮
    api.confirm_retcon(out["proposal_id"])            # 冻结线豁免：可确认
    d = json.loads(api._conn.execute(
        "SELECT definition FROM tracks WHERE id='t1'").fetchone()["definition"])
    assert d == {"流速": 2}
```

- [ ] **Step 2: 跑测试确认失败**
- [ ] **Step 3: 最小实现**（P4 助手 `retcon.affected_pending(conn, node_ids) -> [pid]`：pending 提案 payload 字符串包含任一 id；L14：stale 批量在单事务——逐条 stale_marked 事件 + UPDATE）
- [ ] **Step 4: 跑测试通过**
- [ ] **Step 5: 提交**：`git commit -m "feat(consistency): explicit retcon flow with full-tier impact, precise C5 stale (L14) and track updates (TC-CC-07)"`

---

### Task 9: 伏笔注册门面（foreshadow_register，§4.8）

**Files:**
- Create: `src/snowel_core/consistency/foreshadow.py`
- Modify: `src/snowel_core/api.py`（register_foreshadow 门面）
- Test: `tests/consistency/test_foreshadow.py`

**Interfaces:**
- Consumes: proposals 队列（提案范式——铁律 3）。
- Produces:
  - `foreshadow.register(api, name, planted_at, origin="author", payoff_beat=None, note="") -> str`：校验 planted_at 为已有 MicroBeat 节点 id（或 scene/chapter 节点 id——多层定位 D4/§4.8，v1 接受三类节点 id）；`origin ∈ {"author", "ai"}`；创建 `kind="foreshadow"` 提案，payload facts=[Foreshadow 节点（props: {foreshadow: {planted_at, origin, payoff_beat, note}}）]——确认走 api.confirm（级联/冻结线随 confirm 接线自然生效）。返回 pid。
  - `api.register_foreshadow(name, planted_at, origin="author", payoff_beat=None, note="")` 门面。
- TC-ON-14 的 origin:"ai" 语义已由生成环 payload 透传覆盖；本门面补 author 手动注册通道（advanced 面）。

- [ ] **Step 1: 写失败测试**

```python
# tests/consistency/test_foreshadow.py
import json
import pytest
from snowel_core.consistency import foreshadow
from snowel_core.storage import db, events, projector


def _seed_beat(api):
    with db.transaction(api._conn):
        events.append_event(api._conn, "proposal_confirmed", {
            "artifact_type": "t", "facts": [
                {"fact": "node", "id": "mb1", "types": ["MicroBeat"],
                 "name": "开场拍", "props": {
                     "address": {"volume": 1, "chapter": 1, "scene": 1,
                                 "beat": 1}}}]})
    projector.apply(api._conn)


def test_register_foreshadow_author(api):
    _seed_beat(api)
    pid = api.register_foreshadow("怀表", planted_at="mb1", note="第3章回收")
    row = api.proposals.get(pid)
    assert row["kind"] == "foreshadow"
    api.confirm(pid)
    node = api._conn.execute(
        "SELECT props FROM nodes WHERE name='怀表'").fetchone()
    p = json.loads(node["props"])
    assert p["foreshadow"]["planted_at"] == "mb1"
    assert p["foreshadow"]["origin"] == "author"


def test_register_foreshadow_validates(api):
    _seed_beat(api)
    with pytest.raises(ValueError, match="planted_at"):
        api.register_foreshadow("怀表", planted_at="nope")
    with pytest.raises(ValueError, match="origin"):
        api.register_foreshadow("怀表", planted_at="mb1", origin="ghost")
```

- [ ] **Step 2: 跑测试确认失败**
- [ ] **Step 3: 最小实现**
- [ ] **Step 4: 跑测试通过**
- [ ] **Step 5: 提交**：`git commit -m "feat(consistency): foreshadow register facade with origin and planted_at validation (4.8)"`

---

### Task 10: 壳接线（MCP advanced seal/retcon/foreshadow_register + CLI seal + cascade 键）

**Files:**
- Modify: `shell/src/snowel/mcp_server.py`、`shell/src/snowel/cli.py`
- Test: `tests/shell/test_mcp_server.py`、`tests/shell/test_cli.py`（追加）

**Interfaces:**
- Consumes: Task 6–9 门面（seal/propose_retcon/confirm_retcon/register_foreshadow/cascade_check/last_cascade/sealed_volumes）。
- Produces（壳零编排，一比一映射）：
  - **snowel_proposal confirm 响应增补 `"cascade": ctx.api.last_cascade()`**（有 facts 的确认才有值；revision/retcon kind 走各自流程后 last_cascade 同步更新——确认 retcon 也走 api.confirm_retcon？**MCP confirm 动作分派**：kind=="retcon" → confirm_retcon，其余 → api.confirm；壳读 kind 需一次查询——加 `api.proposal_kind(pid) -> str` 只读门面，壳据此分派，仍零领域逻辑）。
  - **snowel_advanced**：`seal`（require_write + `api.seal(params 不适用——advanced op 无参，改为 seal 走 snowel_writeback 风格？advanced op 无参数形态限制：给 build 时的闭包 ctx；**裁决：seal/retcon/foreshadow_register 全部并入 snowel_writeback 的 action 面**（有 params 通道），advanced 目录只登记 `{"wired": True, "via": "snowel_writeback"}`——避免给 advanced 加参数协议）。snowel_writeback 新增 actions：`seal {volume_id}`、`retcon {facts?, renames?, track_updates?, reason}`（propose 返回 proposal_id+impact，作者再走 snowel_proposal confirm）、`foreshadow {name, planted_at, origin?, note?}`。ADVANCED_CATALOG：seal/retcon 改 wired+via 标注；foreshadow_register 同；**op 分派对 wired+via 项返回 `{"wired": True, "via": "snowel_writeback", "hint": "经 snowel_writeback 对应 action 调用"}` 指引**（不再走 _not_wired）。
  - **CLI `seal`**：`snowel seal --project X [VOLUME_ID]`（参数必填）→ `api.seal(volume_id)`；删 PLANNED_IN 的 seal；`_not_wired` 函数若无引用则删。
  - 既有测试翻转：`test_advanced_catalog_and_rebuild` 的 not_wired 断言再收窄（seal/retcon/foreshadow_register 翻 wired）；`test_cli.py::test_seal_still_not_wired` 改为 seal 接线测试（正常封卷 + 重复封卷 exit 1）。

- [ ] **Step 1: 写失败测试**

```python
# tests/shell/test_mcp_server.py 追加
async def test_writeback_seal_and_retcon_wired(project, tmp_path):
    api = SnowelAPI.open(project)
    pid = api.proposals.create("t", {"facts": [
        {"fact": "node", "id": "v1", "types": ["Volume"], "name": "卷一",
         "props": {"address": {"volume": 1, "chapter": 0, "scene": 0,
                               "beat": 0}}}]})
    api.confirm(pid)
    api.close()
    async with _connected(project) as (ctx, client):
        w = await _call(client, "snowel_writeback",
                        {"action": "seal", "params": {"volume_id": "v1"}})
        assert w["sealed"] == "v1"
        r = await _call(client, "snowel_writeback", {
            "action": "retcon",
            "params": {"facts": [{"fact": "node", "id": "v1",
                                  "types": ["Volume"], "name": "卷一",
                                  "props": {}}], "reason": "测试"}})
        assert "proposal_id" in r and "impact" in r
        cat = await _call(client, "snowel_advanced", {})
        assert cat["operations"]["seal"]["wired"] is True


async def test_confirm_response_carries_cascade(project):
    api = SnowelAPI.open(project)
    p1 = api.proposals.create("t", {"facts": [
        {"fact": "node", "id": "m1", "types": ["Mechanism"], "name": "M",
         "props": {"mechanism": {"level": 3}}}]})
    api.confirm(p1)
    p2 = api.proposals.create("t", {"facts": [
        {"fact": "node", "id": "m1", "types": ["Mechanism"], "name": "M",
         "props": {"mechanism": {"level": 5}}}]})
    api.close()
    async with _connected(project) as (ctx, client):
        done = await _call(client, "snowel_proposal",
                           {"action": "confirm", "proposal_id": p2})
        assert done["cascade"]["tier"] == "full"
        assert any(v["rule"] == "contradiction"
                   for v in done["cascade"]["violations"])
```

```python
# tests/shell/test_cli.py 追加
def test_seal_command(tmp_path):
    SnowelAPI.init_project(tmp_path)
    api = SnowelAPI.open(tmp_path)
    pid = api.proposals.create("t", {"facts": [
        {"fact": "node", "id": "v1", "types": ["Volume"], "name": "卷一",
         "props": {"address": {"volume": 1, "chapter": 0, "scene": 0,
                               "beat": 0}}}]})
    api.confirm(pid)
    api.close()
    res = runner.invoke(app, ["seal", "--project", str(tmp_path), "v1"])
    assert res.exit_code == 0 and "卷一" in res.output
    res2 = runner.invoke(app, ["seal", "--project", str(tmp_path), "v1"])
    assert res2.exit_code == 1 and "已封" in res2.output
```

- [ ] **Step 2: 跑测试确认失败**
- [ ] **Step 3: 最小实现**（writeback action 分派补 seal/retcon/foreshadow 三支；confirm 分派加 proposal_kind 查询；CLI seal 参数必填）
- [ ] **Step 4: 跑测试通过**：`pytest tests/shell -v`
- [ ] **Step 5: 提交**：`git commit -m "feat(shell): wire seal/retcon/foreshadow via writeback actions, cli seal, cascade in confirm response"`

---

### Task 11: 收尾——tests/README 登记 + 全量回归

**Files:**
- Modify: `tests/README.md`（§1 加 consistency 行）
- Test: 全量

**Interfaces:**
- Produces: README §1 新行：`consistency/`（test_deathbeat/test_engine/test_rules_*/test_wiring/test_seal/test_retcon/test_foreshadow）→ 覆盖 TC-CC-01~08、TC-WB-08、TC-ON-10 后半、TC-ON-16、TC-PR-02 retcon 面。

- [ ] **Step 1: 补 README 行**（沿既有表格风格）
- [ ] **Step 2: 全量回归**：`pytest`（预期 ≥160 + 本计划新增全部通过，0 失败；输出干净）
- [ ] **Step 3: 提交**：`git commit -m "docs: register consistency test directory with black-box reverse index"`

---

## 覆盖矩阵（用例 ↔ 任务）

| 黑盒用例 | 任务 | 备注 |
|---|---|---|
| TC-CC-01 矛盾检测 + diff 提案不阻断 | 3+6 | |
| TC-CC-02 依赖反查（边+正文段落） | 4 | |
| TC-CC-03 区间重叠 | 5 | 空洞检测 v1 不做（提示级留后续） |
| TC-CC-04 三类统一跑 | 6 | 全量/轻量档即语义等价实现 |
| TC-CC-05 未封卷仅警告 | 7 | 警告面=sealed_volumes 查询供壳/Web 展示 |
| TC-CC-06 已封卷拦截走 retcon | 7+8 | |
| TC-CC-07 retcon 完整流程 | 8 | |
| TC-CC-08 seal 命令三端可见 | 7+10 | |
| TC-WB-08 后半（auto 否决不受冻结线） | 7 | 前半已覆盖 |
| TC-ON-10 后半（冻结后修改走 retcon） | 5+8 | 棘轮规则 + retcon 改轨通道 |
| TC-ON-16 growth_curve 护栏 | 5 | |
| TC-PR-02 retcon 触发面 stale | 8 | revision 面前半已覆盖；精确分析统一 |
| L4/L13/L14 | 1/1/8 | 挂账清偿 |

**豁免登记**：区间空洞检测（v1 只做重叠，提示级）；"受影响"语义级依赖图（P4 字符串交集为保守超集）；扩展包规则注册接口（E4 目录式发现未排期，engine.register 预留）；retcon 确认后重跑分析（P5 窗口由 stale 补偿）；setting_gap/mechanism_detail（flow/属性组接线，归 Web 计划或补丁）。

## 执行注意

1. worktree 执行先 `pip install -e . -e ./shell`（无新依赖）。
2. Task 3–5 的测试各自 register 内置规则（幂等）；Task 6 wiring 内统一注册一次全部内置规则——若重复注册行为冲突，engine.register 覆盖式（同 name 后注册覆盖）即可，测试互不污染。
3. Task 1 的 descendants 重写允许整体替换函数体（接口契约以测试为准，注释保留 L4 说明）。
4. 计划缺陷执行期发现：控制器 Ruling 落 ledger 后继续，不停摆。



