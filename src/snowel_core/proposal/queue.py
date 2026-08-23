# src/snowel_core/proposal/queue.py
import json
import sqlite3
import uuid
from datetime import datetime, timezone

from ..storage import events, projector
from ..storage.db import transaction

class ProposalStateError(Exception):
    pass

_ALLOWED = {  # design §3.3 状态图
    ("pending", "confirmed"), ("pending", "rejected"), ("pending", "voided"),
    ("pending", "stale"), ("stale", "pending"), ("stale", "confirmed"),
    ("stale", "rejected"), ("stale", "voided"),
}

class ProposalQueue:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def _get(self, pid) -> sqlite3.Row:
        return self.conn.execute(
            "SELECT * FROM proposals WHERE id=?", (pid,)).fetchone()

    def _transition(self, pid, new: str) -> None:
        old = self._get(pid)["status"]
        if (old, new) not in _ALLOWED:
            raise ProposalStateError(f"非法迁移 {old} -> {new}")

    def create(self, kind: str, payload: dict) -> str:
        pid = str(uuid.uuid4())
        self.conn.execute(
            "INSERT INTO proposals(id, kind, payload, status, created_ts) VALUES(?,?,?,?,?)",
            (pid, kind, json.dumps(payload, ensure_ascii=False), "pending",
             datetime.now(timezone.utc).isoformat()))
        return pid

    def list(self, status=None):
        if status:
            return self.conn.execute(
                "SELECT * FROM proposals WHERE status=? ORDER BY created_ts",
                (status,)).fetchall()
        return self.conn.execute(
            "SELECT * FROM proposals ORDER BY created_ts").fetchall()

    def confirm(self, proposal_id: str) -> int:
        self._transition(proposal_id, "confirmed")
        p = self._get(proposal_id)
        payload = json.loads(p["payload"])
        with transaction(self.conn):
            seq = events.append_event(self.conn, "proposal_confirmed", {
                "proposal_id": proposal_id, "artifact_type": p["kind"],
                "facts": payload["facts"]})
            projector.apply(self.conn)
            self.conn.execute(
                "UPDATE proposals SET status='confirmed' WHERE id=?", (proposal_id,))
        return seq

    def reject(self, proposal_id: str, reason: str | None = None):
        self._transition(proposal_id, "rejected")
        with transaction(self.conn):
            events.append_event(self.conn, "proposal_rejected",
                                {"proposal_id": proposal_id, "reason": reason})
            self.conn.execute(
                "UPDATE proposals SET status='rejected' WHERE id=?", (proposal_id,))

    def void(self, proposal_id: str):
        self._transition(proposal_id, "voided")
        with transaction(self.conn):
            events.append_event(self.conn, "proposal_voided",
                                {"proposal_id": proposal_id})
            self.conn.execute(
                "UPDATE proposals SET status='voided' WHERE id=?", (proposal_id,))

    def mark_stale(self, proposal_id: str, hint: str):
        self._transition(proposal_id, "stale")
        with transaction(self.conn):
            events.append_event(self.conn, "stale_marked",
                                {"proposal_id": proposal_id, "hint": hint})
            self.conn.execute(
                "UPDATE proposals SET status='stale', stale_hint=? WHERE id=?",
                (hint, proposal_id))
