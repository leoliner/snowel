# tests/test_proposal.py
import pytest
from snowel_core.storage import db
from snowel_core.proposal import queue

FACTS = [{"fact": "node", "id": "n1", "types": ["Character"],
          "name": "林晚", "props": {}}]

@pytest.fixture
def q(tmp_path):
    conn = db.connect(tmp_path / "s.db"); db.migrate(conn)
    return queue.ProposalQueue(conn), conn

def test_create_is_pending_not_in_log(q):
    q, conn = q
    pid = q.create("scene", {"facts": FACTS})
    p = q.list("pending")
    assert [r["id"] for r in p] == [pid]
    assert conn.execute("SELECT COUNT(*) FROM events").fetchone()[0] == 0  # TC-EV-07

def test_confirm_appends_event_and_materializes(q):
    q, conn = q
    pid = q.create("scene", {"facts": FACTS})
    seq = q.confirm(pid)
    assert seq == 1
    assert conn.execute("SELECT status FROM proposals WHERE id=?", (pid,)).fetchone()["status"] == "confirmed"
    assert conn.execute("SELECT COUNT(*) FROM nodes").fetchone()[0] == 1

def test_confirm_atomic_on_bad_fact(q):  # TC-EV-08
    q, conn = q
    pid = q.create("scene", {"facts": [{"fact": "node", "id": "n1",
        "types": "Character", "name": "x", "props": {}}]})   # types 非数组 → 投影抛错
    with pytest.raises(Exception):
        q.confirm(pid)
    assert conn.execute("SELECT COUNT(*) FROM events").fetchone()[0] == 0
    assert conn.execute("SELECT COUNT(*) FROM nodes").fetchone()[0] == 0
    assert conn.execute("SELECT status FROM proposals WHERE id=?", (pid,)).fetchone()["status"] == "pending"

def test_reject_and_void_events(q):
    q, conn = q
    p1 = q.create("scene", {"facts": FACTS})
    p2 = q.create("scene", {"facts": FACTS})
    q.reject(p1, reason="重复")
    q.void(p2)
    kinds = [r[0] for r in conn.execute("SELECT kind FROM events ORDER BY seq")]
    assert kinds == ["proposal_rejected", "proposal_voided"]

def test_stale_and_strong_confirm(q):  # C5
    q, conn = q
    pid = q.create("scene", {"facts": FACTS})
    q.mark_stale(pid, "上游梗概已改")
    assert q.list("stale")[0]["stale_hint"] == "上游梗概已改"
    q.confirm(pid)   # stale → 强行确认，允许
    assert conn.execute("SELECT status FROM proposals WHERE id=?",
                        (pid,)).fetchone()["status"] == "confirmed"

def test_invalid_transition_raises(q):
    q, conn = q
    pid = q.create("scene", {"facts": FACTS})
    q.reject(pid)
    with pytest.raises(queue.ProposalStateError):
        q.confirm(pid)   # rejected 是终态

def test_no_ttl_no_autovoid(q):  # TC-PR-07：created_ts 久远也不自动迁移
    q, conn = q
    pid = q.create("scene", {"facts": FACTS})
    conn.execute("UPDATE proposals SET created_ts='2000-01-01' WHERE id=?", (pid,))
    assert [r["id"] for r in q.list("pending")] == [pid]
