# tests/flow/test_inspiration.py
# 灵感层（TC-ON-12 / §4.7）+ ON-14 补锚 + L25 派生补强/两阶段恢复锚
import json

import pytest

from tests.conftest import FakeBackend
from snowel_core.storage import db, events, projector


def _gen_resp(facts=None, draft="生成稿"):
    return json.dumps({"draft": draft, "facts": facts or [],
                       "appeared": []}, ensure_ascii=False)


def _seed_beat(api):  # ON-14 定位节点（同 consistency/test_foreshadow.py 手法）
    with db.transaction(api._conn):
        events.append_event(api._conn, "proposal_confirmed", {
            "artifact_type": "t", "facts": [
                {"fact": "node", "id": "mb1", "types": ["MicroBeat"],
                 "name": "开场拍", "props": {
                     "address": {"volume": 1, "chapter": 1, "scene": 1,
                                 "beat": 1}}}]})
    projector.apply(api._conn)


def test_inspiration_preserved_and_derived(api):  # TC-ON-12
    iid = api.save_inspiration("Brainstorm 原话全文……")
    facts = [{"fact": "node", "id": "py1", "types": ["Premise"],
              "name": "两路追凶", "props": {}}]
    pid = api.ai_generate("premise", derive_from=[iid],
                          backend=FakeBackend([_gen_resp(facts=facts)]))
    api.confirm(pid)
    # 原话全文永久保留为 Layer 1 附属（props.inspiration.text）
    assert api.inspirations()[0]["text"] == "Brainstorm 原话全文……"
    # 提炼物有 DERIVED_FROM 边指回原话
    kinds = {e["kind"] for e in api.edges_of(iid)}
    assert "DERIVED_FROM" in kinds


def test_foreshadow_ai_origin_lifecycle(api):  # ON-14 补锚
    _seed_beat(api)
    pid = api.register_foreshadow("怀表", planted_at="mb1", origin="ai")
    api.confirm(pid)  # 入典 origin=="ai"
    node = api._conn.execute(
        "SELECT props FROM nodes WHERE name='怀表'").fetchone()
    assert json.loads(node["props"])["foreshadow"]["origin"] == "ai"
    pid2 = api.register_foreshadow("信笺", planted_at="mb1", origin="ai")
    api.proposals.reject(pid2, reason="重复")  # 不入典（提案否决既有语义回归）
    assert api._conn.execute(
        "SELECT COUNT(*) FROM nodes WHERE name='信笺'").fetchone()[0] == 0
    assert api.proposals.get(pid2)["status"] == "rejected"


def test_derive_from_validation_errors(api):  # §2.2 伴生测试
    # derive_from=["nope"] → ValueError；derive_from=[mb1（MicroBeat）] → ValueError
    _seed_beat(api)
    with pytest.raises(ValueError, match="Inspiration"):
        api.ai_generate("premise", derive_from=["nope"],
                        backend=FakeBackend([_gen_resp()]))
    with pytest.raises(ValueError, match="Inspiration"):
        api.ai_generate("premise", derive_from=["mb1"],
                        backend=FakeBackend([_gen_resp()]))


def test_derive_from_duplicate_ids_dedup(api):  # R5：入口去重
    iid = api.save_inspiration("灵感原话")
    facts = [{"fact": "node", "id": "py1", "types": ["Premise"],
              "name": "两路追凶", "props": {}}]
    pid = api.ai_generate("premise", derive_from=[iid, iid],
                          backend=FakeBackend([_gen_resp(facts=facts)]))
    assert json.loads(api.proposals.get(pid)["payload"])["derive_from"] == [iid]
    api.confirm(pid)
    n = api._conn.execute(
        "SELECT COUNT(*) FROM edges WHERE kind='DERIVED_FROM' "
        "AND src='py1' AND dst=?", (iid,)).fetchone()[0]
    assert n == 1  # 恰一条，无平行边


def test_recover_derived_from_heals_window(api):  # L25 两阶段崩溃恢复
    iid = api.save_inspiration("灵感原话")
    facts = [{"fact": "node", "id": "py1", "types": ["Premise"],
              "name": "两路追凶", "props": {}}]
    pid = api.ai_generate("premise", derive_from=[iid],
                          backend=FakeBackend([_gen_resp(facts=facts)]))
    api.proposals.confirm(pid)  # 直调 queue.confirm 绕过 api.confirm 补边段
    # = 天然制造两事务间崩溃窗口：产物已物化、边缺失
    assert api.get_node("py1") is not None
    n0 = api._conn.execute(
        "SELECT COUNT(*) FROM edges WHERE kind='DERIVED_FROM' "
        "AND src='py1' AND dst=?", (iid,)).fetchone()[0]
    assert n0 == 0
    assert api.recover_derived_from() == 1
    n1 = api._conn.execute(
        "SELECT COUNT(*) FROM edges WHERE kind='DERIVED_FROM' "
        "AND src='py1' AND dst=?", (iid,)).fetchone()[0]
    assert n1 == 1  # 边补上
    assert api.recover_derived_from() == 0  # 再跑幂等：无缺口返回 0


def test_recover_derived_from_noop_when_complete(api):
    iid = api.save_inspiration("灵感原话")
    facts = [{"fact": "node", "id": "py1", "types": ["Premise"],
              "name": "两路追凶", "props": {}}]
    pid = api.ai_generate("premise", derive_from=[iid],
                          backend=FakeBackend([_gen_resp(facts=facts)]))
    api.confirm(pid)  # 正常全流程：confirm 自带补边，无缺口
    assert api.recover_derived_from() == 0
