# src/snowel_core/flow/state.py
import json
import sqlite3

LAYERS = ["premise", "synopsis", "summary", "beat_sheet",
          "characters", "scenes", "prose"]

_LAYER_ALIASES = {"scenes": "scene"}  # 层名与提案 kind 不一致处（LAYERS 复数 vs kind 单数）


def flow_state(conn: sqlite3.Connection) -> dict:
    """雪花流程状态：层进度 + 卷章树（TC-FL-03：只报存在物，未展开不报缺）。"""
    done_kinds = {r["kind"] for r in conn.execute(
        "SELECT DISTINCT p.kind FROM proposals p WHERE p.status='confirmed'")}
    layers = {k: ("done" if k in done_kinds
                  or _LAYER_ALIASES.get(k) in done_kinds else "todo")
              for k in LAYERS}
    volumes = []
    for v in conn.execute(
            "SELECT id, name, types FROM nodes WHERE active=1"):
        types = json.loads(v["types"])
        if "Volume" in types:
            volumes.append({"id": v["id"], "name": v["name"], "chapters": []})
    for c in conn.execute(
            "SELECT id, name, types, props FROM nodes WHERE active=1"):
        props = json.loads(c["props"])
        if "Chapter" not in json.loads(c["types"]):
            continue
        for v in volumes:
            if v["id"] == props.get("volume"):
                v["chapters"].append({"id": c["id"], "name": c["name"]})
    current = next((k for k in LAYERS if layers[k] == "todo"), None)
    return {"layers": layers, "current_layer": current, "volumes": volumes}
