# extensions/infinite-flow/hooks.py
"""无限流包示范规则：排名轨迹写入须附轨迹方向（R2）。

分工示范：direction 在 schema 上刻意 optional（形状归 schema），
跨字段语义义务（写入轨迹组必须交代方向）归本规则（语义归 hooks）。
"""
import sqlite3


def register(registry):
    registry.rule("flow_rank_track_direction_required", _check)


def _check(change: dict, conn: sqlite3.Connection) -> list[dict]:
    """规则 fn 契约与内置规则同款（consistency/rules.py）：只读不阻断。"""
    if change.get("kind") != "node":
        return []
    fact = change.get("fact", {})
    track = fact.get("props", {}).get("flow_rank_track")
    # 空值双态：键缺失与空串都算未交代方向（direction 合法值均为非空词）
    if not isinstance(track, dict) or track.get("direction"):
        return []
    return [{"level": "major", "rule": "flow_rank_track_direction_required",
             "message": "排名轨迹写入须附轨迹方向 direction",
             "refs": [fact["id"]]}]
