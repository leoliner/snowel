from snowel_core.storage import db
from snowel_core.storage import events as ev

def _db(tmp_path):
    conn = db.connect(tmp_path / "snowel.db"); db.migrate(conn)
    return conn

def test_append_event_returns_increasing_seq(tmp_path):
    conn = _db(tmp_path)
    assert ev.head_seq(conn) == 0
    with db.transaction(conn) as tx:
        s1 = ev.append_event(tx, "track_added", {"track_id": "t1"})
        s2 = ev.append_event(tx, "track_frozen", {"track_id": "t1"})
    assert (s1, s2) == (1, 2)
    assert ev.head_seq(conn) == 2
    row = conn.execute("SELECT kind, payload FROM events WHERE seq=1").fetchone()
    assert row["kind"] == "track_added"
    conn.close()
