# src/snowel_core/storage/projector.py
import json
import sqlite3

def _upsert_node(tx, f: dict, seq: int):
    if not isinstance(f.get("types"), list):
        raise ValueError(f"node 事实 types 必须为数组: {f.get('id')}")
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

def _addr_key(props: dict) -> tuple:
    a = props.get("address") or {}
    return (a.get("volume", 0), a.get("chapter", 0), a.get("scene", 0), a.get("beat", 0))

def recompute_story_order(conn: sqlite3.Connection) -> None:
    rows = conn.execute("SELECT id, props FROM nodes WHERE active=1").fetchall()
    addressed = []
    for r in rows:
        p = json.loads(r["props"])
        if p.get("address"):
            addressed.append((_addr_key(p), r["id"]))
    addressed.sort()
    order = {nid: i for i, (_, nid) in enumerate(addressed)}
    conn.executemany("UPDATE nodes SET story_order=? WHERE id=?",
                     [(order.get(r["id"]), r["id"]) for r in rows])
    # 边有效期：拍地址 → story_order
    for e in conn.execute("SELECT id, props FROM edges").fetchall():
        p = json.loads(e["props"])
        vf, vu = p.get("valid_from_beat"), p.get("valid_until_beat")
        conn.execute("UPDATE edges SET valid_from=?, valid_until=? WHERE id=?",
                     (order.get(vf) if vf else None,
                      order.get(vu) if vu else None, e["id"]))

def _revision_applied(tx, payload, seq):
    for ch in payload.get("structure_changes", []):
        if ch.get("op") == "move":
            props = tx.execute("SELECT props FROM nodes WHERE id=?",
                               (ch["node_id"],)).fetchone()
            p = json.loads(props["props"]); p["address"] = ch["address"]
            tx.execute("UPDATE nodes SET props=? WHERE id=?",
                       (json.dumps(p, ensure_ascii=False), ch["node_id"]))
    recompute_story_order(tx)

HANDLERS["revision_applied"] = _revision_applied

def _checkpoint(conn) -> int:
    row = conn.execute("SELECT seq FROM checkpoint WHERE id=1").fetchone()
    return row["seq"] if row else 0

def rebuild(conn: sqlite3.Connection) -> None:
    """全量重建：清空物化表后重放全部事件（D1：检查点永不过期、可随时重建）。"""
    from .db import transaction
    with transaction(conn):
        for t in ("alias", "edges", "nodes", "tracks", "checkpoint"):
            conn.execute(f"DELETE FROM {t}")
        apply(conn)

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
    recompute_story_order(conn)  # 任何含地址事实的事件后派生序保持最新
    if rows:
        conn.execute(
            "INSERT INTO checkpoint(id, seq) VALUES(1, ?) "
            "ON CONFLICT(id) DO UPDATE SET seq=excluded.seq",
            (rows[-1]["seq"],))
