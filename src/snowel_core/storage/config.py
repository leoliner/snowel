# src/snowel_core/storage/config.py
import json
import sqlite3


def get(conn: sqlite3.Connection, key: str, default=None):
    row = conn.execute("SELECT value FROM config WHERE key=?", (key,)).fetchone()
    return json.loads(row["value"]) if row else default


def set(conn: sqlite3.Connection, key: str, value) -> None:
    conn.execute(
        "INSERT INTO config(key, value) VALUES(?, ?) "
        "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
        (key, json.dumps(value, ensure_ascii=False)))
