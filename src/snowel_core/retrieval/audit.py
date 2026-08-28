# src/snowel_core/retrieval/audit.py
import json
import sqlite3
from datetime import datetime, timezone


def record(conn, strategy: str, locate, dry_run: bool, bundle: dict) -> int:
    payload = {"sections": bundle["sections"]}
    if "rewrite" in bundle:  # TC-RT-07：改写明细自由键（TEXT 列，零 schema 变更）
        payload["rewrite"] = bundle["rewrite"]
    cur = conn.execute(
        "INSERT INTO retrieval_audit(ts, strategy, dry_run, locate, bundle) "
        "VALUES(?,?,?,?,?)",
        (datetime.now(timezone.utc).isoformat(), strategy, int(dry_run),
         json.dumps(locate or {}, ensure_ascii=False),
         json.dumps(payload, ensure_ascii=False)))
    return cur.lastrowid


def recent(conn, limit: int = 50) -> list[dict]:
    return [dict(r) for r in conn.execute(
        "SELECT * FROM retrieval_audit ORDER BY id DESC LIMIT ?", (limit,))]
