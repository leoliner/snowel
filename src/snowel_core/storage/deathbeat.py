# src/snowel_core/storage/deathbeat.py
import json
import sqlite3


def dead_at(conn: sqlite3.Connection, node_row) -> int | None:
    """死亡拍 story_order；death_beat 缺失或死亡拍停用/无序 → None（L13 统一口径）。"""
    props = json.loads(node_row["props"])
    beat = props.get("core", {}).get("death_beat")
    if beat is None:
        return None
    row = conn.execute("SELECT story_order, active FROM nodes WHERE id=?",
                       (beat,)).fetchone()
    if row is None or not row["active"] or row["story_order"] is None:
        return None
    return row["story_order"]


def is_dead(conn: sqlite3.Connection, node_row, story_order: int) -> bool | None:
    """True=已死；False=存活（含保守存活）；None=未设死点。"""
    d = dead_at(conn, node_row)
    if d is None:
        beat = json.loads(node_row["props"]).get("core", {}).get("death_beat")
        return None if beat is None else False
    return d <= story_order
