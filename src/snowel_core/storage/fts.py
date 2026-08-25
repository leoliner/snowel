# src/snowel_core/storage/fts.py
import json
import re
import sqlite3

import jieba

_PUNCT = re.compile(r"^[\W_]+$", re.UNICODE)


def tokenize(text: str) -> str:  # P3：Python 侧 jieba 预分词，空格分隔 token 串
    return " ".join(t for t in jieba.cut_for_search(text)
                    if t.strip() and not _PUNCT.match(t))


def refresh(conn: sqlite3.Connection) -> None:  # P2：FTS 便宜，apply 内全量重灌
    conn.execute("DELETE FROM node_fts")
    rows = conn.execute("SELECT id, name, props FROM nodes WHERE active=1").fetchall()
    data = []
    for r in rows:
        props = json.loads(r["props"])
        flat = " ".join(str(v) for g in props.values()
                        if isinstance(g, dict) for v in g.values())
        aliases = [a["alias"] for a in conn.execute(
            "SELECT alias FROM alias WHERE node_id=?", (r["id"],))]
        text = tokenize(" ".join([r["name"], *aliases, flat]))
        data.append((r["id"], text))
    conn.executemany("INSERT INTO node_fts(node_id, text) VALUES(?,?)", data)

    conn.execute("DELETE FROM prose_fts")
    conn.execute("DELETE FROM prose_paragraph")
    paras, raws = [], []
    for r in conn.execute("SELECT chapter_id, prose FROM chapter_prose"):
        for i, para in enumerate(r["prose"].split("\n\n")):
            if para.strip():
                paras.append((r["chapter_id"], i, tokenize(para)))
                raws.append((r["chapter_id"], i, para))  # L10：原文留侧表
    conn.executemany(
        "INSERT INTO prose_fts(chapter_id, para_idx, text) VALUES(?,?,?)", paras)
    conn.executemany(
        "INSERT INTO prose_paragraph(chapter_id, para_idx, text) "
        "VALUES(?,?,?)", raws)


def _query_expr(q: str) -> str:
    return " AND ".join(f'"{t}"*' for t in tokenize(q).split()[:8])


def search(conn: sqlite3.Connection, q: str, limit: int = 100) -> dict:
    expr = _query_expr(q)
    if not expr:
        return {"nodes": [], "paragraphs": []}
    nodes = [{"node_id": r["node_id"],
              "name": conn.execute("SELECT name FROM nodes WHERE id=?",
                                   (r["node_id"],)).fetchone()["name"]}
             for r in conn.execute(
                 "SELECT node_id FROM node_fts WHERE node_fts MATCH ? LIMIT ?",
                 (expr, limit))]
    paras = [{"chapter_id": r["chapter_id"], "para_idx": r["para_idx"],
              "text": r["text"]}
             for r in conn.execute(
                 "SELECT f.chapter_id, f.para_idx, p.text FROM prose_fts f "
                 "JOIN prose_paragraph p ON p.chapter_id=f.chapter_id "
                 "AND p.para_idx=f.para_idx "
                 "WHERE prose_fts MATCH ? LIMIT ?", (expr, limit))]
    return {"nodes": nodes, "paragraphs": paras}
