# src/snowel_core/retrieval/hybrid.py
import json
import sqlite3

from ..storage import fts, queries, vec


def search(conn: sqlite3.Connection, q: str, limit: int = 20,
           mode: str = "hybrid") -> dict:
    out: dict = {"nodes": [], "paragraphs": []}
    if mode in ("fts", "hybrid"):
        f = fts.search(conn, q, limit)
        out["paragraphs"] = f["paragraphs"]
        out["nodes"] = f["nodes"]
    if mode in ("vec", "hybrid"):
        vec.ensure(conn)  # vec0 虚表需扩展加载后建（幂等；直连 core_conn 的测试路径兜底）
        seen = {n["node_id"] for n in out["nodes"]}
        for h in vec.search(conn, q, limit):
            if h["kind"] == "node" and h["node_id"] not in seen:
                row = queries.get_node(conn, h["node_id"])
                if row is not None and row["active"]:  # 撤回节点 vec 残留（重建前）不回流
                    out["nodes"].append({"node_id": h["node_id"],
                                         "name": row["name"]})
    for n in out["nodes"]:  # TC-RT-03：死亡角色附"已死亡@拍N"
        row = queries.get_node(conn, n["node_id"])
        props = json.loads(row["props"])
        death = props.get("core", {}).get("death_beat")
        if death is not None:
            d = queries.get_node(conn, death)
            n["dead_beat"] = d["story_order"] if d and d["story_order"] is not None else -1
    return out
