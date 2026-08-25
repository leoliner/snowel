# src/snowel_core/consistency/engine.py
import sqlite3
from collections.abc import Callable

from ..proposal.queue import ProposalQueue

# Violation：{"level": "major"|"minor", "rule": str, "message": str, "refs": [节点/边 id]}
# Rule 协议（鸭子类型）：fn(change, conn) -> list[Violation]；
#   change 为变更集元素 {"kind": "node"|"edge"|"track"|"retraction", "fact": {...}, "seq": int}

TIERS: dict[str, set[str]] = {"light": set(), "full": set()}
_RULES: dict[str, Callable] = {}


def register(name: str, fn: Callable, tiers: tuple[str, ...] = ("full",)) -> None:
    """注册规则；同 name 后注册覆盖（E1：fn 与档位一并重设，重复注册互不污染）。"""
    _RULES[name] = fn
    for members in TIERS.values():          # 覆盖：先撤尽旧档位再入新档
        members.discard(name)
    for tier in tiers:
        TIERS[tier].add(name)


def run(conn: sqlite3.Connection, changes: list[dict], tier: str) -> list[dict]:
    """按档位逐变更执行注册规则，聚合去重（同 rule+refs 只留一条）。"""
    out: list[dict] = []
    seen: set[tuple] = set()
    for change in changes:
        for name in sorted(TIERS[tier]):    # 名字排序保证执行顺序确定
            for v in _RULES[name](change, conn):
                key = (v.get("rule"), tuple(v.get("refs", [])))
                if key not in seen:
                    seen.add(key)
                    out.append(v)
    return out


def diff_proposal(conn: sqlite3.Connection, violations: list[dict],
                  source_seq: int) -> str | None:
    """major 矛盾项组装 cascade_revision 提案入队返回 pid；无则 None（E5/P1 契约）。

    冲突条目 = Violation 的 detail（node_id/key/old/new）并入 refs。
    """
    conflicts = [v["detail"] | {"refs": v.get("refs", [])}
                 for v in violations
                 if v.get("level") == "major" and "detail" in v]
    if not conflicts:
        return None
    return ProposalQueue(conn).create("cascade_revision", {
        "conflicts": conflicts, "source_change_seq": source_seq})
