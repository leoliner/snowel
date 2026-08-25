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


def _beat_order(conn: sqlite3.Connection, beat) -> int | None:
    """拍地址（节点 id）→ story_order；未解析（无节点/无地址）→ None 视为 ±∞（保守）。"""
    if not beat:
        return None
    row = conn.execute("SELECT story_order FROM nodes WHERE id=?", (beat,)).fetchone()
    return row["story_order"] if row else None


def interval_overlap(change: dict, conn: sqlite3.Connection) -> list[dict]:
    """TC-CC-03 区间检测：新边有效期与同 (src,dst,kind) 既有边重叠 → minor。

    新边拍地址（props 或顶层 valid_from_beat/valid_until_beat，与 projector
    同口径）换算 story_order 后比对：重叠 = f' ≤ u 且 f ≤ u'（None 视为 ±∞）。
    空洞检测 v1 简化不做（提示级，只做重叠）；变更边自身与撤回边
    （valid_until=-1 哨兵，任何拍均不生效）不构成冲突。只读不阻断。
    """
    if change.get("kind") != "edge":
        return []
    fact = change.get("fact", {})
    props = fact.get("props", {})
    from_beat = props.get("valid_from_beat", fact.get("valid_from_beat"))
    until_beat = props.get("valid_until_beat", fact.get("valid_until_beat"))
    if from_beat is None and until_beat is None:  # 无有效期语义不参与比对
        return []
    nf, nu = _beat_order(conn, from_beat), _beat_order(conn, until_beat)
    return [
        {"level": "minor", "rule": "interval_overlap",
         "message": f"有效期与既有边 {e['id']} 重叠",
         "refs": [e["id"], fact["id"]]}
        for e in conn.execute(
            "SELECT id, valid_from, valid_until FROM edges "
            "WHERE src=? AND dst=? AND kind=? AND id!=? "
            "AND (valid_until IS NULL OR valid_until!=-1)",
            (fact.get("src"), fact.get("dst"), fact.get("kind"), fact.get("id")))
        # 重叠 = nf ≤ u 且 f ≤ nu（None = ±∞ 恒过）
        if (nf is None or e["valid_until"] is None or nf <= e["valid_until"])
        and (e["valid_from"] is None or nu is None or e["valid_from"] <= nu)]


def growth_guardrail(change: dict, conn: sqlite3.Connection) -> list[dict]:
    """TC-ON-16 增长曲线护栏：node props 的 mechanism.growth_curve
    值含 "exponential"/"指数" → minor 警告不阻断（Layer 1）。"""
    if change.get("kind") != "node":
        return []
    fact = change.get("fact", {})
    curve = _flat(fact.get("props", {})).get("mechanism_growth_curve")
    if not isinstance(curve, str) or ("exponential" not in curve
                                      and "指数" not in curve):
        return []
    return [{"level": "minor", "rule": "growth_guardrail",
             "message": "指数增长护栏警告（Layer 1）", "refs": [fact["id"]]}]


def track_ratchet(change: dict, conn: sqlite3.Connection) -> list[dict]:
    """TC-ON-10 后半 轨道棘轮：track 变更（定义修改，仅 retcon 路径产生——Task 8）
    且该轨 frozen=1 且 definition 与现存不同 → major。未冻结/无记录 → 不报。
    假设变更 fact 恒带 definition 键（T8 retcon 契约；缺失视为 None，与冻结轨
    存量定义必不等 → 照报 major）。"""
    if change.get("kind") != "track":
        return []
    fact = change.get("fact", {})
    row = conn.execute("SELECT definition, frozen FROM tracks WHERE id=?",
                       (fact.get("track_id"),)).fetchone()
    if row is None or not row["frozen"]:
        return []
    if json.loads(row["definition"]) == fact.get("definition"):
        return []
    return [{"level": "major", "rule": "track_ratchet",
             "message": "轨道已冻结，修改须走显式 retcon（本检查即 retcon 全量档的一部分）",
             "refs": [fact["track_id"]]}]


engine.register("contradiction", contradiction, tiers=("full", "light"))
engine.register("dependents", dependents, tiers=("full", "light"))
engine.register("interval_overlap", interval_overlap, tiers=("full",))
engine.register("growth_guardrail", growth_guardrail, tiers=("full",))
engine.register("track_ratchet", track_ratchet, tiers=("full",))
