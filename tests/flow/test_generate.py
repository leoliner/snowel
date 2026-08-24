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
