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


def test_dependents_prompt_surface_skips_inactive_peer(core_conn, tmp_path):  # L17 锚点
    """提示面口径（默认仅活跃实体）：对端已撤回的边不算"既有依赖"。"""
    with db.transaction(core_conn):
        events.append_event(core_conn, "proposal_confirmed", {
            "artifact_type": "t", "facts": [
                {"fact": "node", "id": "sys", "types": ["Concept"],
                 "name": "轮回游戏", "props": {}},
                {"fact": "node", "id": "m1", "types": ["Mechanism"],
                 "name": "积分兑换", "props": {}},
                {"fact": "node", "id": "gone", "types": ["Concept"],
                 "name": "寒潮营地", "props": {}},
                {"fact": "edge", "id": "e1", "src": "sys", "dst": "m1",
                 "kind": "REQUIRES", "props": {}},
                {"fact": "edge", "id": "e2", "src": "m1", "dst": "gone",
                 "kind": "USES", "props": {}}]})
    projector.apply(core_conn)
    with db.transaction(core_conn):
        events.append_event(core_conn, "retraction",
                            {"target": "node", "target_id": "gone"})
    projector.apply(core_conn)
    vs = engine.run(core_conn, [{"kind": "node", "seq": 3, "fact": {
        "id": "m1", "types": ["Mechanism"], "name": "积分兑换",
        "props": {"level": 9}}}], "full")
    dep = [v for v in vs if v["rule"] == "dependents"]
    assert dep and dep[0]["level"] == "minor"
    assert "e1" in dep[0]["refs"] and "sys" in dep[0]["refs"]   # 活跃对端照常命中
    assert "e2" not in dep[0]["refs"]                           # 已撤回对端不算既有依赖
    assert "gone" not in dep[0]["refs"] and "寒潮营地" not in dep[0]["message"]


def test_dependents_retraction_reads_retracted_row(core_conn, tmp_path):  # L17 锚点
    """retraction 反查被撤条目自身（active=0 前 canon 可读）：边与正文引用照常命中。"""
    _seed(core_conn, tmp_path)
    with db.transaction(core_conn):
        events.append_event(core_conn, "retraction",
                            {"target": "node", "target_id": "m1"})
    projector.apply(core_conn)
    vs = engine.run(core_conn, [{"kind": "retraction", "seq": 3,
                                 "fact": {"target": "node",
                                          "target_id": "m1"}}], "full")
    dep = [v for v in vs if v["rule"] == "dependents"]
    assert dep and "e1" in dep[0]["refs"] and "sys" in dep[0]["refs"]  # 边 + 对端反查
    assert any(r.startswith("ch50:") for r in dep[0]["refs"])          # 正文引用
    assert "轮回游戏" in dep[0]["message"]
