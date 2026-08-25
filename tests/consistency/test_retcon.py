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
