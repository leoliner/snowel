# src/snowel_core/writeback/review.py
import json
import sqlite3

from ..storage import events, fts, projector
from ..storage.db import transaction


def list_auto(conn: sqlite3.Connection) -> list[dict]:
    out = []
    for ev in conn.execute(
            "SELECT seq, payload FROM events WHERE kind='auto_canonized' "
            "ORDER BY seq"):
        p = json.loads(ev["payload"])
        for f in p["facts"]:
            if f["fact"] == "node":
                row = conn.execute(
                    "SELECT name, active FROM nodes WHERE id=?",
                    (f["id"],)).fetchone()
                retracted = row is None or row["active"] == 0
                name_or_id = row["name"] if row else f["id"]
            else:
                row = conn.execute(
                    "SELECT valid_until FROM edges WHERE id=?", (f["id"],)).fetchone()
                retracted = row is None or row["valid_until"] == -1
                name_or_id = f["id"]
            out.append({"event_seq": ev["seq"], "fact_id": f["id"],
                        "kind": f["fact"], "name_or_id": name_or_id,
                        "source_chapter": p.get("source", {}).get("chapter_id"),
                        "retracted": retracted})
    return out


def reject_auto(conn: sqlite3.Connection, entries: list[tuple[str, str]],
                reason: str | None = None) -> dict:
    """auto 否决 = 纠正抽取错误（C11）：不受封卷冻结线约束，任何时候可否决；
    轻量反查只提示引用段落，不自动改正文（C2）。全量级联由级联检查计划承接。"""
    paragraphs = []
    with transaction(conn):
        for target, target_id in entries:
            events.append_event(conn, "retraction", {
                "target": target, "target_id": target_id,
                "reason": reason, "source": "auto_review"})
            if target == "node":
                row = conn.execute("SELECT name FROM nodes WHERE id=?",
                                   (target_id,)).fetchone()
                if row is not None:
                    paragraphs += fts.search(conn, row["name"])["paragraphs"]
        projector.apply(conn)
    return {"retracted": len(entries), "referencing_paragraphs": paragraphs}
