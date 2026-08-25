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
