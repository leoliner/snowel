# src/snowel_core/storage/vec.py
import json
import sqlite3

import sqlite_vec

from ..llm.embed import get_provider
from ..storage import config

_VEC_SQL = """
CREATE VIRTUAL TABLE IF NOT EXISTS node_vec USING vec0(
  node_id TEXT PRIMARY KEY, embedding float[64]);
CREATE VIRTUAL TABLE IF NOT EXISTS prose_vec USING vec0(
  chapter_id TEXT, para_idx INTEGER, embedding float[64]);
"""


def ensure(conn: sqlite3.Connection) -> None:
    conn.enable_load_extension(True)  # conda Python 需显式开扩展加载
    try:
        sqlite_vec.load(conn)  # vec0 模块按连接注册：已建表的库新连接也须加载才能查询
    finally:
        conn.enable_load_extension(False)
    hit = conn.execute("SELECT 1 FROM sqlite_master "
                       "WHERE type='table' AND name='node_vec'").fetchone()
    if hit:
        return  # 已建表短路：executescript 会隐式 COMMIT 未决事务，不随每次搜索重跑
    conn.executescript(_VEC_SQL)


def _node_text(r) -> str:
    props = json.loads(r["props"])
    flat = " ".join(str(v) for g in props.values()
                    if isinstance(g, dict) for v in g.values())
    return f"{r['name']} {flat}"


def rebuild_embeddings(conn: sqlite3.Connection, provider=None) -> dict:  # P2：显式重建
    p = provider or get_provider(conn)
    nodes = conn.execute(
        "SELECT id, name, props FROM nodes WHERE active=1").fetchall()
    paras = [(r["chapter_id"], i, t)
             for r in conn.execute("SELECT chapter_id, prose FROM chapter_prose")
             for i, t in enumerate(r["prose"].split("\n\n")) if t.strip()]
    vecs_n = p.embed([_node_text(r) for r in nodes])
    vecs_p = p.embed([t for _, _, t in paras])
    from .db import transaction  # L8：清旧+灌新+登记 built_with 同事务，失败整体回滚
    with transaction(conn):
        conn.execute("DELETE FROM node_vec"); conn.execute("DELETE FROM prose_vec")
        conn.executemany("INSERT INTO node_vec(node_id, embedding) VALUES(?,?)",
                         [(r["id"], json.dumps(v)) for r, v in zip(nodes, vecs_n)])
        conn.executemany(
            "INSERT INTO prose_vec(chapter_id, para_idx, embedding) VALUES(?,?,?)",
            [(c, i, json.dumps(v)) for (c, i, _), v in zip(paras, vecs_p)])
        config.set(conn, "embedding.built_with", p.name())
    return {"provider": p.name(), "nodes": len(nodes), "paragraphs": len(paras)}


def search(conn: sqlite3.Connection, q: str, limit: int = 10) -> list[dict]:
    p = get_provider(conn)
    qv = json.dumps(p.embed([q])[0])
    out = []
    for r in conn.execute(
            "SELECT node_id, distance FROM node_vec "
            "WHERE embedding MATCH ? AND k=?", (qv, limit)):
        out.append({"kind": "node", "node_id": r["node_id"],
                    "distance": r["distance"]})
    for r in conn.execute(
            "SELECT chapter_id, para_idx, distance FROM prose_vec "
            "WHERE embedding MATCH ? AND k=?", (qv, limit)):
        out.append({"kind": "paragraph", "chapter_id": r["chapter_id"],
                    "para_idx": r["para_idx"], "distance": r["distance"]})
    return out
