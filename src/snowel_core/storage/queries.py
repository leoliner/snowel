# src/snowel_core/storage/queries.py
import json
import sqlite3

from . import deathbeat


def state_at(conn: sqlite3.Connection, story_order: int) -> dict:
    """D1 修正后视角：fold 到 HEAD 后，按叙事时间点 story_order 投影当前生效集。只读。"""
    nodes = []
    for r in conn.execute(
            "SELECT * FROM nodes WHERE active=1 "
            "AND (story_order IS NULL OR story_order <= ?)", (story_order,)):
        props = json.loads(r["props"])
        flat = {f"{g}_{k}": v for g, gv in props.items() for k, v in gv.items()}
        if deathbeat.is_dead(conn, r, story_order):
            continue
        nodes.append({**dict(r), **flat})
    edges = [dict(r) for r in conn.execute(
        """SELECT * FROM edges
           WHERE (valid_from IS NULL OR valid_from <= ?)
             AND (valid_until IS NULL OR valid_until >= ?)""",
        (story_order, story_order))]
    return {"nodes": nodes, "edges": edges}


def get_node(conn: sqlite3.Connection, node_id: str,
             active_only: bool = True):
    """节点反查：默认仅 active=1 的生效行；active_only=False 保留旧行为
    （撤回行仍在库，active=0——读"前 canon"的调用方显式关闭过滤，L17）。"""
    if active_only:
        return conn.execute("SELECT * FROM nodes WHERE id=? AND active=1",
                            (node_id,)).fetchone()
    return conn.execute("SELECT * FROM nodes WHERE id=?", (node_id,)).fetchone()


def find_nodes(conn: sqlite3.Connection, name: str | None = None,
               type: str | None = None) -> list:
    sql = """SELECT DISTINCT n.* FROM nodes n
             LEFT JOIN alias a ON a.node_id = n.id
             WHERE n.active=1"""
    args = []
    if name is not None:
        sql += " AND (n.name=? OR a.alias=?)"
        args += [name, name]
    if type is not None:
        sql += " AND n.types LIKE ?"
        args.append(f'%"{type}"%')
    return conn.execute(sql, args).fetchall()


def edges_of(conn: sqlite3.Connection, node_id: str, direction: str = "both",
             active_only: bool = True) -> list:
    """节点关联边反查：默认仅返回两端节点均 active=1 的边（提示面口径）；
    active_only=False 保留旧行为（读"前 canon"的调用方显式关闭，L17）。
    边行无 active 列——撤回边是软删（valid_until=-1 哨兵），active 判定以
    两端节点 active 为准。"""
    if direction == "out":
        sql, args = "SELECT * FROM edges WHERE (src=?)", [node_id]
    elif direction == "in":
        sql, args = "SELECT * FROM edges WHERE (dst=?)", [node_id]
    else:
        sql, args = "SELECT * FROM edges WHERE (src=? OR dst=?)", [node_id, node_id]
    if active_only:
        sql += (" AND EXISTS(SELECT 1 FROM nodes n WHERE n.id=edges.src"
                " AND n.active=1) AND EXISTS(SELECT 1 FROM nodes n"
                " WHERE n.id=edges.dst AND n.active=1)")
    return conn.execute(sql, args).fetchall()


def descendants(conn: sqlite3.Connection, node_id: str,
                kinds: list[str] | None = None, max_depth: int = 10,
                at_story_order: int | None = None) -> list:
    """L4：kinds=边 kind 白名单（None 全部）；at_story_order=边时效过滤
    （valid_from/until 覆盖该拍才可通行，None 不限）。默认行为不变。
    谓词推入递归 CTE 两臂（锚点与递归臂），遍历中过滤。"""

    def _edge_pred(alias: str) -> tuple[str, list]:
        pred, args = "", []
        if kinds is not None:
            pred += f" AND {alias}.kind IN ({','.join('?' * len(kinds))})"
            args += kinds
        if at_story_order is not None:
            pred += (f" AND ({alias}.valid_from IS NULL OR {alias}.valid_from <= ?)"
                     f" AND ({alias}.valid_until IS NULL OR {alias}.valid_until >= ?)")
            args += [at_story_order, at_story_order]
        return pred, args

    anchor_pred, anchor_args = _edge_pred("edges")
    rec_pred, rec_args = _edge_pred("e")
    return conn.execute(f"""
        WITH RECURSIVE walk(id, depth) AS (
            SELECT dst, 1 FROM edges WHERE src=?{anchor_pred}
            UNION
            SELECT e.dst, walk.depth+1 FROM edges e
            JOIN walk ON e.src = walk.id
            WHERE walk.depth < ?{rec_pred}
        )
        SELECT DISTINCT n.* FROM walk JOIN nodes n ON n.id = walk.id
        WHERE n.active=1 AND n.id != ?
    """, [node_id, *anchor_args, max_depth, *rec_args, node_id]).fetchall()


def graph_stats(conn: sqlite3.Connection) -> dict:
    nodes = conn.execute("SELECT count(*) c FROM nodes").fetchone()["c"]
    edges = conn.execute("SELECT count(*) c FROM edges").fetchone()["c"]
    active_nodes = conn.execute(
        "SELECT count(*) c FROM nodes WHERE active=1").fetchone()["c"]
    by_type = {r["type"]: r["n"] for r in conn.execute(
        "SELECT je.value AS type, count(*) AS n "
        "FROM nodes, json_each(nodes.types) je "
        "GROUP BY je.value ORDER BY n DESC")}
    return {"nodes": nodes, "edges": edges, "active_nodes": active_nodes,
            "nodes_by_type": by_type}
