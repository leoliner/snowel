# src/snowel_core/flow/snowflake.py
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


def volume_start_state(conn, volume_id: str) -> dict:
    """C8：卷首世界状态实时重放（不落快照）；C9：事实取当前生效版。"""
    import json as _json
    from ..storage import queries
    end = 0
    for r in conn.execute(
            "SELECT id, props, types, story_order FROM nodes WHERE active=1"):
        if "MicroBeat" in _json.loads(r["types"]):
            end = max(end, r["story_order"] or 0)
    s = queries.state_at(conn, end)
    alive, mechs, foreshadows = [], [], []
    for n in s["nodes"]:  # state_at 已滤死亡角色：alive/mechanism/伏笔取当前生效集
        types = _json.loads(n["types"])
        if "Character" in types:
            alive.append(n["name"])
        if "Mechanism" in types:
            mechs.append({"name": n["name"],
                          "level": n.get("mechanism_level",
                                         n.get("core_level"))})
        if "Foreshadow" in types:
            foreshadows.append(n["name"])
    dead = []  # 死亡名单：state_at 过滤掉的人，从全量图按 death_beat 单独推导
    for r in conn.execute("SELECT name, props FROM nodes WHERE active=1"):
        props = _json.loads(r["props"])
        death = props.get("core", {}).get("death_beat")
        if death is None:
            continue
        d = queries.get_node(conn, death)
        if d is not None and d["story_order"] is not None \
                and d["story_order"] <= end:
            dead.append(r["name"])
    return {"story_order": end, "alive": alive, "dead": dead,
            "mechanisms": mechs, "open_foreshadows": foreshadows}


def expand_volume(api, volume_id: str, backend,
                  extra: dict | None = None) -> list[str]:
    start = volume_start_state(api._conn, volume_id)
    locate = {"volume": volume_id, "start_state": start}
    return [ai_generate(api, "volume_theme", locate, extra, backend),
            ai_generate(api, "volume_acts", locate, extra, backend)]
