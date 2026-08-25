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
