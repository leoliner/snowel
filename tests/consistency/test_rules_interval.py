# tests/consistency/test_rules_interval.py
from snowel_core.consistency import engine, rules
from snowel_core.storage import db, events, projector

engine.register("interval_overlap", rules.interval_overlap, tiers=("full",))
engine.register("growth_guardrail", rules.growth_guardrail, tiers=("full",))
engine.register("track_ratchet", rules.track_ratchet, tiers=("full",))


def _seed(conn):
    with db.transaction(conn):
        events.append_event(conn, "proposal_confirmed", {
            "artifact_type": "t", "facts": [
                {"fact": "node", "id": "a", "types": ["Character"], "name": "a",
                 "props": {}},
                {"fact": "node", "id": "b", "types": ["Concept"], "name": "b",
                 "props": {}},
                {"fact": "node", "id": "mb1", "types": ["MicroBeat"], "name": "1",
                 "props": {"address": {"volume": 1, "chapter": 1, "scene": 1,
                                       "beat": 1}}},
                {"fact": "node", "id": "mb5", "types": ["MicroBeat"], "name": "5",
                 "props": {"address": {"volume": 1, "chapter": 5, "scene": 1,
                                       "beat": 1}}},
                {"fact": "node", "id": "mb9", "types": ["MicroBeat"], "name": "9",
                 "props": {"address": {"volume": 1, "chapter": 9, "scene": 1,
                                       "beat": 1}}},
                {"fact": "edge", "id": "old1", "src": "a", "dst": "b",
                 "kind": "PARTICIPATES",
                 "props": {"valid_from_beat": "mb1", "valid_until_beat": "mb5"}}]})
    projector.apply(conn)


def test_interval_overlap_detected(core_conn):  # TC-CC-03
    _seed(core_conn)
    vs = engine.run(core_conn, [{"kind": "edge", "seq": 2, "fact": {
        "id": "new1", "src": "a", "dst": "b", "kind": "PARTICIPATES",
        "props": {"valid_from_beat": "mb5", "valid_until_beat": "mb9"}}}],
        "full")
    hit = [v for v in vs if v["rule"] == "interval_overlap"]
    assert hit and "old1" in hit[0]["refs"] and "new1" in hit[0]["refs"]


def test_interval_overlap_open_ended_existing(core_conn):  # 回归：开区间既有边（valid_until NULL）
    _seed(core_conn)
    with db.transaction(core_conn):  # 既有边 [mb1, +∞)：NULL 不得被撤回哨兵滤掉
        events.append_event(core_conn, "proposal_confirmed", {
            "artifact_type": "t", "facts": [
                {"fact": "edge", "id": "open1", "src": "a", "dst": "b",
                 "kind": "PARTICIPATES", "props": {"valid_from_beat": "mb1"}}]})
    projector.apply(core_conn)
    vs = engine.run(core_conn, [{"kind": "edge", "seq": 3, "fact": {
        "id": "new2", "src": "a", "dst": "b", "kind": "PARTICIPATES",
        "props": {"valid_from_beat": "mb5", "valid_until_beat": "mb9"}}}],
        "full")
    hit = [v for v in vs if v["rule"] == "interval_overlap"
           and "open1" in v["refs"]]
    assert hit and "new2" in hit[0]["refs"]


def test_growth_guardrail_warns_not_blocks(core_conn):  # TC-ON-16
    vs = engine.run(core_conn, [{"kind": "node", "seq": 1, "fact": {
        "id": "g1", "types": ["Mechanism"], "name": "成长机制",
        "props": {"mechanism": {"growth_curve": "exponential"}}}}], "full")
    hit = [v for v in vs if v["rule"] == "growth_guardrail"]
    assert hit and hit[0]["level"] == "minor"      # 警告不阻断


def test_retracted_edge_does_not_trigger_interval_overlap(core_conn):  # T5 微裁决：撤回哨兵排除
    _seed(core_conn)
    with db.transaction(core_conn):
        events.append_event(core_conn, "retraction", {
            "target": "edge", "target_id": "old1", "reason": "误抽",
            "source": "auto_review"})
    projector.apply(core_conn)
    sentinel = core_conn.execute(
        "SELECT valid_until FROM edges WHERE id='old1'").fetchone()
    assert sentinel["valid_until"] == -1           # 前置条件：撤回边软删哨兵已物化
    vs = engine.run(core_conn, [{"kind": "edge", "seq": 3, "fact": {
        "id": "new2", "src": "a", "dst": "b", "kind": "PARTICIPATES",
        "props": {"valid_from_beat": "mb5", "valid_until_beat": "mb9"}}}],
        "full")
    assert not [v for v in vs if v["rule"] == "interval_overlap"]  # 已撤回边不构成冲突


def test_interval_overlap_top_level_beat_address_fallback(core_conn):  # T5 微裁决：props 优先、顶层兜底
    _seed(core_conn)
    vs = engine.run(core_conn, [{"kind": "edge", "seq": 2, "fact": {
        "id": "new3", "src": "a", "dst": "b", "kind": "PARTICIPATES",
        "valid_from_beat": "mb5", "valid_until_beat": "mb9"}}], "full")
    hit = [v for v in vs if v["rule"] == "interval_overlap"]
    assert hit and "old1" in hit[0]["refs"] and "new3" in hit[0]["refs"]


def test_track_ratchet_frozen(core_conn):  # TC-ON-10 后半
    with db.transaction(core_conn):
        events.append_event(core_conn, "track_added", {
            "track_id": "t1", "name": "现实轨", "definition": {"流速": 1}})
        events.append_event(core_conn, "track_frozen", {"track_id": "t1"})
    projector.apply(core_conn)
    vs = engine.run(core_conn, [{"kind": "track", "seq": 3, "fact": {
        "track_id": "t1", "definition": {"流速": 2}}}], "full")
    hit = [v for v in vs if v["rule"] == "track_ratchet"]
    assert hit and hit[0]["level"] == "major"
    clean = engine.run(core_conn, [{"kind": "track", "seq": 4, "fact": {
        "track_id": "t2", "definition": {"流速": 1}}}], "full")
    assert not [v for v in clean if v["rule"] == "track_ratchet"]  # 未冻结不管
