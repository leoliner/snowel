# src/snowel_core/retrieval/context.py
import json
import sqlite3

from ..storage import queries
from . import audit, hybrid


def _alive(conn, node_ids, story_order):
    out = []
    for nid in node_ids:
        row = queries.get_node(conn, nid)
        if row is None or not row["active"]:
            continue
        props = json.loads(row["props"])
        death = props.get("core", {}).get("death_beat")
        if death is not None:
            d = queries.get_node(conn, death)
            if d is not None and d["story_order"] is not None \
                    and d["story_order"] <= story_order:
                continue  # 已死亡@拍 ≤ 目标拍 → 不在场
        out.append(row)
    return out


def _node_section(conn, kind, rows, trim_core=False):
    rows = [r for r in rows
            if not json.loads(r["props"]).get("core", {}).get("todo")]
    # TODO 设定项排除（§6.1）：不进任何 section（refs 与 text 均不含）
    texts = []
    for r in rows:
        props = json.loads(r["props"])
        shown = {"core": props.get("core", {})} if trim_core else props
        texts.append(f"[{r['name']}] {json.dumps(shown, ensure_ascii=False)}")
    return {"kind": kind, "refs": [r["id"] for r in rows], "text": "\n".join(texts)}


def compose_context(conn: sqlite3.Connection, strategy: str,
                    locate: dict | None = None, dry_run: bool = False) -> dict:
    """E3：上下文组装唯一实现；检索审计每次落表（含 dry_run 标注）。"""
    locate = locate or {}
    sections = []
    if strategy == "prose":
        so = locate.get("story_order", 10 ** 9)
        scene = _scene_of_chapter(conn, locate.get("chapter"))
        if scene is not None:
            sections.append(_node_section(conn, "scene_card", [scene]))
            chars = _alive(conn, json.loads(scene["props"])
                           .get("characters", []), so)
            sections.append(_node_section(conn, "characters", chars,
                                          trim_core=True))
        open_fs = [r for r in conn.execute(
            "SELECT * FROM nodes WHERE active=1") if "Foreshadow" in r["types"]]
        sections.append(_node_section(conn, "foreshadows", open_fs))
        world = [r for r in conn.execute(
            "SELECT * FROM nodes WHERE active=1") if "Concept" in r["types"]]
        sections.append(_node_section(conn, "worldview", world))
    elif strategy == "character":
        row = queries.get_node(conn, locate["node_id"])
        peers = [queries.get_node(conn, e["dst"] if e["src"] == locate["node_id"]
                                  else e["src"])
                 for e in queries.edges_of(conn, locate["node_id"])]
        sections.append(_node_section(conn, "character", [row] if row else []))
        sections.append(_node_section(
            conn, "relations", [p for p in peers if p is not None]))
    q = locate.get("query") or locate.get("chapter") or ""
    if q:
        fallback = hybrid.search(conn, q, mode="hybrid")
        if fallback["nodes"] or fallback["paragraphs"]:
            sections.append({"kind": "fallback_recall",
                             "refs": [n["node_id"] for n in fallback["nodes"]],
                             "text": json.dumps(fallback, ensure_ascii=False)})
    bundle = {"strategy": strategy, "locate": locate, "sections": sections}
    bundle["audit_id"] = audit.record(conn, strategy, locate, dry_run, bundle)
    return bundle


def _scene_of_chapter(conn, chapter_id):
    for r in conn.execute("SELECT * FROM nodes WHERE active=1"):
        if "Scene" in r["types"] and json.loads(r["props"]).get("chapter") == chapter_id:
            return r
    return None
