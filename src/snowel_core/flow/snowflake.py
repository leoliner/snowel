# src/snowel_core/flow/snowflake.py
import json

from ..retrieval.context import unrecovered
from ..storage import deathbeat, queries
from .generate import ai_generate


def expand_chapter(api, chapter_id: str, backend,
                   extra: dict | None = None) -> list[str]:
    """小雪花 = 受限展开（§5.1）：档案现成直接拉取，只产提案不自动确认。"""
    locate = {"chapter": chapter_id}
    return [
        ai_generate(api, "chapter_intent", locate, extra, backend),
        ai_generate(api, "microbeat_group", locate, extra, backend),
        ai_generate(api, "prose", locate, extra, backend),
    ]


def _prior_volume_end(conn, volume_id: str) -> int:
    """上一卷末拍（C8）：目标卷带 address.volume=N → 编址卷号 < N 的节点
    （卷/章/拍）story_order 最大值；卷节点无地址（旧库，或滚动展开写 N+1
    时后卷尚不存在）→ 全图 MicroBeat 最大值兜底，即上一卷末拍。"""
    vol = queries.get_node(conn, volume_id)
    v = ((json.loads(vol["props"]).get("address") or {}) if vol is not None
         else {}).get("volume")
    end = 0
    for r in conn.execute(
            "SELECT props, types, story_order FROM nodes WHERE active=1"):
        if v is not None:
            nv = (json.loads(r["props"]).get("address") or {}).get("volume")
            if nv is not None and nv < v and r["story_order"] is not None:
                end = max(end, r["story_order"])
        elif "MicroBeat" in json.loads(r["types"]):
            end = max(end, r["story_order"] or 0)
    return end


def volume_start_state(conn, volume_id: str) -> dict:
    """C8：卷首世界状态实时重放（不落快照）；C9：事实取当前生效版。"""
    end = _prior_volume_end(conn, volume_id)
    s = queries.state_at(conn, end)
    alive, mechs, foreshadows = [], [], []
    for n in s["nodes"]:  # state_at 已滤死亡角色：alive/mechanism/伏笔取当前生效集
        types = json.loads(n["types"])
        if "Character" in types:
            alive.append(n["name"])
        if "Mechanism" in types:
            mechs.append({"name": n["name"],
                          "level": n.get("mechanism_level",
                                         n.get("core_level"))})
        if "Foreshadow" in types and unrecovered(conn, n, end):
            foreshadows.append(n["name"])  # 已回收（payoff ≤ end）剔除
    dead = []  # 死亡名单：deathbeat 统一口径（L13：死亡拍停用 → 保守存活）
    for r in conn.execute("SELECT name, props FROM nodes WHERE active=1"):
        if deathbeat.is_dead(conn, r, end):
            dead.append(r["name"])
    return {"story_order": end, "alive": alive, "dead": dead,
            "mechanisms": mechs, "open_foreshadows": foreshadows}


def expand_volume(api, volume_id: str, backend,
                  extra: dict | None = None) -> list[str]:
    start = volume_start_state(api._conn, volume_id)
    locate = {"volume": volume_id, "start_state": start}
    return [ai_generate(api, "volume_theme", locate, extra, backend),
            ai_generate(api, "volume_acts", locate, extra, backend)]
