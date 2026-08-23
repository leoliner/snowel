# src/snowel_core/storage/queries.py
import json
import sqlite3


def state_at(conn: sqlite3.Connection, story_order: int) -> dict:
    """D1 修正后视角：fold 到 HEAD 后，按叙事时间点 story_order 投影当前生效集。只读。"""
    nodes = []
    for r in conn.execute(
            "SELECT * FROM nodes WHERE active=1 "
            "AND (story_order IS NULL OR story_order <= ?)", (story_order,)):
        props = json.loads(r["props"])
        flat = {f"{g}_{k}": v for g, gv in props.items() for k, v in gv.items()}
        death = props.get("core", {}).get("death_beat")
        if death is not None:
            dso = conn.execute("SELECT story_order, active FROM nodes WHERE id=?",
                               (death,)).fetchone()
            if (dso and dso["active"] == 1
                    and dso["story_order"] is not None
                    and dso["story_order"] <= story_order):
                continue
        nodes.append({**dict(r), **flat})
    edges = [dict(r) for r in conn.execute(
        """SELECT * FROM edges
           WHERE (valid_from IS NULL OR valid_from <= ?)
             AND (valid_until IS NULL OR valid_until >= ?)""",
        (story_order, story_order))]
    return {"nodes": nodes, "edges": edges}


def get_node(conn: sqlite3.Connection, node_id: str):
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


def edges_of(conn: sqlite3.Connection, node_id: str, direction: str = "both") -> list:
    if direction == "out":
        return conn.execute("SELECT * FROM edges WHERE src=?", (node_id,)).fetchall()
    if direction == "in":
        return conn.execute("SELECT * FROM edges WHERE dst=?", (node_id,)).fetchall()
    return conn.execute(
        "SELECT * FROM edges WHERE src=? OR dst=?", (node_id, node_id)).fetchall()


def descendants(conn: sqlite3.Connection, node_id: str,
                kinds: list[str] | None = None, max_depth: int = 10) -> list:
    # kinds 参数保留签名不消费——按 kind 过滤边属级联检查计划的需求（YAGNI）
    return conn.execute("""
        WITH RECURSIVE walk(id, depth) AS (
            SELECT dst, 1 FROM edges WHERE src=?
            UNION
            SELECT e.dst, walk.depth+1 FROM edges e
            JOIN walk ON e.src = walk.id WHERE walk.depth < ?
        )
        SELECT DISTINCT n.* FROM walk JOIN nodes n ON n.id = walk.id
        WHERE n.active=1 AND n.id != ?
    """, (node_id, max_depth, node_id)).fetchall()
