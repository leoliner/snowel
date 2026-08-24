# tests/flow/test_volume.py
import json
from tests.conftest import FakeBackend
from snowel_core.flow import snowflake
from snowel_core.storage import db, events, projector


def _seed_v1(api):
    """卷一：英雄存活升级、队友死亡、伏笔未回收。"""
    facts = [
        {"fact": "node", "id": "v1", "types": ["Volume"], "name": "卷一",
         "props": {}},
        {"fact": "node", "id": "v2", "types": ["Volume"], "name": "卷二",
         "props": {}},
        {"fact": "node", "id": "hero", "types": ["Character"], "name": "林晚",
         "props": {"core": {"level": 1}}},
        {"fact": "node", "id": "mate", "types": ["Character"], "name": "旧队友",
         "props": {"core": {"death_beat": "mb9"}}},
        {"fact": "node", "id": "mb9", "types": ["MicroBeat"], "name": "终拍",
         "props": {"address": {"volume": 1, "chapter": 9, "scene": 1, "beat": 1}}},
        {"fact": "node", "id": "mech", "types": ["Mechanism"], "name": "积分兑换",
         "props": {"mechanism": {"level": 1}}},
        {"fact": "node", "id": "fs1", "types": ["Foreshadow"], "name": "怀表",
         "props": {}},
    ]
    with db.transaction(api._conn):
        events.append_event(api._conn, "proposal_confirmed", {
            "artifact_type": "t", "facts": facts})
        events.append_event(api._conn, "proposal_confirmed", {
            "artifact_type": "retcon", "facts": [   # C9：等级 retcon 到 9
                {"fact": "node", "id": "mech", "types": ["Mechanism"],
                 "name": "积分兑换", "props": {"mechanism": {"level": 9}}}]})
        projector.apply(api._conn)


def test_volume_start_state_replays(api):  # TC-FL-01 / TC-FL-02 / C8 / C9
    _seed_v1(api)
    s = api.volume_start_state("v2")
    assert "林晚" in s["alive"] and "旧队友" in s["dead"]   # 死者不在场
    assert s["mechanisms"] == [{"name": "积分兑换", "level": 9}]  # 取升级后（修正版）
    assert s["open_foreshadows"] == ["怀表"]


def test_expand_volume_feeds_start_state(api):  # 卷首状态进卷级上下文
    _seed_v1(api)
    fake = FakeBackend([json.dumps({"draft": "主题", "facts": [], "appeared": []}),
                        json.dumps({"draft": "三幕", "facts": [], "appeared": []})])
    pids = api.expand_volume("v2", backend=fake)
    assert [api.proposals.get(p)["kind"] for p in pids] == ["volume_theme",
                                                            "volume_acts"]
    assert "积分兑换" in fake.calls[0]["prompt"]     # 世界状态注入卷级生成
    assert "=== 卷首世界状态 ===" in fake.calls[0]["prompt"]  # E1 裁决：start_state 分节头
    assert "旧队友" not in fake.calls[0]["prompt"] or "dead" in fake.calls[0]["prompt"]
