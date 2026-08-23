import json
import sqlite3
from datetime import datetime, timezone

def append_event(tx: sqlite3.Connection, kind: str, payload: dict) -> int:
    ts = datetime.now(timezone.utc).isoformat()
    cur = tx.execute(
        "INSERT INTO events(ts, kind, payload) VALUES(?,?,?)",
        (ts, kind, json.dumps(payload, ensure_ascii=False)))
    return cur.lastrowid

def head_seq(conn: sqlite3.Connection) -> int:
    row = conn.execute("SELECT COALESCE(MAX(seq), 0) AS s FROM events").fetchone()
    return row["s"]
