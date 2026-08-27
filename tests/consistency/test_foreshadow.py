# tests/consistency/test_foreshadow.py
import json
import pytest
from snowel_core.consistency import foreshadow
from snowel_core.storage import db, events, projector


def _seed_beat(api):
    with db.transaction(api._conn):
        events.append_event(api._conn, "proposal_confirmed", {
            "artifact_type": "t", "facts": [
                {"fact": "node", "id": "mb1", "types": ["MicroBeat"],
                 "name": "开场拍", "props": {
                     "address": {"volume": 1, "chapter": 1, "scene": 1,
                                 "beat": 1}}}]})
    projector.apply(api._conn)


def test_register_foreshadow_author(api):
    _seed_beat(api)
    pid = api.register_foreshadow("怀表", planted_at="mb1", note="第3章回收")
    row = api.proposals.get(pid)
    assert row["kind"] == "foreshadow"
    api.confirm(pid)
    node = api._conn.execute(
        "SELECT props FROM nodes WHERE name='怀表'").fetchone()
    p = json.loads(node["props"])
    assert p["foreshadow"]["planted_at"] == "mb1"
    assert p["foreshadow"]["origin"] == "author"


def test_register_foreshadow_validates(api):
    _seed_beat(api)
    with pytest.raises(ValueError, match="planted_at"):
        api.register_foreshadow("怀表", planted_at="nope")
    with pytest.raises(ValueError, match="origin"):
        api.register_foreshadow("怀表", planted_at="mb1", origin="ghost")


def _seed_beats(api):
    with db.transaction(api._conn):
        events.append_event(api._conn, "proposal_confirmed", {
            "artifact_type": "t", "facts": [
                {"fact": "node", "id": "mb1", "types": ["MicroBeat"],
                 "name": "拍1", "props": {"address": {"volume": 1, "chapter": 2,
                                                      "scene": 1, "beat": 3}}},
                {"fact": "node", "id": "mb2", "types": ["MicroBeat"],
                 "name": "拍2", "props": {"address": {"volume": 1, "chapter": 2,
                                                      "scene": 1, "beat": 4}}},
                {"fact": "node", "id": "mb3", "types": ["MicroBeat"],
                 "name": "拍3", "props": {"address": {"volume": 1, "chapter": 2,
                                                      "scene": 1, "beat": 5}}}]})
    projector.apply(api._conn)


def test_beat_merged_migrates_foreshadow(api):  # TC-ON-08 / D6
    _seed_beats(api)
    pid = api.register_foreshadow("怀表", planted_at="mb1")
    api.confirm(pid)
    fid = api._conn.execute(
        "SELECT id FROM nodes WHERE name='怀表'").fetchone()["id"]
    api.merge_beats("mb1", "mb2")
    # 恰一条 beat_merged 事件（R1：载荷自含迁移清单）
    assert api._conn.execute(
        "SELECT COUNT(*) FROM events WHERE kind='beat_merged'"
    ).fetchone()[0] == 1
    payload = json.loads(api._conn.execute(
        "SELECT payload FROM events WHERE kind='beat_merged'").fetchone()["payload"])
    assert payload["source_beat_id"] == "mb1"
    assert payload["target_beat_id"] == "mb2"
    assert payload["moved_foreshadows"] == [
        {"foreshadow_id": fid, "old": "mb1", "new": "mb2"}]
    # 源拍失效、目标拍不动
    assert api.get_node("mb1") is None
    assert api.get_node("mb1", active_only=False)["active"] == 0
    assert api.get_node("mb2")["active"] == 1
    # 伏笔引用已迁移：不再指向失效源拍
    p = json.loads(api.get_node(fid, active_only=False)["props"])
    assert p["foreshadow"]["planted_at"] == "mb2"
    # 同 scene 剩余拍的派生序重算连续（无空洞、不漂移）
    so = {r["id"]: r["story_order"] for r in api._conn.execute(
        "SELECT id, story_order FROM nodes WHERE id IN ('mb1','mb2','mb3')")}
    assert (so["mb2"], so["mb3"]) == (0, 1)
    assert so["mb1"] is None
    # 统计视图不报死链：伏笔仍只见于 planted 状态、指向 mb2
    item = next(i for i in api.stats_foreshadow()["items"] if i["id"] == fid)
    assert item["planted_at"] == "mb2" and item["status"] == "planted"


def test_foreshadow_chapter_location_view_consistent(api):  # ON-13 补锚
    # planted_at=Chapter 节点 id 注册伏笔 → stats_foreshadow 可查（与 MicroBeat 定位同视图）
    _seed_beat(api)
    with db.transaction(api._conn):
        events.append_event(api._conn, "proposal_confirmed", {
            "artifact_type": "t", "facts": [
                {"fact": "node", "id": "chx", "types": ["Chapter"],
                 "name": "第二章", "props": {"address": {"volume": 1, "chapter": 2,
                                                         "scene": 0, "beat": 0}}}]})
    projector.apply(api._conn)
    pid = api.register_foreshadow("铃铛", planted_at="chx", payoff_beat="mb1")
    api.confirm(pid)
    fid = api._conn.execute(
        "SELECT id FROM nodes WHERE name='铃铛'").fetchone()["id"]
    item = next(i for i in api.stats_foreshadow()["items"] if i["id"] == fid)
    assert item["planted_at"] == "chx"
    assert item["payoff_beat"] == "mb1"
    assert item["status"] == "paid"


def test_delete_beat_rejects_foreshadow_reference(api):  # TC-ON-17 前半
    # 伏笔 planted_at=mb1 已确认 → delete_beat("mb1") ValueError
    _seed_beat(api)
    pid = api.register_foreshadow("怀表", planted_at="mb1")
    api.confirm(pid)
    n_events = api._conn.execute(
        "SELECT COUNT(*) FROM events").fetchone()[0]
    with pytest.raises(ValueError, match="该拍承载 1 个伏笔引用"):
        api.delete_beat("mb1")
    # 拒绝不留半事件：事件日志无新增（事务原子）
    assert api._conn.execute(
        "SELECT COUNT(*) FROM events").fetchone()[0] == n_events


def test_delete_beat_empty_succeeds(api):  # TC-ON-17 后半
    # merge_beats(mb1, mb2) 迁移伏笔 → delete_beat("mb1") 成功
    _seed_beats(api)
    pid = api.register_foreshadow("怀表", planted_at="mb1")
    api.confirm(pid)
    fid = api._conn.execute(
        "SELECT id FROM nodes WHERE name='怀表'").fetchone()["id"]
    api.merge_beats("mb1", "mb2")
    seq = api.delete_beat("mb1", reason="拍合并后清理空源拍")
    # 恰一条 beat_deleted；reason 透传入载荷
    rows = api._conn.execute(
        "SELECT seq, payload FROM events WHERE kind='beat_deleted'").fetchall()
    assert len(rows) == 1 and rows[0]["seq"] == seq
    assert json.loads(rows[0]["payload"]) == {
        "beat_id": "mb1", "reason": "拍合并后清理空源拍"}
    # mb1 失效、story_order 清 NULL；同 scene 剩余拍派生序重算连续
    assert api.get_node("mb1") is None
    assert api.get_node("mb1", active_only=False)["active"] == 0
    so = {r["id"]: r["story_order"] for r in api._conn.execute(
        "SELECT id, story_order FROM nodes WHERE id IN ('mb1','mb2','mb3')")}
    assert so["mb1"] is None
    assert (so["mb2"], so["mb3"]) == (0, 1)
    # 伏笔引用不受删除影响：仍指向承接拍 mb2
    p = json.loads(api.get_node(fid, active_only=False)["props"])
    assert p["foreshadow"]["planted_at"] == "mb2"


def test_delete_beat_validates(api):  # 校验面
    _seed_beat(api)
    with db.transaction(api._conn):
        events.append_event(api._conn, "proposal_confirmed", {
            "artifact_type": "t", "facts": [
                {"fact": "node", "id": "chA", "types": ["Chapter"],
                 "name": "一章", "props": {"address": {"volume": 1, "chapter": 1,
                                                       "scene": 0, "beat": 0}}}]})
    projector.apply(api._conn)
    n_events = api._conn.execute(
        "SELECT COUNT(*) FROM events").fetchone()[0]
    with pytest.raises(ValueError, match="不存在"):
        api.delete_beat("nope")
    with pytest.raises(ValueError, match="MicroBeat"):
        api.delete_beat("chA")
    # 校验拒绝不落事件
    assert api._conn.execute(
        "SELECT COUNT(*) FROM events").fetchone()[0] == n_events


def test_merge_beats_validates(api):  # D6 校验面
    _seed_beat(api)
    with db.transaction(api._conn):
        events.append_event(api._conn, "proposal_confirmed", {
            "artifact_type": "t", "facts": [
                {"fact": "node", "id": "chA", "types": ["Chapter"],
                 "name": "一章", "props": {"address": {"volume": 1, "chapter": 1,
                                                       "scene": 0, "beat": 0}}}]})
    projector.apply(api._conn)
    with pytest.raises(ValueError, match="不能相同"):
        api.merge_beats("mb1", "mb1")
    with pytest.raises(ValueError, match="不存在"):
        api.merge_beats("nope", "mb1")
    with pytest.raises(ValueError, match="MicroBeat"):
        api.merge_beats("chA", "mb1")
