# tests/flow/test_snowflake.py
import json
from tests.conftest import FakeBackend
from snowel_core.flow import snowflake
from snowel_core.storage import db, events, projector


def _seed_profiled_hero(api):
    with db.transaction(api._conn):
        events.append_event(api._conn, "proposal_confirmed", {
            "artifact_type": "characters", "facts": [
                {"fact": "node", "id": "hero", "types": ["Character"],
                 "name": "林晚", "completeness": "profiled",
                 "props": {"core": {"motivation": "活下来", "lie": "没人救",
                                    "fear": "深渊", "arc": "信任"}}},
                {"fact": "node", "id": "sc1", "types": ["Scene"], "name": "雨夜",
                 "props": {"chapter": "ch1", "characters": ["hero"],
                           "required_elements": ["雨夜"]}}]})
        projector.apply(api._conn)


def _resp(draft):
    return json.dumps({"draft": draft, "facts": [], "appeared": []},
                      ensure_ascii=False)


def test_expand_chapter_reuses_profile_facts(api):  # TC-FL-04：受限展开
    _seed_profiled_hero(api)
    fake = FakeBackend([_resp("意图"), _resp("微节拍组"), _resp("正文")])
    pids = api.expand_chapter("ch1", backend=fake)
    assert len(pids) == 3
    kinds = [api.proposals.get(p)["kind"] for p in pids]
    assert kinds == ["chapter_intent", "microbeat_group", "prose"]
    prose_prompt = fake.calls[2]["prompt"]
    assert "活下来" in prose_prompt            # 档案直接拉取复用（现成，不重新生成）
    assert "生成角色档案" not in prose_prompt


def test_deviation_attached_after_prose_confirm(api, tmp_path):  # C12 数据流闭环
    _seed_profiled_hero(api)
    facts = [{"fact": "node", "id": "mb0", "types": ["MicroBeat"],
              "name": "拍0", "props": {"chapter": "ch1", "keywords": ["雨夜"]}}]
    fake = FakeBackend([_resp("i"), json.dumps(
        {"draft": "组", "facts": facts, "appeared": []}, ensure_ascii=False),
        _resp("正文")])
    pids = api.expand_chapter("ch1", backend=fake)
    api.confirm(pids[1])                          # 微节拍组确认
    from snowel_core.writeback import mirror
    mirror.write_prose(api._conn, tmp_path, "ch1", "干燥的白天。")
    r = api.deviation("ch1")
    assert r == {"microbeat": {"done": 0, "total": 1},
                 "missing_elements": ["雨夜"]}
