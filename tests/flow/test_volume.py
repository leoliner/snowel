# tests/flow/test_volume.py
import json
from tests.conftest import FakeBackend
from snowel_core.flow import snowflake
from snowel_core.storage import db, events, projector


def _seed_v1(api):
    """卷一：英雄存活升级、队友死亡、伏笔一未回收一已回收。"""
    facts = [
        {"fact": "node", "id": "v1", "types": ["Volume"], "name": "卷一",
         "props": {"address": {"volume": 1, "chapter": 0, "scene": 0, "beat": 0}}},
        {"fact": "node", "id": "v2", "types": ["Volume"], "name": "卷二",
         "props": {"address": {"volume": 2, "chapter": 0, "scene": 0, "beat": 0}}},
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
        {"fact": "node", "id": "fs2", "types": ["Foreshadow"], "name": "旧信",
         "props": {"core": {"payoff_beat": "mb9"}}},  # 已回收（payoff=卷一末拍）
    ]
    with db.transaction(api._conn):
        events.append_event(api._conn, "proposal_confirmed", {
            "artifact_type": "t", "facts": facts})
        events.append_event(api._conn, "proposal_confirmed", {
            "artifact_type": "retcon", "facts": [   # C9：等级 retcon 到 9
                {"fact": "node", "id": "mech", "types": ["Mechanism"],
                 "name": "积分兑换", "props": {"mechanism": {"level": 9}}}]})
        projector.apply(api._conn)


def _seed_rolling(api):
    """三卷乱序推进：v1 已完（末拍死亡），v3 已有拍与编址事实，展开 v2。"""
    facts = [
        {"fact": "node", "id": "v1", "types": ["Volume"], "name": "卷一",
         "props": {"address": {"volume": 1, "chapter": 0, "scene": 0, "beat": 0}}},
        {"fact": "node", "id": "v2", "types": ["Volume"], "name": "卷二",
         "props": {"address": {"volume": 2, "chapter": 0, "scene": 0, "beat": 0}}},
        {"fact": "node", "id": "v3", "types": ["Volume"], "name": "卷三",
         "props": {"address": {"volume": 3, "chapter": 0, "scene": 0, "beat": 0}}},
        {"fact": "node", "id": "hero", "types": ["Character"], "name": "林晚",
         "props": {"core": {"level": 1}}},
        {"fact": "node", "id": "mate", "types": ["Character"], "name": "旧队友",
         "props": {"core": {"death_beat": "mb1"}}},
        {"fact": "node", "id": "mb1", "types": ["MicroBeat"], "name": "卷一末拍",
         "props": {"address": {"volume": 1, "chapter": 9, "scene": 1, "beat": 1}}},
        {"fact": "node", "id": "mb3", "types": ["MicroBeat"], "name": "卷三拍",
         "props": {"address": {"volume": 3, "chapter": 1, "scene": 1, "beat": 1}}},
        {"fact": "node", "id": "mech1", "types": ["Mechanism"], "name": "v1机制",
         "props": {"mechanism": {"level": 5}}},
        {"fact": "node", "id": "mech3", "types": ["Mechanism"], "name": "v3机制",
         "props": {"address": {"volume": 3, "chapter": 1, "scene": 1, "beat": 2},
                   "mechanism": {"level": 7}}},
    ]
    with db.transaction(api._conn):
        events.append_event(api._conn, "proposal_confirmed", {
            "artifact_type": "t", "facts": facts})
        projector.apply(api._conn)


def test_volume_start_state_replays(api):  # TC-FL-01 / TC-FL-02 / C8 / C9
    _seed_v1(api)
    s = api.volume_start_state("v2")
    assert "林晚" in s["alive"] and "旧队友" in s["dead"]   # 死者不在场
    assert s["mechanisms"] == [{"name": "积分兑换", "level": 9}]  # 取升级后（修正版）
    assert s["open_foreshadows"] == ["怀表"]   # 已回收伏笔（payoff ≤ end）剔除


def test_volume_end_scoped_to_prior_volumes(api):  # C8：end 截断到目标卷之前
    _seed_rolling(api)
    s = api.volume_start_state("v2")
    assert s["story_order"] == 1                 # 上一卷末拍，而非全图最大拍
    assert "旧队友" in s["dead"] and "旧队友" not in s["alive"]  # v1 末拍死亡生效
    assert [m["name"] for m in s["mechanisms"]] == ["v1机制"]   # v3 的事实在卷二不可见


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
