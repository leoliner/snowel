# tests/flow/test_generate.py
import json
from tests.conftest import FakeBackend
from snowel_core.flow import generate


def _gen_resp(facts=None, draft="生成稿"):
    return json.dumps({"draft": draft, "facts": facts or [],
                       "appeared": []}, ensure_ascii=False)


def test_ai_generate_composes_audits_and_proposes(api):  # E3 / TC-RT-04
    fake = FakeBackend([_gen_resp()])
    pid = api.ai_generate("premise", extra={"notes": "无限流"},
                          backend=fake)
    assert api.proposals.get(pid)["status"] == "pending"   # 永不直接落正典
    from snowel_core.retrieval import audit
    assert audit.recent(api._conn)[0]["strategy"] == "generic"  # 内部第一步可观察
    assert "无限流" in fake.calls[0]["prompt"]


def test_ai_generate_rejects_unknown_type(api):
    import pytest
    with pytest.raises(ValueError, match="premise"):
        api.ai_generate("nope", backend=FakeBackend([]))


def test_rejected_digest_injected(api):  # TC-PR-08 / D7
    p1 = api.proposals.create("premise", {"draft": "角色A习得技能S"})
    api.proposals.reject(p1, reason="重复")
    fake = FakeBackend([_gen_resp()])
    api.ai_generate("premise", backend=fake)
    assert "角色A习得技能S" in fake.calls[0]["prompt"]   # 近期被否摘要进提示词


def test_microbeat_group_confirm_with_exclude(api):  # TC-PR-09 / C3
    facts = [{"fact": "node", "id": f"mb{i}", "types": ["MicroBeat"],
              "name": f"拍{i}", "props": {"chapter": "ch1",
                                          "keywords": [f"k{i}"]}}
             for i in range(3)]
    fake = FakeBackend([_gen_resp(facts)])
    pid = api.ai_generate("microbeat_group",
                          locate={"chapter": "ch1"}, backend=fake)
    api.confirm(pid, exclude=["mb1"])                     # 整组确认，剔除 mb1
    ids = {r["id"] for r in api._conn.execute("SELECT id FROM nodes")}
    assert ids == {"mb0", "mb2"}


def _seed(conn, facts):
    from snowel_core.storage import db, events, projector
    with db.transaction(conn):
        events.append_event(conn, "proposal_confirmed",
                            {"artifact_type": "seed", "facts": facts})
        projector.apply(conn)


_CH1 = {"fact": "node", "id": "ch1", "types": ["Chapter"],
        "name": "第1章", "props": {}}
_SCENE = {"fact": "node", "id": "sc1", "types": ["Scene"], "name": "雨夜追凶",
          "props": {"chapter": "ch1", "required_elements": ["红伞", "码头"],
                    "characters": []}}


def test_prose_payload_fits_confirm_chain(api):  # 修复波 F1：C1 确认链契约
    _seed(api._conn, [_CH1, _SCENE])
    fake = FakeBackend([_gen_resp(draft="正文内容")])
    pid = api.ai_generate("prose", locate={"chapter": "ch1"}, backend=fake)
    api.confirm(pid)                                      # 确认即代写文件（不再 KeyError）
    f = api._root / "chapters" / "ch1.md"
    assert "正文内容" in f.read_text(encoding="utf-8")
    kinds = [r["kind"] for r in api._conn.execute(
        "SELECT kind FROM events ORDER BY seq")]
    assert kinds[-2:] == ["proposal_confirmed", "prose_hash_registered"]


def test_prose_locate_query_from_scene_card(api):  # 修复波 F2：L9 持久化
    _seed(api._conn, [_CH1, _SCENE])
    fake = FakeBackend([_gen_resp()])
    api.ai_generate("prose", locate={"chapter": "ch1"}, backend=fake)
    from snowel_core.retrieval import audit
    loc = json.loads(audit.recent(api._conn)[0]["locate"])
    assert loc["query"] == "雨夜追凶 红伞 码头"      # 场景卡 name+required_elements
