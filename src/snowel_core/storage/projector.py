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
             types=excluded.types, name=excluded.name, props=excluded.props,
             active=1""",
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
    for nid in payload.get("appeared", []):  # P7：登场 → active（不跳级）
        row = tx.execute("SELECT completeness FROM nodes WHERE id=?",
                         (nid,)).fetchone()
        if row is not None and row["completeness"] == "profiled":
            tx.execute("UPDATE nodes SET completeness='active' WHERE id=?", (nid,))

HANDLERS = {
    "proposal_confirmed": _facts_event,
    "auto_canonized": _facts_event,
    "inspiration_saved": _facts_event,        # TC-ON-12/§4.7：灵感原话落库
    "derived_from_registered": _facts_event,  # TC-ON-12/§4.7：DERIVED_FROM 边
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
    for t in payload.get("track_updates", []):  # P3：retcon 即合法改轨路径
        tx.execute("UPDATE tracks SET definition=? WHERE id=?",
                   (json.dumps(t["definition"], ensure_ascii=False), t["track_id"]))

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

def _volume_sealed(tx, payload, seq):
    tx.execute("INSERT INTO sealed_volumes(volume_id, sealed_seq) VALUES(?,?)",
               (payload["volume_id"], seq))

HANDLERS.update({
    "retraction": _retraction,
    "retcon_applied": _retcon_applied,
    "completeness_override": _completeness_override,
    "track_added": _track_added,
    "track_frozen": _track_frozen,
    "volume_sealed": _volume_sealed,
})

def _addr_key(props: dict) -> tuple:
    a = props.get("address") or {}
    return (a.get("volume", 0), a.get("chapter", 0), a.get("scene", 0), a.get("beat", 0))

def recompute_story_order(conn: sqlite3.Connection) -> None:
    # 不变量：story_order 仅活跃有地址节点有意义，其余一律清为 NULL——失效节点
    # 若不清，_beat_order（rules.py）会把它解析成有限序而非"未解析→None（±∞ 保守）"
    rows = conn.execute("SELECT id, props, active FROM nodes").fetchall()
    addressed = []
    for r in rows:
        if not r["active"]:
            continue
        p = json.loads(r["props"])
        if p.get("address"):
            addressed.append((_addr_key(p), r["id"]))
    addressed.sort()
    order = {nid: i for i, (_, nid) in enumerate(addressed)}
    conn.executemany("UPDATE nodes SET story_order=? WHERE id=?",
                     [(order.get(r["id"]), r["id"]) for r in rows])
    # 边有效期：拍地址 → story_order
    for e in conn.execute("SELECT id, props, valid_until FROM edges").fetchall():
        if e["valid_until"] == -1:  # 已撤回哨兵：保持撤回，直到后续事实重新确认该边
            continue
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

def _prose_event(tx, payload: dict, seq: int):
    # P1：事件只登记哈希；全文由 writeback 对账从文件灌入
    h = payload.get("hash") or payload["new_hash"]  # external_change 登记新哈希
    tx.execute(
        """INSERT INTO chapter_prose(chapter_id, path, hash, prose, updated_event)
           VALUES(?,?,?,?,?)
           ON CONFLICT(chapter_id) DO UPDATE SET
             hash=excluded.hash, path=excluded.path,
             updated_event=excluded.updated_event""",
        (payload["chapter_id"], payload["path"], h, "", seq))

HANDLERS.update({
    "prose_hash_registered": _prose_event,
    "prose_external_change": _prose_event,
})

def _beat_merged(tx, payload: dict, seq: int):
    # D6：源拍失效；伏笔引用按 R1 载荷迁移（目标拍不动、派生序由 apply 尾部重算）
    tx.execute("UPDATE nodes SET active=0 WHERE id=?", (payload["source_beat_id"],))
    for m in payload.get("moved_foreshadows", []):
        row = tx.execute("SELECT props FROM nodes WHERE id=?",
                         (m["foreshadow_id"],)).fetchone()
        if row is None:  # 载荷自含、但节点不存在时静默跳过（幂等重放安全）
            continue
        p = json.loads(row["props"])
        p.setdefault("foreshadow", {})["planted_at"] = m["new"]
        tx.execute("UPDATE nodes SET props=? WHERE id=?",
                   (json.dumps(p, ensure_ascii=False), m["foreshadow_id"]))

HANDLERS["beat_merged"] = _beat_merged

def _chapter_importance_set(tx, payload: dict, seq: int):
    # R4：低重要标记也必须事件化（append-only，rebuild 可重放）——
    # chapter 节点 props.importance 随之更新（low/normal）
    row = tx.execute("SELECT props FROM nodes WHERE id=?",
                     (payload["chapter_id"],)).fetchone()
    if row is None:  # 节点不存在时静默跳过（幂等重放安全）
        return
    p = json.loads(row["props"])
    p["importance"] = payload["importance"]
    tx.execute("UPDATE nodes SET props=? WHERE id=?",
               (json.dumps(p, ensure_ascii=False), payload["chapter_id"]))

HANDLERS["chapter_importance_set"] = _chapter_importance_set

def _checkpoint(conn) -> int:
    row = conn.execute("SELECT seq FROM checkpoint WHERE id=1").fetchone()
    return row["seq"] if row else 0

def rebuild(conn: sqlite3.Connection) -> None:
    """全量重建：清空物化表后重放全部事件（D1：检查点永不过期、可随时重建）。"""
    from .db import transaction
    with transaction(conn):
        for t in ("alias", "edges", "nodes", "tracks", "chapter_prose",
                  "sealed_volumes", "checkpoint"):
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
    from . import fts
    fts.refresh(conn)  # E1/P2：一次确认=事件+物化+索引，FTS 重灌同事务
    if rows:
        conn.execute(
            "INSERT INTO checkpoint(id, seq) VALUES(1, ?) "
            "ON CONFLICT(id) DO UPDATE SET seq=excluded.seq",
            (rows[-1]["seq"],))
