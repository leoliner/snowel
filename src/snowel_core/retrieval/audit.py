# src/snowel_core/retrieval/audit.py
import json
import sqlite3
from datetime import datetime, timezone


def record(conn, strategy: str, locate, dry_run: bool, bundle: dict) -> int:
    cur = conn.execute(
        "INSERT INTO retrieval_audit(ts, strategy, dry_run, locate, bundle) "
        "VALUES(?,?,?,?,?)",
        (datetime.now(timezone.utc).isoformat(), strategy, int(dry_run),
         json.dumps(locate or {}, ensure_ascii=False),
         json.dumps({"sections": bundle["sections"]}, ensure_ascii=False)))
    return cur.lastrowid


def recent(conn, limit: int = 50) -> list[dict]:
    return [dict(r) for r in conn.execute(
        "SELECT * FROM retrieval_audit ORDER BY id DESC LIMIT ?", (limit,))]
