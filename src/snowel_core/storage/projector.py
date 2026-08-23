# src/snowel_core/storage/projector.py
import json
import sqlite3

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
    # 其余 kind 由后续计划补齐；未知 kind 静默跳过不物化（防前向兼容炸库）
}

def _retraction(tx, payload, seq):
    table = "nodes" if payload["target"] == "node" else "edges"
    if table == "nodes":
        tx.execute("UPDATE nodes SET active=0 WHERE id=?", (payload["target_id"],))
    else:
        tx.execute("UPDATE edges SET valid_until=-1 WHERE id=?", (payload["target_id"],))
    # edges 的 valid_until=-1 表示"已被撤回、任何拍均不生效"

def _retcon_applied(tx, payload, seq):
    for r in payload.get("renames", []):
        tx.execute("UPDATE nodes SET name=? WHERE id=?", (r["new_name"], r["node_id"]))
        tx.execute("INSERT OR IGNORE INTO alias(node_id, alias, source) VALUES(?,?,?)",
                   (r["node_id"], r["old_name"], "retcon"))

def _completeness_override(tx, payload, seq):
    tx.execute("UPDATE nodes SET completeness=? WHERE id=?",
               (payload["new"], payload["node_id"]))

def _track_added(tx, payload, seq):
    tx.execute("INSERT INTO tracks(id, name, definition, frozen) VALUES(?,?,?,0) "
               "ON CONFLICT(id) DO NOTHING",
               (payload["track_id"], payload["name"],
                json.dumps(payload["definition"], ensure_ascii=False)))

def _track_frozen(tx, payload, seq):
    tx.execute("UPDATE tracks SET frozen=1 WHERE id=?", (payload["track_id"],))

HANDLERS.update({
    "retraction": _retraction,
    "retcon_applied": _retcon_applied,
    "completeness_override": _completeness_override,
    "track_added": _track_added,
    "track_frozen": _track_frozen,
})

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
