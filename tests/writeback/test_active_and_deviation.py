# tests/writeback/test_active_and_deviation.py
import json
from tests.conftest import FakeBackend
from snowel_core.storage import db, events, projector
from snowel_core.writeback import deviation, mirror


def _profiled_hero(api):
    with db.transaction(api._conn):
        events.append_event(api._conn, "proposal_confirmed", {
            "artifact_type": "t", "facts": [
                {"fact": "node", "id": "hero", "types": ["Character"],
                 "name": "林晚", "completeness": "profiled",
                 "props": {"core": {"motivation": "a", "lie": "b",
                                    "fear": "c", "arc": "d"}}}]})
        projector.apply(api._conn)


def test_appeared_activates_profiled_only(api):  # TC-ON-06 / P7
    _profiled_hero(api)
    with db.transaction(api._conn):
        events.append_event(api._conn, "auto_canonized", {
            "facts": [], "source": {"chapter_id": "ch1", "hash": "h"},
            "appeared": ["hero"]})
        projector.apply(api._conn)
    assert api.get_node("hero")["completeness"] == "active"


def test_appeared_does_not_skip_draft(api):  # D5 链式：draft 登场仍是 draft
    with db.transaction(api._conn):
        events.append_event(api._conn, "proposal_confirmed", {
            "artifact_type": "t", "facts": [
                {"fact": "node", "id": "hero", "types": ["Character"],
                 "name": "林晚", "props": {}}]})
        events.append_event(api._conn, "auto_canonized", {
            "facts": [], "source": {}, "appeared": ["hero"]})
        projector.apply(api._conn)
    assert api.get_node("hero")["completeness"] == "draft"


def test_deviation_report(api, tmp_path):  # TC-FL-05：4/6 + 缺"雨夜"
    with db.transaction(api._conn):
        events.append_event(api._conn, "proposal_confirmed", {
            "artifact_type": "t", "facts": [
                {"fact": "node", "id": "sc1", "types": ["Scene"], "name": "场景",
                 "props": {"chapter": "ch1", "required_elements": ["雨夜", "电话亭"]}},
                *[{"fact": "node", "id": f"mb{i}", "types": ["MicroBeat"],
                   "name": f"节拍{i}",
                   "props": {"chapter": "ch1",
                             "keywords": ["关键词A"] if i < 4 else ["关键词B"]}}
                  for i in range(6)]]})
        projector.apply(api._conn)
    mirror.write_prose(api._conn, tmp_path, "ch1", "关键词A反复出现。")
    r = deviation.report(api._conn, "ch1")
    assert r == {"microbeat": {"done": 4, "total": 6},
                 "missing_elements": ["雨夜", "电话亭"]}


def test_extract_returns_deviation(api, tmp_path):
    _profiled_hero(api)
    mirror.write_prose(api._conn, tmp_path, "ch1", "正文")
    resp = json.dumps({"facts": [], "appeared": ["hero"]}, ensure_ascii=False)
    r = api.extract_and_writeback("ch1", backend=FakeBackend([resp]))
    assert "deviation" in r and r["deviation"]["microbeat"] is None


def test_all_high_chapter_activates_via_proposal(api, tmp_path):  # 修环 1：全 high 章经提案确认激活（D5 补洞）
    _profiled_hero(api)
    mirror.write_prose(api._conn, tmp_path, "ch1", "正文")
    resp = json.dumps({"facts": [   # 数字事实 → numeric_high 强转 high：无 auto_canonized 事件
        {"sensitivity": "low", "fact": {
            "fact": "node", "id": "n-level", "types": ["Mechanism"],
            "name": "等级", "props": {"core": {"level": 3}}}}],
        "appeared": ["hero"]}, ensure_ascii=False)
    r = api.extract_and_writeback("ch1", backend=FakeBackend([resp]))
    assert r["proposal_id"] is not None and r["auto_event_seq"] is None
    api.confirm(r["proposal_id"])  # appeared 须随提案载荷穿透到 proposal_confirmed
    assert api.get_node("hero")["completeness"] == "active"
