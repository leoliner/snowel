# tests/test_projector.py
import json
from snowel_core.storage import db, events, projector

NODE_FACT = {"fact": "node", "id": "n-linwan", "types": ["Character"],
             "name": "林晚", "props": {"core": {"motivation": "活下去"}}}
NODE_X_FACT = {"fact": "node", "id": "n-x", "types": ["Concept"], "name": "玩家", "props": {}}
EDGE_FACT = {"fact": "edge", "id": "e-1", "src": "n-linwan", "dst": "n-x",
             "kind": "IS_A", "props": {}}

def _confirmed(conn, facts, artifact="scene"):
    with db.transaction(conn) as tx:
        events.append_event(tx, "proposal_confirmed",
                        {"proposal_id": "p1", "artifact_type": artifact, "facts": facts})

def test_apply_materializes_node_and_edge(tmp_path):
    conn = db.connect(tmp_path / "s.db"); db.migrate(conn)
    _confirmed(conn, [NODE_FACT, NODE_X_FACT, EDGE_FACT])
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

def _ev(conn, kind, payload):
    with db.transaction(conn) as tx:
        events.append_event(tx, kind, payload)

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

def _addr_node(nid, name, addr):
    return {"fact": "node", "id": nid, "types": ["Chapter"], "name": name,
            "props": {"address": addr}}

def test_story_order_stable_on_insertion(tmp_path):  # TC-ON-09 / D4
    conn = db.connect(tmp_path / "s.db"); db.migrate(conn)
    _confirmed(conn, [
        _addr_node("ch2", "第二章", {"volume": 1, "chapter": 2, "scene": 0, "beat": 0}),
        _addr_node("ch3", "第三章", {"volume": 1, "chapter": 3, "scene": 0, "beat": 0}),
    ])
    projector.apply(conn)
    so = {r["id"]: r["story_order"] for r in conn.execute(
        "SELECT id, story_order FROM nodes WHERE id LIKE 'ch%'")}
    assert so["ch2"] < so["ch3"]
    # 插章：ch3 让位到 chapter 4、新章占 chapter 3
    _ev(conn, "revision_applied", {"structure_changes": [
        {"op": "move", "node_id": "ch3", "address": {"volume": 1, "chapter": 4,
         "scene": 0, "beat": 0}}]})
    with db.transaction(conn) as tx:
        events.append_event(tx, "proposal_confirmed", {"proposal_id": "p2",
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

def test_rebuild_reproduces_identical_state(tmp_path):  # D1/TC-EV-05
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
    after = [tuple(r) for r in conn.execute(
        "SELECT * FROM nodes ORDER BY id")]
    assert before == after
    assert conn.execute("SELECT COUNT(*) FROM edges").fetchone()[0] == edge_before
    assert conn.execute("SELECT seq FROM checkpoint WHERE id=1").fetchone()["seq"] == \
        events.head_seq(conn)
