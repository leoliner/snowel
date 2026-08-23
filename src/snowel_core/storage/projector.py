# src/snowel_core/storage/projector.py
import json
import sqlite3
from . import events

def _upsert_node(tx, f: dict, seq: int):
    tx.execute(
        """INSERT INTO nodes(id, types, name, completeness, props, active, created_event)
           VALUES(?,?,?,?,?,1,?)
           ON CONFLICT(id) DO UPDATE SET
             types=excluded.types, name=excluded.name, props=excluded.props""",
        (f["id"], json.dumps(f["types"], ensure_ascii=False), f["name"],
         f.get("completeness", "draft"), json.dumps(f.get("props", {}), ensure_ascii=False), seq))

def _upsert_edge(tx, f: dict, seq: int):
    vf, vu = f.get("valid_from_beat"), f.get("valid_until_beat")  # 拍地址→story_order 由 Task 5 换算，先并入 props 存档
    props = {**f.get("props", {})}
    if vf is not None:
        props["valid_from_beat"] = vf
    if vu is not None:
        props["valid_until_beat"] = vu
    tx.execute(
        """INSERT INTO edges(id, src, dst, kind, props, created_event)
           VALUES(?,?,?,?,?,?)
           ON CONFLICT(id) DO UPDATE SET
             src=excluded.src, dst=excluded.dst, kind=excluded.kind, props=excluded.props""",
        (f["id"], f["src"], f["dst"], f["kind"],
         json.dumps(props, ensure_ascii=False), seq))

def _facts_event(tx, payload: dict, seq: int):
    for f in payload["facts"]:
        (_upsert_node if f["fact"] == "node" else _upsert_edge)(tx, f, seq)

HANDLERS = {
    "proposal_confirmed": _facts_event,
    "auto_canonized": _facts_event,
    # 其余 kind 由 Task 4/后续计划补齐；未知 kind 记录但不物化（防前向兼容炸库）
}

def _checkpoint(conn) -> int:
    row = conn.execute("SELECT seq FROM checkpoint WHERE id=1").fetchone()
    return row["seq"] if row else 0

def apply(conn: sqlite3.Connection) -> None:
    """物化 checkpoint 之后的事件。必须在调用方事务内调用。"""
    last = _checkpoint(conn)
    rows = conn.execute(
        "SELECT seq, kind, payload FROM events WHERE seq > ? ORDER BY seq", (last,)).fetchall()
    for r in rows:
        payload = json.loads(r["payload"])
        handler = HANDLERS.get(r["kind"])
        if handler:
            handler(conn, payload, r["seq"])
    if rows:
        conn.execute(
            "INSERT INTO checkpoint(id, seq) VALUES(1, ?) "
            "ON CONFLICT(id) DO UPDATE SET seq=excluded.seq",
            (rows[-1]["seq"],))
