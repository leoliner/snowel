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
    assert {e["id"] for e in p1["edges"]} == {"e1"}
    p2 = queries.state_at(conn, 1)
    assert {n["id"] for n in p2["nodes"]} == {"mb1", "mb2"}
    assert {e["id"] for e in p2["edges"]} == {"e1"}
    p3 = queries.state_at(conn, 2)
    assert {e["id"] for e in p3["edges"]} == set()      # valid_until=1 已过期


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
    assert s["nodes"][0]["core_level"] == 9             # 取当前生效版，不是历史原版
