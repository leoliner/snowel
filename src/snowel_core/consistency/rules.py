# src/snowel_core/consistency/rules.py
import json
import sqlite3

from . import engine
from ..storage import fts, queries


def _flat(props: dict) -> dict:
    """与 state_at 同法扁平化：仅展开 dict 组值中的标量 → {g}_{k}: v。"""
    return {f"{g}_{k}": v for g, gv in props.items()
            if isinstance(gv, dict) for k, v in gv.items()
            if not isinstance(v, (dict, list))}


def contradiction(change: dict, conn: sqlite3.Connection) -> list[dict]:
    """TC-CC-01 集合一致性：变更 fact 扁平属性 vs 物化当前生效值同键不同值 → major。

    只读物化表不写不阻断（事件照常落、节点照常 upsert）；
    diff 修订提案由 engine.diff_proposal 组装。
    """
    if change.get("kind") != "node":
        return []
    fact = change.get("fact", {})
    new_flat = _flat(fact.get("props", {}))
    if not new_flat:
        return []
    row = conn.execute("SELECT props FROM nodes WHERE id=? AND active=1",
                       (fact.get("id"),)).fetchone()
    if row is None:
        return []
    old_flat = _flat(json.loads(row["props"]))
    return [
        {"level": "major", "rule": "contradiction",
         "message": f"属性 {k} 与当前生效值矛盾",
         "refs": [fact["id"]],
         "detail": {"node_id": fact["id"], "key": k,
                    "old": old_flat[k], "new": v}}
        for k, v in sorted(new_flat.items())
        if k in old_flat and old_flat[k] != v
    ]


def dependents(change: dict, conn: sqlite3.Connection) -> list[dict]:
    """TC-CC-02 依赖检测（引用反查）：变更牵出的既有依赖 → 聚合一条 minor。

    node 变更：①边反查——指向该节点的边（src/dst 任一端）+ 对端节点名入 message；
    ②正文引用——fts.search(节点名) 命中段落，refs 追加 "chapter:para_idx"。
    edge 变更：反查 src/dst 两端节点各自的边与正文引用（变更边自身不计）。
    只读物化与索引表不阻断；无任何引用 → 无 Violation。
    """
    fact = change.get("fact", {})
    if change.get("kind") == "node":
        ends = [fact.get("id")]
        search_names = {fact.get("name")} - {None}
        skip = None
    elif change.get("kind") == "edge":
        ends = [fact.get("src"), fact.get("dst")]
        search_names = set()
        skip = fact.get("id")  # 变更边自身不是"既有依赖"
    else:
        return []
    edges, peer_ids = {}, []
    for nid in ends:
        if not nid:
            continue
        for e in queries.edges_of(conn, nid):
            if e["id"] == skip:
                continue
            edges[e["id"]] = e
            peer = e["dst"] if e["src"] == nid else e["src"]
            if peer != nid and peer not in peer_ids:
                peer_ids.append(peer)
    for nid in ends:  # 两端节点名并入正文搜索（node 变更换名时旧名也反查）
        if nid:
            row = queries.get_node(conn, nid)
            if row is not None:
                search_names.add(row["name"])
    peer_names = [r["name"] for r in conn.execute(
        f"SELECT name FROM nodes WHERE id IN ({','.join('?' * len(peer_ids))})",
        peer_ids)] if peer_ids else []
    paras = sorted({f'{p["chapter_id"]}:{p["para_idx"]}'
                    for name in search_names if name
                    for p in fts.search(conn, name)["paragraphs"]})
    refs = [*edges, *peer_ids, *paras]
    if not refs:
        return []
    message = (f"牵动既有依赖：对端 {'、'.join(peer_names) or '无'}；"
               f"正文段落命中 {len(paras)} 处")
    return [{"level": "minor", "rule": "dependents",
             "message": message, "refs": refs}]


engine.register("contradiction", contradiction, tiers=("full", "light"))
engine.register("dependents", dependents, tiers=("full", "light"))
