# tests/consistency/test_retcon.py
import json
import pytest
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
    ev = api._conn.execute(
        "SELECT payload FROM events WHERE kind='retcon_applied'").fetchone()
    p = json.loads(ev["payload"])
    assert set(p) == {"renames", "track_updates", "impact"}   # 影响清单三键齐全
    assert p["renames"] == [] and p["track_updates"] == []
    assert p["impact"]["affected_proposals"] == [touched]     # P5：确认不重跑
    deps = [v for v in p["impact"]["violations"] if v["rule"] == "dependents"]
    assert deps and any(any(str(r).startswith("ch50:") for r in v["refs"])
                        for v in deps)                        # 正文提示（C9 面）
    contra = [v for v in p["impact"]["violations"]
              if v["rule"] == "contradiction"]
    assert contra and contra[0]["detail"]["old"] == 3         # 旧→新版事实
    assert contra[0]["detail"]["new"] == 9
    f = tmp_path / "chapters" / "ch50.md"                     # C9：旧正文不被自动改
    assert f.read_text(encoding="utf-8") == "积分兑换面板亮起。"
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


def test_retcon_rename_materializes_and_keeps_alias(api, tmp_path):  # renames 端到端
    _seed(api, tmp_path)
    out = retcon.propose_retcon(api, renames=[
        {"node_id": "m1", "old_name": "积分兑换", "new_name": "积分商城"}],
        reason="改名")
    deps = [v for v in out["impact"]["violations"] if v["rule"] == "dependents"]
    assert deps and any(any(str(r).startswith("ch50:") for r in v["refs"])
                        for v in deps)                # 旧名正文反查命中（C9 提示面）
    assert api.confirm_retcon(out["proposal_id"]) > 0
    assert api.get_node("m1")["name"] == "积分商城"    # 物化为新名
    ev = api._conn.execute(
        "SELECT payload FROM events WHERE kind='retcon_applied'").fetchone()
    p = json.loads(ev["payload"])
    assert p["renames"] == [{"node_id": "m1", "old_name": "积分兑换",
                             "new_name": "积分商城"}]  # 事件完整携带 renames
    alias = api._conn.execute(
        "SELECT alias FROM alias WHERE node_id='m1' AND source='retcon'"
    ).fetchone()
    assert alias["alias"] == "积分兑换"                # 旧名入 alias 可查


def test_retcon_propose_syncs_last_cascade(api):  # T10：confirm 响应 cascade 键数据面
    _seed(api, api._root)
    out = api.propose_retcon(facts=[
        {"fact": "node", "id": "m1", "types": ["Mechanism"], "name": "积分兑换",
         "props": {"mechanism": {"level": 9}}}], reason="等级体系重排")
    last = api.last_cascade()
    assert last["tier"] == "full"
    assert last["violations"] == out["impact"]["violations"]
    assert last["cascade_proposal_id"] is None       # retcon 不产 diff 提案


def test_confirm_rejects_retcon_proposal(api, tmp_path):  # 通用确认拦截锚定：无半应用
    _seed(api, tmp_path)
    out = retcon.propose_retcon(api, facts=[
        {"fact": "node", "id": "m1", "types": ["Mechanism"], "name": "积分兑换",
         "props": {"mechanism": {"level": 5}}}], reason="拦截验证")
    with pytest.raises(ValueError, match="confirm_retcon"):
        api.confirm(out["proposal_id"])
    assert api.proposals.get(out["proposal_id"])["status"] == "pending"  # 未半应用
