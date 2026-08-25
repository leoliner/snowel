# src/snowel_core/consistency/rules.py
import json
import sqlite3

from . import engine


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


engine.register("contradiction", contradiction, tiers=("full", "light"))
