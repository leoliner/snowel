# src/snowel_core/retrieval/hybrid.py
import json
import sqlite3

from ..llm import ports
from ..storage import fts, queries, vec


def search(conn: sqlite3.Connection, q: str, limit: int = 20,
           mode: str = "hybrid", backend=None) -> dict:
    out: dict = {"nodes": [], "paragraphs": []}
    eff = q
    if q:
        # 改写层前置（TC-RT-07/R2）：三路检索入口全收敛此处。改写结果以
        # "rewrite" 键随结果返回——api.search 门面据此落 strategy="search"
        # 条件审计行，compose_context 并入既有审计行（入口 B 不新增行）；
        # 开关关时 rewrite_query 内部早退返回原词（无该键、零 LLM 调用）。
        w = ports.rewrite_query(conn, q, {"original": q}, backend=backend)
        if w is None:
            out["rewrite"] = {"failed": True, "original": q}
        elif w != q:
            eff = w
            out["rewrite"] = {"original": q, "rewritten": w}
    if mode in ("fts", "hybrid"):
        f = fts.search(conn, eff, limit)
        out["paragraphs"] = f["paragraphs"]
        out["nodes"] = f["nodes"]
    if mode in ("vec", "hybrid"):
        vec.ensure(conn)  # vec0 虚表需扩展加载后建（幂等；直连 core_conn 的测试路径兜底）
        seen = {n["node_id"] for n in out["nodes"]}
        for h in vec.search(conn, eff, limit):
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
