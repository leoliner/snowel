# src/snowel_core/consistency/seal.py
"""封卷（volume seal）与冻结线（freeze-line）拦截（C7/C11，TC-CC-05/06/08）。

封卷 = 卷级设定冻结：seal_volume 追加 volume_sealed 事件并由投影器物化
sealed_volumes 表；冻结线 = 已封卷内设定改动被普通确认拦截（SealedVolumeError，
提示走显式 retcon），auto 入典同拦，retraction 豁免（C11：auto 否决不受冻结线）。
"""
import json
import sqlite3

from ..storage import db, events, projector


class SealedVolumeError(Exception):
    """目标卷已封卷，设定改动须走显式 retcon（C7 冻结线）。"""


def _volume_node_id(conn: sqlite3.Connection, volume_no: int) -> str | None:
    """卷号 → 同号编址的 Volume 节点 id（props.address.volume 同号；无 → None）。"""
    for r in conn.execute("SELECT id, types, props FROM nodes WHERE active=1"):
        if "Volume" in json.loads(r["types"]) and \
                (json.loads(r["props"]).get("address") or {}).get("volume") == volume_no:
            return r["id"]
    return None


def _sealed(conn: sqlite3.Connection, volume_id: str) -> bool:
    row = conn.execute("SELECT 1 FROM sealed_volumes WHERE volume_id=?",
                       (volume_id,)).fetchone()
    return row is not None


def volume_id_of(conn: sqlite3.Connection, node_id: str) -> str | None:
    """节点归属卷 id（落盘地址口径）：节点 address.volume 编号 → 同号 Volume 节点 id。
    无 address / 无卷号 → None。"""
    row = conn.execute("SELECT props FROM nodes WHERE id=? AND active=1",
                       (node_id,)).fetchone()
    if row is None:
        return None
    v = (json.loads(row["props"]).get("address") or {}).get("volume")
    return _volume_node_id(conn, v) if v is not None else None


def is_sealed(conn: sqlite3.Connection, node_id: str) -> bool:
    """冻结线判定（落盘地址口径）：节点归属卷已封 → True；无 address/无卷 → False。"""
    vid = volume_id_of(conn, node_id)
    return vid is not None and _sealed(conn, vid)


def sealed_volume_of(conn: sqlite3.Connection, node_id: str,
                     address: dict | None = None) -> str | None:
    """冻结线判定（变更口径）：节点归属卷已封 → 卷 id，否则 None。

    address 为变更事实携带的地址（投影器全组覆写 props，变更后地址即生效值）；
    缺省/缺 volume 时回落到盘地址。confirm/extract 接线用本口——TC-CC-06 的
    拦截面含"变更给旧无地址节点新挂 address.volume"（存盘地址口径查不到）。
    """
    v = (address or {}).get("volume")
    vid = _volume_node_id(conn, v) if v is not None else volume_id_of(conn, node_id)
    if vid is None:
        return None
    return vid if _sealed(conn, vid) else None


def seal_volume(conn: sqlite3.Connection, volume_id: str) -> int:
    """校验 Volume 节点存在且未封 → 事务追加 volume_sealed + apply → 返回 seq。

    已封卷重复封 → ValueError（拒绝再封；改设定须走显式 retcon，Task 8）。
    """
    row = conn.execute("SELECT types FROM nodes WHERE id=? AND active=1",
                       (volume_id,)).fetchone()
    if row is None or "Volume" not in json.loads(row["types"]):
        raise ValueError(f"节点 {volume_id} 不存在或不是 Volume 节点，无法封卷")
    if _sealed(conn, volume_id):
        raise ValueError(f"卷 {volume_id} 已封卷")
    with db.transaction(conn):
        seq = events.append_event(conn, "volume_sealed",
                                  {"volume_id": volume_id})
        projector.apply(conn)
    return seq
