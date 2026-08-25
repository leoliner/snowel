# tests/consistency/test_deathbeat.py
import json
from snowel_core.storage import db, deathbeat, events, projector


def _confirm(conn, facts):
    with db.transaction(conn):
        events.append_event(conn, "proposal_confirmed",
                            {"artifact_type": "t", "facts": facts})
    projector.apply(conn)


def _seed(conn):
    _confirm(conn, [
        {"fact": "node", "id": "hero", "types": ["Character"], "name": "林晚",
         "props": {"core": {"death_beat": "mb9"}}},
        {"fact": "node", "id": "mb1", "types": ["MicroBeat"], "name": "早拍",
         "props": {"address": {"volume": 1, "chapter": 1, "scene": 1, "beat": 1}}},
        {"fact": "node", "id": "mb9", "types": ["MicroBeat"], "name": "死亡拍",
         "props": {"address": {"volume": 1, "chapter": 9, "scene": 1, "beat": 1}}},
    ])


def test_deathbeat_helpers(core_conn):
    _seed(core_conn)
    hero = deathbeat.dead_at(core_conn, core_conn.execute(
        "SELECT * FROM nodes WHERE id='hero'").fetchone())
    assert hero == 1                                   # mb1 序 0、mb9 序 1
    assert deathbeat.is_dead(core_conn, _row(core_conn, "hero"), 0) is False
    assert deathbeat.is_dead(core_conn, _row(core_conn, "hero"), 1) is True
    assert deathbeat.is_dead(core_conn, _row(core_conn, "mb1"), 5) is None


def _row(conn, nid):
    return conn.execute("SELECT * FROM nodes WHERE id=?", (nid,)).fetchone()


def test_deathbeat_requires_active_beat(core_conn):  # L13：死亡拍停用→保守存活
    _seed(core_conn)
    with db.transaction(core_conn):
        events.append_event(core_conn, "retraction",
                            {"target": "node", "target_id": "mb9"})
    projector.apply(core_conn)
    assert deathbeat.is_dead(core_conn, _row(core_conn, "hero"), 99) is False
    assert deathbeat.dead_at(core_conn, _row(core_conn, "hero")) is None
