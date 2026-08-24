# src/snowel_core/writeback/deviation.py
import json
import sqlite3


def report(conn: sqlite3.Connection, chapter_id: str) -> dict:
    """C12 轻量偏离报告：确定性比对，零 LLM（P6 判据）。"""
    row = conn.execute("SELECT prose FROM chapter_prose WHERE chapter_id=?",
                       (chapter_id,)).fetchone()
    prose = row["prose"] if row else ""
    beats, scene = [], None
    for r in conn.execute("SELECT * FROM nodes WHERE active=1"):
        props = json.loads(r["props"])
        if props.get("chapter") != chapter_id:
            continue
        if "MicroBeat" in json.loads(r["types"]):
            beats.append(props)
        if "Scene" in json.loads(r["types"]) and scene is None:
            scene = props
    done = sum(1 for b in beats
               if all(k in prose for k in b.get("keywords", [])))
    missing = [e for e in (scene or {}).get("required_elements", [])
               if e not in prose]
    return {"microbeat": {"done": done, "total": len(beats)} if beats else None,
            "missing_elements": missing}
