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
