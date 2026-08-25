# src/snowel_core/consistency/foreshadow.py
"""伏笔注册门面（§4.8，TC-ON-14 手动 author 通道）：校验 → 建 kind="foreshadow" 提案。

铁律 3 提案范式：注册即建提案，确认走 api.confirm（级联/冻结线随 confirm
接线自然生效）；TC-ON-14 的 origin:"ai" 语义由生成环 payload 透传覆盖，
本模块补 author 手动注册通道（advanced 面）。
"""
import json
import sqlite3
import uuid

_LOCATION_TYPES = {"MicroBeat", "Scene", "Chapter"}  # 三类定位节点（D4/§4.8，多层定位）
_ORIGINS = {"author", "ai"}


def register(api, name: str, planted_at: str, origin: str = "author",
             payoff_beat: str | None = None, note: str = "") -> str:
    """注册伏笔：校验 planted_at/origin → 建 Foreshadow 节点事实提案，返回 pid。

    planted_at 必须是已有 MicroBeat/Scene/Chapter 节点 id（多层定位 D4/§4.8）；
    origin ∈ {"author", "ai"}。确认走 api.confirm，不在此物化。
    """
    conn: sqlite3.Connection = api._conn
    row = conn.execute(
        "SELECT types FROM nodes WHERE id=? AND active=1", (planted_at,)).fetchone()
    if row is None or not (_LOCATION_TYPES & set(json.loads(row["types"]))):
        raise ValueError(
            f"planted_at 必须是已有 MicroBeat/Scene/Chapter 节点 id: {planted_at}")
    if origin not in _ORIGINS:
        raise ValueError(f"origin 必须是 {'/'.join(sorted(_ORIGINS))}: {origin!r}")
    payload = {"facts": [{"fact": "node", "id": str(uuid.uuid4()),
                          "types": ["Foreshadow"], "name": name,
                          "props": {"foreshadow": {"planted_at": planted_at,
                                                   "origin": origin,
                                                   "payoff_beat": payoff_beat,
                                                   "note": note}}}]}
    return api.proposals.create("foreshadow", payload)
