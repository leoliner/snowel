# snowel-core 实现计划（v1.0.0 第一阶段：本体 + 事件溯源 + 基础图查询）

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 建成 snowel-core 引擎核心的存储层与本体层：SQLite 单库、append-only 事件日志、投影器物化图、拍号编址与 state_at 历史查询、提案队列、单写者租约、api 门面——支撑 Layer 1/2，不含 LLM 调用。

**Architecture:** 事件日志是唯一真相源；物化图（nodes/edges/alias/tracks/story_order）只能由投影器在追加事件的同一事务内增量应用；api 门面是三端唯一入口。领域动作 = 追加事件 + 投影，一步一事务。

**Tech Stack:** Python 3.12+，sqlite3（标准库，WAL 模式），pydantic v2（属性组 schema），pytest。

**Spec:** `docs/v1.0.0/requirements.md`（C1–C12）、`docs/v1.0.0/design.md`（D1–D8/E1–E5）、`docs/v1.0.0/testcases.md`（用例编号在任务中引用）。

## Global Constraints

- Python >= 3.12；本计划**零第三方运行时依赖 except pydantic**（litellm/sqlite-vec/FTS5 jieba 属后续计划，禁止提前引入）。
- 事件日志 append-only：不提供任何修改/删除已追加事件的代码路径（TC-EV-06）。
- 物化表（nodes/edges/alias/tracks）唯一写入口是 `storage/projector.py`（E2 红线）；其他模块只能追加事件。
- 事件 payload 中结构引用只用稳定 ID（UUIDv7、拍结构地址），不用派生序（D1/§3.3）。
- 领域模块同层不互相 import；storage 不自开事务，事务由调用方以 `with db.transaction(conn) as tx:` 发起（E1）。
- 包名 `snowel-core`（import 名 `snowel_core`），src 布局，测试放 `tests/`。
- 每个 Task 结束提交一次 git commit，消息用 conventional commits（feat/test/chore）。

## 本计划的显式范围裁剪（后续计划承接）

| 裁剪项 | 承接计划 | 本计划的处理 |
|---|---|---|
| llm/ 三口、retrieval/、writeback/、flow/ | 回写环+混合检索计划 | 不建这些模块；api 门面预留命名空间不实现 |
| completeness `active` 判定（需"已确认正文登场"） | 回写环计划 | 本计划实现 draft/profiled 推导 + 手动 override（D5 部分） |
| beat_merged/beat_deleted、stale_marked、volume_sealed、prose_* 事件 | 各自承接计划 | 投影器分发表中留 no-op 占位，不实现物化 |
| FTS5 / sqlite-vec / 嵌入 | 检索计划 | 不建索引 |
| MCP / CLI / Web 外壳 | 壳计划 | 只保证 api 门面可编程调用 |

## File Structure

```
pyproject.toml
src/snowel_core/__init__.py            # 导出 SnowelAPI
src/snowel_core/storage/__init__.py
src/snowel_core/storage/schema.sql     # 全部 DDL
src/snowel_core/storage/db.py          # connect/migrate/transaction
src/snowel_core/storage/events.py      # append_event（唯一写日志入口）
src/snowel_core/storage/projector.py   # 事件→物化动作分发 + apply/rebuild + story_order
src/snowel_core/storage/queries.py     # 基础图查询（含递归 CTE）
src/snowel_core/storage/lease.py       # 单写者租约
src/snowel_core/ontology/__init__.py
src/snowel_core/ontology/groups.py     # 属性组注册表（pydantic，D3）
src/snowel_core/ontology/completeness.py
src/snowel_core/proposal/__init__.py
src/snowel_core/proposal/queue.py      # 提案队列 + 状态机
src/snowel_core/api.py                 # SnowelAPI 门面
tests/conftest.py
tests/test_storage.py                  # Task 1–3
tests/test_projector.py                # Task 4–6
tests/test_queries.py                  # Task 8–9
tests/test_proposal.py                 # Task 10
tests/test_api.py                      # Task 11
```

## 事件 payload 契约（本计划用到的 kind）

统一为 `{"fact": ...}` 列表的"事实集"风格（D1 批量单事件）：

```python
# fact 两形：
{"fact": "node", "id": "<uuid>", "types": ["Character", "Concept"], "name": "林晚",
 "props": {"core": {"motivation": "活下去"}}}
{"fact": "edge", "id": "<uuid>", "src": "<node_id>", "dst": "<node_id>", "kind": "IS_A",
 "props": {}, "valid_from_beat": null, "valid_until_beat": null}

# kind 与 payload：
proposal_confirmed  {"proposal_id", "artifact_type", "facts": [fact...]}
auto_canonized      {"facts": [fact...], "source_hash": "<章节哈希或null>"}
retraction          {"target": "node|edge", "target_id": "<id>", "cascade_hints": [str...]}
completeness_override {"node_id", "old", "new", "reason"}
track_added         {"track_id", "name", "definition": {...}}
track_frozen        {"track_id"}
retcon_applied      {"renames": [{"node_id", "old_name", "new_name"}], "notes": str}
revision_applied    {"structure_changes": [str...]}   # 触发 story_order 全量重算
```

拍地址（D4，存 props，不参与事件引用）：`{"volume": 1, "chapter": 3, "scene": 2, "beat": 5}`。

---

### Task 1: 项目骨架与建库（connect / migrate / transaction）

**Files:**
- Create: `pyproject.toml`, `src/snowel_core/__init__.py`, `src/snowel_core/storage/__init__.py`, `src/snowel_core/storage/schema.sql`, `src/snowel_core/storage/db.py`, `tests/conftest.py`, `tests/test_storage.py`

**Interfaces:**
- Produces: `db.connect(path) -> sqlite3.Connection`（WAL、外键开启）；`db.migrate(conn)`（幂等建表）；`db.transaction(conn)` 上下文管理器（成功 commit、异常 rollback 并 re-raise）。

- [ ] **Step 1: 写 pyproject 与包骨架**

```toml
# pyproject.toml
[project]
name = "snowel-core"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = ["pydantic>=2.7"]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/snowel_core"]

[tool.pytest.ini_options]
testpaths = ["tests"]
```

```bash
mkdir -p src/snowel_core/storage tests
touch src/snowel_core/__init__.py src/snowel_core/storage/__init__.py
pip install -e . pytest
```

- [ ] **Step 2: 写 schema.sql（design §2.1/2.3/2.5/3.1/3.4 + 检查点/租约表）**

```sql
-- src/snowel_core/storage/schema.sql
CREATE TABLE IF NOT EXISTS events(
  seq    INTEGER PRIMARY KEY AUTOINCREMENT,
  ts     TEXT NOT NULL,
  kind   TEXT NOT NULL,
  payload TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS nodes(
  id           TEXT PRIMARY KEY,
  types        TEXT NOT NULL,
  name         TEXT NOT NULL,
  completeness TEXT NOT NULL DEFAULT 'draft',
  props        TEXT NOT NULL DEFAULT '{}',
  story_order  INTEGER,
  active       INTEGER NOT NULL DEFAULT 1,
  created_event INTEGER NOT NULL REFERENCES events(seq)
);
CREATE TABLE IF NOT EXISTS edges(
  id            TEXT PRIMARY KEY,
  src           TEXT NOT NULL,
  dst           TEXT NOT NULL,
  kind          TEXT NOT NULL,
  props         TEXT NOT NULL DEFAULT '{}',
  valid_from    INTEGER,
  valid_until   INTEGER,
  created_event INTEGER NOT NULL REFERENCES events(seq)
);
CREATE TABLE IF NOT EXISTS alias(
  node_id TEXT NOT NULL REFERENCES nodes(id),
  alias   TEXT NOT NULL,
  source  TEXT NOT NULL,
  PRIMARY KEY (node_id, alias)
);
CREATE TABLE IF NOT EXISTS tracks(
  id         TEXT PRIMARY KEY,
  name       TEXT NOT NULL,
  definition TEXT NOT NULL,
  frozen     INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS proposals(
  id         TEXT PRIMARY KEY,
  kind       TEXT NOT NULL,
  payload    TEXT NOT NULL,
  status     TEXT NOT NULL,
  stale_hint TEXT,
  created_ts TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS checkpoint(
  id  INTEGER PRIMARY KEY CHECK (id = 1),
  seq INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS lease(
  id           INTEGER PRIMARY KEY CHECK (id = 1),
  holder       TEXT NOT NULL,
  heartbeat_ts REAL NOT NULL
);
```

- [ ] **Step 3: 写失败测试（connect/migrate/transaction）**

```python
# tests/test_storage.py
import sqlite3
import pytest
from snowel_core.storage import db

def test_migrate_creates_all_tables(tmp_path):
    conn = db.connect(tmp_path / "snowel.db")
    db.migrate(conn)
    names = {r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'")}
    assert {"events", "nodes", "edges", "alias", "tracks",
            "proposals", "checkpoint", "lease"} <= names
    conn.close()

def test_migrate_is_idempotent(tmp_path):
    conn = db.connect(tmp_path / "snowel.db")
    db.migrate(conn); db.migrate(conn)
    conn.close()

def test_transaction_commits_and_rolls_back(tmp_path):
    conn = db.connect(tmp_path / "snowel.db"); db.migrate(conn)
    with db.transaction(conn) as tx:
        tx.execute("INSERT INTO events(ts, kind, payload) VALUES('t','x','{}')")
    with pytest.raises(RuntimeError):
        with db.transaction(conn) as tx:
            tx.execute("INSERT INTO events(ts, kind, payload) VALUES('t','y','{}')")
            raise RuntimeError("boom")
    assert conn.execute("SELECT COUNT(*) FROM events").fetchone()[0] == 1
    conn.close()
```

- [ ] **Step 4: 运行确认失败**

Run: `pytest tests/test_storage.py -v` → Expected: FAIL（ModuleNotFoundError: snowel_core.storage.db）

- [ ] **Step 5: 实现 db.py**

```python
# src/snowel_core/storage/db.py
import sqlite3
from contextlib import contextmanager
from pathlib import Path

SCHEMA = Path(__file__).with_name("schema.sql").read_text(encoding="utf-8")

def connect(path) -> sqlite3.Connection:
    conn = sqlite3.connect(path, isolation_level=None)  # 手动事务
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn

def migrate(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA)

@contextmanager
def transaction(conn: sqlite3.Connection):
    conn.execute("BEGIN IMMEDIATE")
    try:
        yield conn
    except BaseException:
        conn.execute("ROLLBACK")
        raise
    else:
        conn.execute("COMMIT")
```

- [ ] **Step 6: 运行测试通过**

Run: `pytest tests/test_storage.py -v` → Expected: 3 PASS

- [ ] **Step 7: Commit**

```bash
git add pyproject.toml src tests
git commit -m "feat(core): project skeleton, sqlite schema, transaction ctx"
```

---

### Task 2: 事件日志 append（唯一写入口 + append-only）

**Files:**
- Create: `src/snowel_core/storage/events.py`
- Test: `tests/test_storage.py`（追加）

**Interfaces:**
- Consumes: `db.transaction`（调用方必须已开事务；本模块不开事务）。
- Produces: `events.append_event(tx, kind: str, payload: dict) -> int`（返回 seq）；`events.head_seq(conn) -> int`（无事件返回 0）。

- [ ] **Step 1: 写失败测试**

```python
# 追加到 tests/test_storage.py
from snowel_core.storage import events as ev

def _db(tmp_path):
    conn = db.connect(tmp_path / "snowel.db"); db.migrate(conn)
    return conn

def test_append_event_returns_increasing_seq(tmp_path):
    conn = _db(tmp_path)
    assert ev.head_seq(conn) == 0
    with db.transaction(conn) as tx:
        s1 = ev.append_event(tx, "track_added", {"track_id": "t1"})
        s2 = ev.append_event(tx, "track_frozen", {"track_id": "t1"})
    assert (s1, s2) == (1, 2)
    assert ev.head_seq(conn) == 2
    row = conn.execute("SELECT kind, payload FROM events WHERE seq=1").fetchone()
    assert row["kind"] == "track_added"
    conn.close()
```

- [ ] **Step 2: 运行确认失败** — Run: `pytest tests/test_storage.py::test_append_event_returns_increasing_seq -v` → FAIL（ModuleNotFoundError）

- [ ] **Step 3: 实现 events.py**

```python
# src/snowel_core/storage/events.py
import json
import sqlite3
from datetime import datetime, timezone

def append_event(tx: sqlite3.Connection, kind: str, payload: dict) -> int:
    ts = datetime.now(timezone.utc).isoformat()
    cur = tx.execute(
        "INSERT INTO events(ts, kind, payload) VALUES(?,?,?)",
        (ts, kind, json.dumps(payload, ensure_ascii=False)))
    return cur.lastrowid

def head_seq(conn: sqlite3.Connection) -> int:
    row = conn.execute("SELECT COALESCE(MAX(seq), 0) AS s FROM events").fetchone()
    return row["s"]
```

说明：append-only 靠"不存在 update/delete 日志的函数"保证（TC-EV-06 的实现面），事件表不暴露任何其他写 API。

- [ ] **Step 4: 运行通过** — `pytest tests/test_storage.py -v` → PASS

- [ ] **Step 5: Commit** — `git add -A && git commit -m "feat(core): append-only event log"`

---

### Task 3: 投影器核心——proposal_confirmed / auto_canonized 物化节点与边

**Files:**
- Create: `src/snowel_core/storage/projector.py`
- Test: `tests/test_projector.py`

**Interfaces:**
- Consumes: `events.head_seq`、表结构。
- Produces:
  - `projector.apply(conn)`：把 checkpoint 水位线之后的事件全部物化并推进水位线（**必须在调用方事务内调用**，与事件追加原子绑定）；
  - `projector.HANDLERS: dict[str, callable]`（kind → handler(tx, payload, seq)）。

- [ ] **Step 1: 写失败测试（TC-EV-01 / TC-EV-02 / TC-EV-07 部分）**

```python
# tests/test_projector.py
import json
from snowel_core.storage import db, events, projector

NODE_FACT = {"fact": "node", "id": "n-linwan", "types": ["Character"],
             "name": "林晚", "props": {"core": {"motivation": "活下去"}}}
EDGE_FACT = {"fact": "edge", "id": "e-1", "src": "n-linwan", "dst": "n-x",
             "kind": "IS_A", "props": {}}

def _confirmed(conn, facts, artifact="scene"):
    with db.transaction(conn) as tx:
        ev.append_event(tx, "proposal_confirmed",
                        {"proposal_id": "p1", "artifact_type": artifact, "facts": facts})

def test_apply_materializes_node_and_edge(tmp_path):
    conn = db.connect(tmp_path / "s.db"); db.migrate(conn)
    _confirmed(conn, [NODE_FACT, {**EDGE_FACT, "dst": NODE_FACT["id"]} |
               {"fact": "node", "id": "n-x", "types": ["Concept"], "name": "玩家", "props": {}}])
    projector.apply(conn)
    n = conn.execute("SELECT * FROM nodes WHERE id='n-linwan'").fetchone()
    assert n["types"] == json.dumps(["Character"])
    assert n["completeness"] == "draft" and n["active"] == 1
    e = conn.execute("SELECT * FROM edges WHERE id='e-1'").fetchone()
    assert e["kind"] == "IS_A" and e["created_event"] == 1
    # 水位线推进：再 apply 无重复、无新增
    projector.apply(conn)
    assert conn.execute("SELECT COUNT(*) FROM nodes").fetchone()[0] == 2

def test_batch_facts_single_event(tmp_path):  # D1/TC-EV-02
    conn = db.connect(tmp_path / "s.db"); db.migrate(conn)
    facts = [{"fact": "node", "id": f"n-{i}", "types": ["Concept"],
              "name": f"c{i}", "props": {}} for i in range(5)]
    _confirmed(conn, facts)
    projector.apply(conn)
    assert conn.execute("SELECT COUNT(*) FROM events").fetchone()[0] == 1
    assert conn.execute("SELECT COUNT(*) FROM nodes").fetchone()[0] == 5

def test_apply_is_incremental_with_checkpoint(tmp_path):
    conn = db.connect(tmp_path / "s.db"); db.migrate(conn)
    _confirmed(conn, [NODE_FACT])
    projector.apply(conn)
    cp = conn.execute("SELECT seq FROM checkpoint WHERE id=1").fetchone()
    assert cp["seq"] == 1
```

- [ ] **Step 2: 运行确认失败** — `pytest tests/test_projector.py -v` → FAIL

- [ ] **Step 3: 实现 projector.py（本任务只含 node/edge upsert handler）**

```python
# src/snowel_core/storage/projector.py
import json
import sqlite3
from . import events

def _upsert_node(tx, f: dict, seq: int):
    tx.execute(
        """INSERT INTO nodes(id, types, name, completeness, props, active, created_event)
           VALUES(?,?,?,?,?,1,?)
           ON CONFLICT(id) DO UPDATE SET
             types=excluded.types, name=excluded.name, props=excluded.props""",
        (f["id"], json.dumps(f["types"], ensure_ascii=False), f["name"],
         f.get("completeness", "draft"), json.dumps(f.get("props", {}), ensure_ascii=False), seq))

def _upsert_edge(tx, f: dict, seq: int):
    vf, vu = f.get("valid_from_beat"), f.get("valid_until_beat")  # 拍地址→story_order 由 Task 5 换算，先存 null
    tx.execute(
        """INSERT INTO edges(id, src, dst, kind, props, created_event)
           VALUES(?,?,?,?,?,?)
           ON CONFLICT(id) DO UPDATE SET
             src=excluded.src, dst=excluded.dst, kind=excluded.kind, props=excluded.props""",
        (f["id"], f["src"], f["dst"], f["kind"],
         json.dumps(f.get("props", {}), ensure_ascii=False), seq))

def _facts_event(tx, payload: dict, seq: int):
    for f in payload["facts"]:
        (_upsert_node if f["fact"] == "node" else _upsert_edge)(tx, f, seq)

HANDLERS = {
    "proposal_confirmed": _facts_event,
    "auto_canonized": _facts_event,
    # 其余 kind 由 Task 4/后续计划补齐；未知 kind 记录但不物化（防前向兼容炸库）
}

def _checkpoint(conn) -> int:
    row = conn.execute("SELECT seq FROM checkpoint WHERE id=1").fetchone()
    return row["seq"] if row else 0

def apply(conn: sqlite3.Connection) -> None:
    """物化 checkpoint 之后的事件。必须在调用方事务内调用。"""
    last = _checkpoint(conn)
    rows = conn.execute(
        "SELECT seq, kind, payload FROM events WHERE seq > ? ORDER BY seq", (last,)).fetchall()
    for r in rows:
        payload = json.loads(r["payload"])
        handler = HANDLERS.get(r["kind"])
        if handler:
            handler(conn, payload, r["seq"])
    if rows:
        conn.execute(
            "INSERT INTO checkpoint(id, seq) VALUES(1, ?) "
            "ON CONFLICT(id) DO UPDATE SET seq=excluded.seq",
            (rows[-1]["seq"],))
```

- [ ] **Step 4: 运行通过** — `pytest tests/test_projector.py -v` → 3 PASS（注意修正 Step 1 测试里 EDGE_FACT 的 dst 引用：应指向已存在的 n-x 节点，按写出的实际断言微调事实列表）

- [ ] **Step 5: Commit** — `git add -A && git commit -m "feat(core): projector materializes node/edge facts with checkpoint"`

---

### Task 4: 投影器扩展——retraction / completeness_override / track_* / retcon 改名与 alias

**Files:**
- Modify: `src/snowel_core/storage/projector.py`
- Test: `tests/test_projector.py`（追加）

**Interfaces:**
- Produces: HANDLERS 新增 5 个 kind；retraction 使目标物化行 `active=0`；retcon 改名自动写 alias 表。

- [ ] **Step 1: 写失败测试（TC-EV-04 前置 / TC-ON-02 / TC-ON-07 / TC-ON-10 物化面）**

```python
# 追加到 tests/test_projector.py
def _ev(conn, kind, payload):
    with db.transaction(conn) as tx:
        ev.append_event(tx, kind, payload)

def test_retraction_deactivates_node(tmp_path):  # C2
    conn = db.connect(tmp_path / "s.db"); db.migrate(conn)
    _confirmed(conn, [NODE_FACT]); projector.apply(conn)
    _ev(conn, "retraction", {"target": "node", "target_id": "n-linwan", "cascade_hints": []})
    projector.apply(conn)
    n = conn.execute("SELECT active FROM nodes WHERE id='n-linwan'").fetchone()
    assert n["active"] == 0
    assert conn.execute("SELECT COUNT(*) FROM events").fetchone()[0] == 2  # 行未删、日志 append-only

def test_retcon_rename_keeps_alias(tmp_path):  # D2/TC-ON-02
    conn = db.connect(tmp_path / "s.db"); db.migrate(conn)
    _confirmed(conn, [NODE_FACT]); projector.apply(conn)
    _ev(conn, "retcon_applied", {"renames": [
        {"node_id": "n-linwan", "old_name": "林晚", "new_name": "江晚"}], "notes": ""})
    projector.apply(conn)
    n = conn.execute("SELECT name FROM nodes WHERE id='n-linwan'").fetchone()
    a = conn.execute("SELECT alias FROM alias WHERE node_id='n-linwan'").fetchone()
    assert n["name"] == "江晚" and a["alias"] == "林晚"

def test_completeness_override_event(tmp_path):  # D5
    conn = db.connect(tmp_path / "s.db"); db.migrate(conn)
    _confirmed(conn, [NODE_FACT]); projector.apply(conn)
    _ev(conn, "completeness_override",
        {"node_id": "n-linwan", "old": "draft", "new": "profiled", "reason": "手动"})
    projector.apply(conn)
    assert conn.execute("SELECT completeness FROM nodes WHERE id='n-linwan'"
                        ).fetchone()["completeness"] == "profiled"

def test_track_added_and_frozen(tmp_path):  # C7
    conn = db.connect(tmp_path / "s.db"); db.migrate(conn)
    _ev(conn, "track_added", {"track_id": "t1", "name": "现实轨",
                              "definition": {"scale": 1.0}})
    _ev(conn, "track_frozen", {"track_id": "t1"})
    projector.apply(conn)
    t = conn.execute("SELECT * FROM tracks WHERE id='t1'").fetchone()
    assert t["frozen"] == 1

def test_unknown_kind_is_noop(tmp_path):
    conn = db.connect(tmp_path / "s.db"); db.migrate(conn)
    _ev(conn, "volume_sealed", {"volume_id": "v1"})  # 后续计划的 kind
    projector.apply(conn)  # 不抛错，水位线照常推进
    assert conn.execute("SELECT seq FROM checkpoint WHERE id=1").fetchone()["seq"] == 1
```

- [ ] **Step 2: 运行确认失败** — `pytest tests/test_projector.py -v` → 新增 5 条 FAIL

- [ ] **Step 3: 实现 handlers（追加进 projector.py）**

```python
def _retraction(tx, payload, seq):
    table = "nodes" if payload["target"] == "node" else "edges"
    if table == "nodes":
        tx.execute("UPDATE nodes SET active=0 WHERE id=?", (payload["target_id"],))
    else:
        tx.execute("UPDATE edges SET valid_until=-1 WHERE id=?", (payload["target_id"],))
    # edges 的 valid_until=-1 表示"已被撤回、任何拍均不生效"

def _retcon_applied(tx, payload, seq):
    for r in payload.get("renames", []):
        tx.execute("UPDATE nodes SET name=? WHERE id=?", (r["new_name"], r["node_id"]))
        tx.execute("INSERT OR IGNORE INTO alias(node_id, alias, source) VALUES(?,?,?)",
                   (r["node_id"], r["old_name"], "retcon"))

def _completeness_override(tx, payload, seq):
    tx.execute("UPDATE nodes SET completeness=? WHERE id=?",
               (payload["new"], payload["node_id"]))

def _track_added(tx, payload, seq):
    tx.execute("INSERT INTO tracks(id, name, definition, frozen) VALUES(?,?,?,0) "
               "ON CONFLICT(id) DO NOTHING",
               (payload["track_id"], payload["name"],
                json.dumps(payload["definition"], ensure_ascii=False)))

def _track_frozen(tx, payload, seq):
    tx.execute("UPDATE tracks SET frozen=1 WHERE id=?", (payload["track_id"],))

HANDLERS.update({
    "retraction": _retraction,
    "retcon_applied": _retcon_applied,
    "completeness_override": _completeness_override,
    "track_added": _track_added,
    "track_frozen": _track_frozen,
})
```

- [ ] **Step 4: 运行通过** — `pytest tests/test_projector.py -v` → 8 PASS

- [ ] **Step 5: Commit** — `git add -A && git commit -m "feat(core): projector handlers for retraction/retcon/override/tracks"`

---

### Task 5: 拍地址与 story_order 物化（revision_applied 重算）

**Files:**
- Modify: `src/snowel_core/storage/projector.py`
- Test: `tests/test_projector.py`（追加）

**Interfaces:**
- Produces: `projector.recompute_story_order(conn)`（必须在事务内）；对 props 含 `address` 的 node（Volume/Chapter/Scene/MicroBeat）按 `(volume, chapter, scene, beat)` 字典序赋全局单调整数；边的 `valid_from_beat/valid_until_beat` 地址换算为 valid_from/valid_until story_order；`revision_applied` 事件自动触发重算。

- [ ] **Step 1: 写失败测试（TC-ON-09 / D4）**

```python
# 追加到 tests/test_projector.py
def _addr_node(nid, name, addr):
    return {"fact": "node", "id": nid, "types": ["Chapter"], "name": name,
            "props": {"address": addr}}

def test_story_order_stable_on_insertion(tmp_path):
    conn = db.connect(tmp_path / "s.db"); db.migrate(conn)
    _confirmed(conn, [
        _addr_node("ch2", "第二章", {"volume": 1, "chapter": 2, "scene": 0, "beat": 0}),
        _addr_node("ch3", "第三章", {"volume": 1, "chapter": 3, "scene": 0, "beat": 0}),
    ])
    projector.apply(conn)
    so = {r["id"]: r["story_order"] for r in conn.execute(
        "SELECT id, story_order FROM nodes WHERE id LIKE 'ch%'")}
    assert so["ch2"] < so["ch3"]
    # 插章：ch2 改为 chapter 2、新章占 2.5 位置用 chapter 索引体现
    _ev(conn, "revision_applied", {"structure_changes": [
        {"op": "move", "node_id": "ch3", "address": {"volume": 1, "chapter": 4,
         "scene": 0, "beat": 0}}]})
    with db.transaction(conn) as tx:
        _upsert = None  # 插入新章走正常确认事件：
        ev.append_event(tx, "proposal_confirmed", {"proposal_id": "p2",
            "artifact_type": "structure", "facts": [
                _addr_node("ch25", "新章", {"volume": 1, "chapter": 3,
                 "scene": 0, "beat": 0})]})
    projector.apply(conn)
    so = {r["id"]: r["story_order"] for r in conn.execute(
        "SELECT id, story_order FROM nodes WHERE id LIKE 'ch%'")}
    assert so["ch2"] < so["ch25"] < so["ch3"]          # 派生序重排
    # ID 与历史引用不动：
    assert conn.execute("SELECT COUNT(*) FROM nodes WHERE id='ch3'").fetchone()[0] == 1

def test_revision_applied_moves_node_address(tmp_path):
    conn = db.connect(tmp_path / "s.db"); db.migrate(conn)
    _confirmed(conn, [_addr_node("ch1", "一", {"volume": 1, "chapter": 1, "scene": 0, "beat": 0}),
                      _addr_node("ch2", "二", {"volume": 1, "chapter": 2, "scene": 0, "beat": 0})])
    projector.apply(conn)
    _ev(conn, "revision_applied", {"structure_changes": [
        {"op": "move", "node_id": "ch2",
         "address": {"volume": 1, "chapter": 0, "scene": 0, "beat": 0}}]})
    projector.apply(conn)
    so = {r["id"]: r["story_order"] for r in conn.execute(
        "SELECT id, story_order FROM nodes WHERE id LIKE 'ch%'")}
    assert so["ch2"] < so["ch1"]
```

- [ ] **Step 2: 运行确认失败** — FAIL（story_order 为 NULL）

- [ ] **Step 3: 实现地址排序与 revision handler**

```python
def _addr_key(props: dict) -> tuple:
    a = props.get("address") or {}
    return (a.get("volume", 0), a.get("chapter", 0), a.get("scene", 0), a.get("beat", 0))

def recompute_story_order(conn: sqlite3.Connection) -> None:
    rows = conn.execute("SELECT id, props FROM nodes WHERE active=1").fetchall()
    addressed = [( _addr_key(json.loads(r["props"])), r["id"]) for r in rows
                 if json.loads(r["props"]).get("address")]
    addressed.sort()
    order = {nid: i for i, (_, nid) in enumerate(addressed)}
    conn.executemany("UPDATE nodes SET story_order=? WHERE id=?",
                     [(order.get(r["id"]), r["id"]) for r in rows])
    # 边有效期：拍地址 → story_order
    for e in conn.execute("SELECT id, props FROM edges").fetchall():
        p = json.loads(e["props"])
        vf, vu = p.get("valid_from_beat"), p.get("valid_until_beat")
        conn.execute("UPDATE edges SET valid_from=?, valid_until=? WHERE id=?",
                     (order.get(vf) if vf else None,
                      order.get(vu) if vu else None, e["id"]))

def _revision_applied(tx, payload, seq):
    for ch in payload.get("structure_changes", []):
        if ch.get("op") == "move":
            props = tx.execute("SELECT props FROM nodes WHERE id=?",
                               (ch["node_id"],)).fetchone()
            p = json.loads(props["props"]); p["address"] = ch["address"]
            tx.execute("UPDATE nodes SET props=? WHERE id=?",
                       (json.dumps(p, ensure_ascii=False), ch["node_id"]))
    recompute_story_order(tx)

HANDLERS["revision_applied"] = _revision_applied
```

同时：在 `apply()` 末尾、推进水位线之前调用 `recompute_story_order(conn)`（任何含地址事实的事件后派生序保持最新）。

- [ ] **Step 4: 运行通过** — `pytest tests/test_projector.py -v` → 10 PASS

- [ ] **Step 5: Commit** — `git add -A && git commit -m "feat(core): story_order materialization and revision moves"`

---

### Task 6: state_at 历史点投影查询（修正后视角）

**Files:**
- Create: `src/snowel_core/storage/queries.py`（state_at 放这里，Task 8 续写查询）
- Test: `tests/test_queries.py`

**Interfaces:**
- Produces: `queries.state_at(conn, story_order: int) -> dict`，返回 `{"nodes": [Row], "edges": [Row]}`：物化图当前生效集过滤"在该 story_order 点生效"——node 需 `active=1` 且（若 props 有 `death_beat`）死亡点 > 该点；edge 需 `valid_from`/`valid_until` 区间包含该点。

- [ ] **Step 1: 写失败测试（TC-EV-03 / TC-EV-04）**

```python
# tests/test_queries.py
from snowel_core.storage import db, events, projector, queries

def _mk(tmp_path):
    conn = db.connect(tmp_path / "s.db"); db.migrate(conn); return conn

def _confirm(conn, facts, **kw):
    with db.transaction(conn) as tx:
        events.append_event(tx, "proposal_confirmed",
                            {"proposal_id": "p", "artifact_type": "t",
                             "facts": facts, **kw})
    projector.apply(conn)

def test_state_at_filters_by_validity(tmp_path):
    conn = _mk(tmp_path)
    _confirm(conn, [
        {"fact": "node", "id": "mb1", "types": ["MicroBeat"], "name": "b1",
         "props": {"address": {"volume": 1, "chapter": 1, "scene": 1, "beat": 1}}},
        {"fact": "node", "id": "mb2", "types": ["MicroBeat"], "name": "b2",
         "props": {"address": {"volume": 1, "chapter": 1, "scene": 1, "beat": 2}}},
        {"fact": "edge", "id": "e1", "src": "mb1", "dst": "mb2", "kind": "PARTICIPATES",
         "props": {"valid_from_beat": "mb1", "valid_until_beat": "mb2"}},
    ])
    p1 = queries.state_at(conn, 0)
    assert {n["id"] for n in p1["nodes"]} == {"mb1"}     # mb2 尚未生效
    p2 = queries.state_at(conn, 1)
    assert {n["id"] for n in p2["nodes"]} == {"mb1", "mb2"}

def test_state_at_uses_current_effective_version(tmp_path):  # C9 修正后视角
    conn = _mk(tmp_path)
    _confirm(conn, [{"fact": "node", "id": "n1", "types": ["Character"],
                     "name": "林晚", "props": {"core": {"level": 1}}}])
    # retcon 修正等级（追加事件，物化为当前版）
    with db.transaction(conn) as tx:
        events.append_event(tx, "proposal_confirmed",
            {"proposal_id": "p2", "artifact_type": "retcon", "facts": [
                {"fact": "node", "id": "n1", "types": ["Character"], "name": "林晚",
                 "props": {"core": {"level": 9}}}]})
    projector.apply(conn)
    s = queries.state_at(conn, 0)
    assert s["nodes"][0]["props_core_level"] == 9        # 取当前生效版，不是历史原版
```

- [ ] **Step 2: 运行确认失败** — FAIL（queries.state_at 不存在）

- [ ] **Step 3: 实现 state_at**

```python
# src/snowel_core/storage/queries.py
import json
import sqlite3

def state_at(conn: sqlite3.Connection, story_order: int) -> dict:
    nodes = []
    for r in conn.execute("SELECT * FROM nodes WHERE active=1"):
        props = json.loads(r["props"])
        flat = {f"{g}_{k}": v for g, gv in props.items() for k, v in gv.items()}
        death = props.get("core", {}).get("death_beat")
        if death is not None:
            dso = conn.execute("SELECT story_order FROM nodes WHERE id=?",
                               (death,)).fetchone()
            if dso and dso["story_order"] is not None and dso["story_order"] <= story_order:
                continue
        nodes.append({**dict(r), **flat})
    edges = [dict(r) for r in conn.execute(
        """SELECT * FROM edges
           WHERE (valid_from IS NULL OR valid_from <= ?)
             AND (valid_until IS NULL OR valid_until >= ?)""",
        (story_order, story_order))]
    return {"nodes": nodes, "edges": edges}
```

- [ ] **Step 4: 运行通过** — `pytest tests/test_queries.py -v` → 2 PASS

- [ ] **Step 5: Commit** — `git add -A && git commit -m "feat(core): state_at replay with corrected-view semantics"`

---

### Task 7: rebuild 全量重建

**Files:**
- Modify: `src/snowel_core/storage/projector.py`
- Test: `tests/test_projector.py`（追加）

**Interfaces:**
- Produces: `projector.rebuild(conn)`——清空物化表（nodes/edges/alias/tracks/checkpoint），重放全部事件。自带事务。

- [ ] **Step 1: 写失败测试（TC-EV-05）**

```python
# 追加到 tests/test_projector.py
def test_rebuild_reproduces_identical_state(tmp_path):
    conn = db.connect(tmp_path / "s.db"); db.migrate(conn)
    _confirmed(conn, [NODE_FACT,
        {"fact": "node", "id": "n-x", "types": ["Concept"], "name": "玩家", "props": {}}])
    _ev(conn, "retcon_applied", {"renames": [
        {"node_id": "n-linwan", "old_name": "林晚", "new_name": "江晚"}], "notes": ""})
    projector.apply(conn)
    before = [tuple(r) for r in conn.execute(
        "SELECT * FROM nodes ORDER BY id")]
    edge_before = conn.execute("SELECT COUNT(*) FROM edges").fetchone()[0]
    projector.rebuild(conn)
    after = [tuple(r) for r in conn.execute("SELECT * FROM nodes ORDER BY id")]
    assert before == after
    assert conn.execute("SELECT COUNT(*) FROM edges").fetchone()[0] == edge_before
    assert conn.execute("SELECT seq FROM checkpoint WHERE id=1").fetchone()["seq"] == \
        events.head_seq(conn)
```

- [ ] **Step 2: 运行确认失败** — FAIL（rebuild 不存在）

- [ ] **Step 3: 实现 rebuild**

```python
def rebuild(conn: sqlite3.Connection) -> None:
    with _tx(conn):  # 复用 db.transaction，避免循环 import：局部 import
        from .db import transaction
    # ——实现如下（上面的伪示意删掉，用真代码）：——
```

实际实现（替换上面占位）：

```python
def rebuild(conn: sqlite3.Connection) -> None:
    from .db import transaction
    with transaction(conn):
        for t in ("nodes", "edges", "alias", "tracks", "checkpoint"):
            conn.execute(f"DELETE FROM {t}")
        apply(conn)
```

- [ ] **Step 4: 运行通过** — `pytest tests/test_projector.py -v` → 11 PASS

- [ ] **Step 5: Commit** — `git add -A && git commit -m "feat(core): full rebuild from event log"`

---

### Task 8: 基础图查询（name/alias 命中、类型过滤、边反查、递归 CTE）

**Files:**
- Modify: `src/snowel_core/storage/queries.py`
- Test: `tests/test_queries.py`（追加）

**Interfaces:**
- Produces:
  - `queries.get_node(conn, node_id) -> Row | None`
  - `queries.find_nodes(conn, name: str | None = None, type: str | None = None) -> list[Row]`（name 同时匹配 name 与 alias）
  - `queries.edges_of(conn, node_id: str, direction: str = "both") -> list[Row]`
  - `queries.descendants(conn, node_id: str, kinds: list[str] | None = None, max_depth: int = 10) -> list[Row]`（递归 CTE）

- [ ] **Step 1: 写失败测试（TC-ON-01 / TC-ON-02 查询面）**

```python
# 追加到 tests/test_queries.py
def _seed(tmp_path):
    conn = _mk(tmp_path)
    _confirm(conn, [
        {"fact": "node", "id": "n1", "types": ["Character", "Concept"],
         "name": "江晚", "props": {}},
        {"fact": "node", "id": "n2", "types": ["Concept"], "name": "轮回游戏", "props": {}},
        {"fact": "node", "id": "n3", "types": ["Mechanism"], "name": "积分兑换", "props": {}},
        {"fact": "edge", "id": "e1", "src": "n2", "dst": "n3", "kind": "REQUIRES", "props": {}},
        {"fact": "edge", "id": "e2", "src": "n3", "dst": "n2", "kind": "IS_A", "props": {}},
    ])
    with db.transaction(conn) as tx:
        events.append_event(tx, "retcon_applied", {"renames": [
            {"node_id": "n1", "old_name": "林晚", "new_name": "江晚"}], "notes": ""})
    projector.apply(conn)
    return conn

def test_find_nodes_by_alias_and_type(tmp_path):
    conn = _seed(tmp_path)
    assert queries.find_nodes(conn, name="林晚")[0]["id"] == "n1"   # alias 命中
    assert queries.find_nodes(conn, name="江晚")[0]["id"] == "n1"
    assert {r["id"] for r in queries.find_nodes(conn, type="Concept")} == {"n1", "n2"}

def test_edges_of_both_directions(tmp_path):
    conn = _seed(tmp_path)
    out = queries.edges_of(conn, "n2", "out")
    assert [e["id"] for e in out] == ["e1"]
    both = queries.edges_of(conn, "n3")
    assert {e["id"] for e in both} == {"e1", "e2"}

def test_descendants_recursive_cte(tmp_path):
    conn = _seed(tmp_path)
    # e1: n2->n3, e2: n3->n2 构成环：递归 CTE 必须不死循环
    ds = queries.descendants(conn, "n2", max_depth=5)
    assert {r["id"] for r in ds} == {"n3"}
```

- [ ] **Step 2: 运行确认失败** — FAIL

- [ ] **Step 3: 实现四个查询**

```python
def get_node(conn, node_id):
    return conn.execute("SELECT * FROM nodes WHERE id=?", (node_id,)).fetchone()

def find_nodes(conn, name=None, type=None):
    sql = """SELECT DISTINCT n.* FROM nodes n
             LEFT JOIN alias a ON a.node_id = n.id
             WHERE n.active=1"""
    args = []
    if name is not None:
        sql += " AND (n.name=? OR a.alias=?)"; args += [name, name]
    if type is not None:
        sql += " AND n.types LIKE ?"; args.append(f'%"{type}"%')
    return conn.execute(sql, args).fetchall()

def edges_of(conn, node_id, direction="both"):
    if direction == "out":
        return conn.execute("SELECT * FROM edges WHERE src=?", (node_id,)).fetchall()
    if direction == "in":
        return conn.execute("SELECT * FROM edges WHERE dst=?", (node_id,)).fetchall()
    return conn.execute(
        "SELECT * FROM edges WHERE src=? OR dst=?", (node_id, node_id)).fetchall()

def descendants(conn, node_id, kinds=None, max_depth=10):
    return conn.execute("""
        WITH RECURSIVE walk(id, depth) AS (
            SELECT dst, 1 FROM edges WHERE src=?
            UNION
            SELECT e.dst, walk.depth+1 FROM edges e
            JOIN walk ON e.src = walk.id WHERE walk.depth < ?
        )
        SELECT DISTINCT n.* FROM walk JOIN nodes n ON n.id = walk.id
        WHERE n.active=1
    """, (node_id, max_depth)).fetchall()
```

（`kinds` 参数本计划保留签名不消费——按 kind 过滤边属级联检查计划的需求，YAGNI。）

- [ ] **Step 4: 运行通过** — `pytest tests/test_queries.py -v` → 5 PASS

- [ ] **Step 5: Commit** — `git add -A && git commit -m "feat(core): graph queries with alias hit and recursive CTE"`

---

### Task 9: 属性组注册表与 completeness 推导（ontology）

**Files:**
- Create: `src/snowel_core/ontology/__init__.py`, `src/snowel_core/ontology/groups.py`, `src/snowel_core/ontology/completeness.py`
- Test: `tests/test_ontology.py`

**Interfaces:**
- Produces:
  - `groups.registry`：`register(schema: pydantic.Model, name: str, version: int)`；`validate(group_name: str, data: dict) -> ("ok" | "unmanaged" | "version_mismatch", warning: str | None)`；core 组内置注册。
  - `completeness.derive(conn, node_id) -> "draft" | "profiled"`：core 组必填齐备 → `profiled` 候选（经确认的迁移由 proposal 确认事件带 `completeness` 字段或 override 完成）；`is_core_complete(props: dict) -> bool`。

- [ ] **Step 1: 写失败测试（TC-ON-03 / TC-ON-04 / TC-ON-05 推导面）**

```python
# tests/test_ontology.py
from snowel_core.ontology import groups, completeness

def test_core_group_registered_and_validated():
    status, warn = groups.validate("core", {"motivation": "活下去", "lie": "没人会救我",
                                            "fear": "被抛下", "arc": "学会信任"})
    assert status == "ok" and warn is None
    status, warn = groups.validate("core", {"motivation": "x"})
    assert status == "invalid"

def test_unmanaged_group_stored_with_flag():
    status, warn = groups.validate("foo", {"anything": 1})
    assert status == "unmanaged"

def test_version_mismatch_downgrades_to_warning():
    groups._registered.pop("demo", None)
    from pydantic import BaseModel
    class DemoV2(BaseModel):
        power: int
    groups.register(DemoV2, "demo", version=2)
    data = {"_schema": "demo@1", "power": 5}
    status, warn = groups.validate("demo", data)
    assert status == "version_mismatch" and warn

def test_derive_completeness():
    assert not completeness.is_core_complete({"motivation": "x"})
    assert completeness.is_core_complete(
        {"motivation": "x", "lie": "y", "fear": "z", "arc": "w"})
```

- [ ] **Step 2: 运行确认失败** — FAIL

- [ ] **Step 3: 实现 groups.py 与 completeness.py**

```python
# src/snowel_core/ontology/groups.py
from pydantic import BaseModel, ValidationError

class CoreGroup(BaseModel):
    motivation: str
    lie: str
    fear: str
    arc: str

_registered: dict[str, tuple[type[BaseModel], int]] = {}

def register(schema: type[BaseModel], name: str, version: int) -> None:
    _registered[name] = (schema, version)

def validate(group_name: str, data: dict):
    if group_name not in _registered:
        return "unmanaged", None
    schema, cur = _registered[group_name]
    declared = None
    if isinstance(data.get("_schema"), str) and "@" in data["_schema"]:
        declared = int(data["_schema"].split("@")[1])
    try:
        schema.model_validate(data)
    except ValidationError as e:
        if declared is not None and declared != cur:
            return "version_mismatch", f"组 {group_name}@{declared} 与注册版本 @{cur} 不匹配"
        return "invalid", str(e.errors()[0])
    if declared is not None and declared != cur:
        return "version_mismatch", f"组 {group_name}@{declared} 与注册版本 @{cur} 不匹配"
    return "ok", None

register(CoreGroup, "core", version=1)
```

```python
# src/snowel_core/ontology/completeness.py
# active 判定需"已确认正文登场"，属回写环计划；此处只做 draft/profiled。
_CORE_FIELDS = ("motivation", "lie", "fear", "arc")

def is_core_complete(core: dict) -> bool:
    return all(core.get(f) for f in _CORE_FIELDS)

def derive(props: dict) -> str:
    return "profiled" if is_core_complete(props.get("core", {})) else "draft"
```

- [ ] **Step 4: 运行通过** — `pytest tests/test_ontology.py -v` → 4 PASS

- [ ] **Step 5: Commit** — `git add -A && git commit -m "feat(core): property-group registry and completeness derivation"`

---

### Task 10: 提案队列（状态机 + 确认单事务）

**Files:**
- Create: `src/snowel_core/proposal/__init__.py`, `src/snowel_core/proposal/queue.py`
- Test: `tests/test_proposal.py`

**Interfaces:**
- Consumes: `events.append_event`、`projector.apply`、事实集契约。
- Produces: `proposal.ProposalQueue(conn)`：
  - `create(kind: str, payload: dict) -> str`（uuid，pending 入库，**不写事件日志**）
  - `list(status: str | None = None) -> list[Row]`
  - `confirm(proposal_id: str) -> int`：单事务 = 追加 `proposal_confirmed` + apply + 状态置 confirmed，返回事件 seq
  - `reject(proposal_id: str, reason: str | None = None)` / `void(proposal_id: str)` / `mark_stale(proposal_id, hint: str)`
  - 状态迁移校验：非法迁移抛 `ProposalStateError`。

- [ ] **Step 1: 写失败测试（TC-PR-01/05/06/07 + TC-EV-07/08）**

```python
# tests/test_proposal.py
import pytest
from snowel_core.storage import db
from snowel_core.proposal import queue

FACTS = [{"fact": "node", "id": "n1", "types": ["Character"],
          "name": "林晚", "props": {}}]

@pytest.fixture
def q(tmp_path):
    conn = db.connect(tmp_path / "s.db"); db.migrate(conn)
    return queue.ProposalQueue(conn), conn

def test_create_is_pending_not_in_log(q):
    q, conn = q
    pid = q.create("scene", {"facts": FACTS})
    p = q.list("pending")
    assert [r["id"] for r in p] == [pid]
    assert conn.execute("SELECT COUNT(*) FROM events").fetchone()[0] == 0  # TC-EV-07

def test_confirm_appends_event_and_materializes(q):
    q, conn = q
    pid = q.create("scene", {"facts": FACTS})
    seq = q.confirm(pid)
    assert seq == 1
    assert conn.execute("SELECT status FROM proposals WHERE id=?", (pid,)).fetchone()["status"] == "confirmed"
    assert conn.execute("SELECT COUNT(*) FROM nodes").fetchone()[0] == 1

def test_confirm_atomic_on_bad_fact(q):  # TC-EV-08
    q, conn = q
    pid = q.create("scene", {"facts": [{"fact": "node", "id": "n1",
        "types": "Character", "name": "x", "props": {}}]})   # types 非数组 → 投影抛错
    with pytest.raises(Exception):
        q.confirm(pid)
    assert conn.execute("SELECT COUNT(*) FROM events").fetchone()[0] == 0
    assert conn.execute("SELECT COUNT(*) FROM nodes").fetchone()[0] == 0
    assert conn.execute("SELECT status FROM proposals WHERE id=?", (pid,)).fetchone()["status"] == "pending"

def test_reject_and_void_events(q):
    q, conn = q
    p1 = q.create("scene", {"facts": FACTS})
    p2 = q.create("scene", {"facts": FACTS})
    q.reject(p1, reason="重复")
    q.void(p2)
    kinds = [r[0] for r in conn.execute("SELECT kind FROM events ORDER BY seq")]
    assert kinds == ["proposal_rejected", "proposal_voided"]

def test_stale_and_strong_confirm(q):  # C5
    q, conn = q
    pid = q.create("scene", {"facts": FACTS})
    q.mark_stale(pid, "上游梗概已改")
    assert q.list("stale")[0]["stale_hint"] == "上游梗概已改"
    q.confirm(pid)   # stale → 强行确认，允许
    assert conn.execute("SELECT status FROM proposals WHERE id=?",
                        (pid,)).fetchone()["status"] == "confirmed"

def test_invalid_transition_raises(q):
    q, conn = q
    pid = q.create("scene", {"facts": FACTS})
    q.reject(pid)
    with pytest.raises(queue.ProposalStateError):
        q.confirm(pid)   # rejected 是终态

def test_no_ttl_no_autovoid(q):  # TC-PR-07：created_ts 久远也不自动迁移
    q, conn = q
    pid = q.create("scene", {"facts": FACTS})
    conn.execute("UPDATE proposals SET created_ts='2000-01-01' WHERE id=?", (pid,))
    assert [r["id"] for r in q.list("pending")] == [pid]
```

- [ ] **Step 2: 运行确认失败** — FAIL

- [ ] **Step 3: 实现 queue.py**

```python
# src/snowel_core/proposal/queue.py
import json
import sqlite3
import uuid
from datetime import datetime, timezone

from ..storage import events, projector
from ..storage.db import transaction

class ProposalStateError(Exception):
    pass

_ALLOWED = {  # design §3.3 状态图
    ("pending", "confirmed"), ("pending", "rejected"), ("pending", "voided"),
    ("pending", "stale"), ("stale", "pending"), ("stale", "confirmed"),
    ("stale", "rejected"), ("stale", "voided"),
}

class ProposalQueue:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def _get(self, pid) -> sqlite3.Row:
        return self.conn.execute(
            "SELECT * FROM proposals WHERE id=?", (pid,)).fetchone()

    def _transition(self, pid, new: str) -> None:
        old = self._get(pid)["status"]
        if (old, new) not in _ALLOWED:
            raise ProposalStateError(f"非法迁移 {old} -> {new}")

    def create(self, kind: str, payload: dict) -> str:
        pid = str(uuid.uuid4())
        self.conn.execute(
            "INSERT INTO proposals(id, kind, payload, status, created_ts) VALUES(?,?,?,?,?)",
            (pid, kind, json.dumps(payload, ensure_ascii=False), "pending",
             datetime.now(timezone.utc).isoformat()))
        return pid

    def list(self, status=None):
        if status:
            return self.conn.execute(
                "SELECT * FROM proposals WHERE status=? ORDER BY created_ts",
                (status,)).fetchall()
        return self.conn.execute(
            "SELECT * FROM proposals ORDER BY created_ts").fetchall()

    def confirm(self, proposal_id: str) -> int:
        self._transition(proposal_id, "confirmed")
        p = self._get(proposal_id)
        payload = json.loads(p["payload"])
        with transaction(self.conn):
            seq = events.append_event(self.conn, "proposal_confirmed", {
                "proposal_id": proposal_id, "artifact_type": p["kind"],
                "facts": payload["facts"]})
            projector.apply(self.conn)
            self.conn.execute(
                "UPDATE proposals SET status='confirmed' WHERE id=?", (proposal_id,))
        return seq

    def reject(self, proposal_id: str, reason: str | None = None):
        self._transition(proposal_id, "rejected")
        with transaction(self.conn):
            events.append_event(self.conn, "proposal_rejected",
                                {"proposal_id": proposal_id, "reason": reason})
            self.conn.execute(
                "UPDATE proposals SET status='rejected' WHERE id=?", (proposal_id,))

    def void(self, proposal_id: str):
        self._transition(proposal_id, "voided")
        with transaction(self.conn):
            events.append_event(self.conn, "proposal_voided",
                                {"proposal_id": proposal_id})
            self.conn.execute(
                "UPDATE proposals SET status='voided' WHERE id=?", (proposal_id,))

    def mark_stale(self, proposal_id: str, hint: str):
        self._transition(proposal_id, "stale")
        with transaction(self.conn):
            events.append_event(self.conn, "stale_marked",
                                {"proposal_id": proposal_id, "hint": hint})
            self.conn.execute(
                "UPDATE proposals SET status='stale', stale_hint=? WHERE id=?",
                (hint, proposal_id))
```

（stale→pending 的"重新生成"由生成端 create 新提案实现，不复活旧行——与 TC-PR-03 一致，故无 `unstale` 方法。）

配套：`_upsert_node` 增加类型校验使坏事实抛错（若 Task 3 未加）：`if not isinstance(f.get("types"), list): raise ValueError(...)`。

- [ ] **Step 4: 运行通过** — `pytest tests/test_proposal.py -v` → 7 PASS

- [ ] **Step 5: Commit** — `git add -A && git commit -m "feat(core): proposal queue state machine, atomic confirm"`

---

### Task 11: 单写者租约 + api 门面

**Files:**
- Create: `src/snowel_core/storage/lease.py`, `src/snowel_core/api.py`
- Modify: `src/snowel_core/__init__.py`
- Test: `tests/test_api.py`

**Interfaces:**
- Produces:
  - `lease.acquire(conn, holder: str, stale_after: float = 30.0) -> bool`；`renew(conn, holder)`；`release(conn, holder)`（过期判定 = 心跳时间戳早于 `now - stale_after`，即存活检测 C10）。
  - `api.SnowelAPI`：`init_project(path) -> SnowelAPI`（建库+迁移）、`open(path) -> SnowelAPI`、`close()`；组合 `proposals: ProposalQueue`；代理 `state_at` / `get_node` / `find_nodes` / `edges_of` / `descendants` / `rebuild` / `acquire_lease` / `renew_lease` / `release_lease`。三端唯一入口（铁律 1 / §10）。

- [ ] **Step 1: 写失败测试（TC-SH-04 / 05 核心层 + 门面冒烟）**

```python
# tests/test_api.py
from snowel_core import api as sapi
from snowel_core.storage import db, lease

def test_lease_single_writer(tmp_path):
    a = db.connect(tmp_path / "s.db"); db.migrate(a)
    assert lease.acquire(a, "web-1") is True
    b = db.connect(tmp_path / "s.db")
    assert lease.acquire(b, "cli-1") is False        # 活租约拒绝第二写者
    lease.release(a, "web-1")
    assert lease.acquire(b, "cli-1") is True
    a.close(); b.close()

def test_lease_recovers_after_holder_death(tmp_path):  # C10 存活检测
    a = db.connect(tmp_path / "s.db"); db.migrate(a)
    assert lease.acquire(a, "web-1", stale_after=0.05) is True
    a.close()                                        # 模拟崩溃：不再心跳
    import time; time.sleep(0.1)
    b = db.connect(tmp_path / "s.db")
    assert lease.acquire(b, "cli-1", stale_after=0.05) is True  # 过期租约可夺
    b.close()

def test_api_facade_end_to_end(tmp_path):
    core = sapi.SnowelAPI.init_project(tmp_path / "book")
    pid = core.proposals.create("scene", {"facts": [
        {"fact": "node", "id": "n1", "types": ["Character"], "name": "林晚",
         "props": {"core": {"motivation": "活下去", "lie": "x", "fear": "y", "arc": "z"}}}]})
    core.proposals.confirm(pid)
    n = core.get_node("n1")
    assert n["name"] == "林晚"
    assert core.find_nodes(name="林晚")[0]["id"] == "n1"
    core.rebuild()
    assert core.get_node("n1")["name"] == "林晚"     # rebuild 后状态一致
    core.close()
```

- [ ] **Step 2: 运行确认失败** — FAIL

- [ ] **Step 3: 实现 lease.py 与 api.py**

```python
# src/snowel_core/storage/lease.py
import time

def _now() -> float:
    return time.time()

def acquire(conn, holder: str, stale_after: float = 30.0) -> bool:
    from ..storage.db import transaction
    with transaction(conn):
        row = conn.execute("SELECT * FROM lease WHERE id=1").fetchone()
        if row and row["holder"] != holder and row["heartbeat_ts"] > _now() - stale_after:
            return False                             # 他人活租约
        conn.execute(
            "INSERT INTO lease(id, holder, heartbeat_ts) VALUES(1,?,?) "
            "ON CONFLICT(id) DO UPDATE SET holder=excluded.holder, "
            "heartbeat_ts=excluded.heartbeat_ts", (holder, _now()))
        return True

def renew(conn, holder: str) -> bool:
    cur = conn.execute("UPDATE lease SET heartbeat_ts=? WHERE id=1 AND holder=?",
                       (_now(), holder))
    return cur.rowcount == 1

def release(conn, holder: str) -> None:
    conn.execute("DELETE FROM lease WHERE id=1 AND holder=?", (holder,))
```

```python
# src/snowel_core/api.py
from pathlib import Path

from .proposal.queue import ProposalQueue
from .storage import db, lease, queries
from .storage.projector import rebuild as _rebuild

class SnowelAPI:
    def __init__(self, conn):
        self._conn = conn
        self.proposals = ProposalQueue(conn)

    @classmethod
    def init_project(cls, path) -> "SnowelAPI":
        p = Path(path); p.mkdir(parents=True, exist_ok=True)
        conn = db.connect(p / "snowel.db"); db.migrate(conn)
        return cls(conn)

    @classmethod
    def open(cls, path) -> "SnowelAPI":
        return cls(db.connect(Path(path) / "snowel.db"))

    def close(self):
        self._conn.close()

    # 只读查询（代理 storage.queries）
    def state_at(self, story_order: int):
        return queries.state_at(self._conn, story_order)

    def get_node(self, node_id):
        return queries.get_node(self._conn, node_id)

    def find_nodes(self, name=None, type=None):
        return queries.find_nodes(self._conn, name, type)

    def edges_of(self, node_id, direction="both"):
        return queries.edges_of(self._conn, node_id, direction)

    def descendants(self, node_id, kinds=None, max_depth=10):
        return queries.descendants(self._conn, node_id, kinds, max_depth)

    def rebuild(self):
        _rebuild(self._conn)

    # 租约（C10）
    def acquire_lease(self, holder: str, stale_after: float = 30.0) -> bool:
        return lease.acquire(self._conn, holder, stale_after)

    def renew_lease(self, holder: str) -> bool:
        return lease.renew(self._conn, holder)

    def release_lease(self, holder: str) -> None:
        lease.release(self._conn, holder)
```

```python
# src/snowel_core/__init__.py
from .api import SnowelAPI
__all__ = ["SnowelAPI"]
```

- [ ] **Step 4: 运行全量测试通过**

Run: `pytest -v` → Expected: 全部 PASS（storage 4 + projector 11 + queries 5 + ontology 4 + proposal 7 + api 3）

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "feat(core): writer lease and SnowelAPI facade"
```

---

## Self-Review 记录

- **Spec 覆盖**：D1（检查点/批量/重放）→ Task 3/5/6；D2（UUID+alias+多标签）→ Task 3/4/8；D3（注册式属性组/unmanaged/版本降级）→ Task 9；D4（地址+派生序+插入重算）→ Task 5；D5（draft/profiled+override）→ Task 4/9（active 显式裁剪）；D6/D7 部分 → D6 的 beat_merged 留后续计划（D7 否决/作废事件在 Task 10）；E1（事务规则）→ Task 1/10；E2（投影器唯一写入口）→ Task 3–7 全部物化集中在 projector.py；C5/C10 → Task 10/11；C7 → Task 4；C2 → Task 4。未覆盖项均已在"范围裁剪"表登记并有承接计划。
- **占位符扫描**：无 TBD/TODO；Task 7 Step 3 的伪代码段已明确标注"删掉换真代码"，执行者照做。
- **类型一致性**：`apply(conn)`/`rebuild(conn)`/`state_at(conn, story_order)`/`ProposalQueue(conn)` 签名在各任务间一致；事实集契约统一在文首定义。

## 执行注意

- 执行中发现计划有错：停下改本计划再继续，不现场发挥（spec-workflow 规约）。
- Task 3 Step 1 的测试事实列表里 EDGE_FACT 引用需指向实际存在的节点，执行者按断言修正测试数据（不修改被测行为）。

---

## 执行结果

本计划已于 2026-08-23 以 Subagent-Driven 方式执行完成：11 个任务 + 终审修复波，12 个提交（789846a..6334903），合入 dev-1.0.0，37/37 测试通过。执行遗留问题（L1–L4 及随行小项）与关键裁决记录于 `.superpowers/sdd/2026-08-23-snowel-core/progress.md`（ledger，git 忽略）——**下游计划拆解时必须在 preflight 中携带 L1–L4**。
