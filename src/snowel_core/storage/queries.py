# src/snowel_core/storage/queries.py
import json
import sqlite3


def state_at(conn: sqlite3.Connection, story_order: int) -> dict:
    """D1 修正后视角：fold 到 HEAD 后，按叙事时间点 story_order 投影当前生效集。只读。"""
    nodes = []
    for r in conn.execute(
            "SELECT * FROM nodes WHERE active=1 "
            "AND (story_order IS NULL OR story_order <= ?)", (story_order,)):
        props = json.loads(r["props"])
        flat = {f"{g}_{k}": v for g, gv in props.items() for k, v in gv.items()}
        death = props.get("core", {}).get("death_beat")
        if death is not None:
            dso = conn.execute("SELECT story_order, active FROM nodes WHERE id=?",
                               (death,)).fetchone()
            if (dso and dso["active"] == 1
                    and dso["story_order"] is not None
                    and dso["story_order"] <= story_order):
                continue
        nodes.append({**dict(r), **flat})
    edges = [dict(r) for r in conn.execute(
        """SELECT * FROM edges
           WHERE (valid_from IS NULL OR valid_from <= ?)
             AND (valid_until IS NULL OR valid_until >= ?)""",
        (story_order, story_order))]
    return {"nodes": nodes, "edges": edges}
