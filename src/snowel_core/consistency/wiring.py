# src/snowel_core/consistency/wiring.py
"""四写入点接线助手（E5）：变更集构造 + 跑档 + major 矛盾 diff 提案。

rules 模块在导入时注册全部内置规则——生产路径首次 import 本模块即激活
（"注册休眠"，T3 挂账）；E1 覆盖式 register 保证与测试内手动注册互不污染。
级联分析只读（P1）；diff 提案是主事务之后的独立写入（P2），均不阻断主流程。
"""
import sqlite3

from ..storage import events
from . import engine, rules  # noqa: F401  rules 导入即注册全部内置规则


def change_set_from_facts(facts: list[dict], seq: int) -> list[dict]:
    """事实列表 → 引擎变更集：事实的 "fact" 键即 kind，其余键原样进 fact。"""
    return [{"kind": f.get("fact"),
             "fact": {k: v for k, v in f.items() if k != "fact"},
             "seq": seq}
            for f in facts]


def analyze(conn: sqlite3.Connection, facts: list[dict], tier: str,
            seq: int | None = None) -> list[dict]:
    """只读跑档（P1），比对基线 = 调用时的生效集。

    需要变更前基线的写入点（api.confirm）必须在主事务前调用——projector
    会在确认事务内覆写物化值，事后分析回看不到旧值；seq 缺省取当前事件头
    仅作变更集记账（内置规则不消费，source_seq 由 finalize 持真值）。
    """
    if seq is None:
        seq = events.head_seq(conn)
    return engine.run(conn, change_set_from_facts(facts, seq), tier)


def finalize(conn: sqlite3.Connection, violations: list[dict], seq: int,
             tier: str) -> dict:
    """主事务后收尾（P2）：major 矛盾组装 cascade_revision 提案独立入队。"""
    return {"tier": tier, "violations": violations,
            "cascade_proposal_id": engine.diff_proposal(conn, violations, seq)}


def after_commit(conn: sqlite3.Connection, facts: list[dict], seq: int,
                 tier: str) -> dict:
    """主事务后一站式跑档：analyze + finalize。

    分析基线是调用时的生效集——主事务已物化覆写同键值时比对不到旧值；
    需要变更前基线的写入点（confirm / extract）须拆 analyze→主事务→
    finalize 两段式（见各自接线），本口仅供 retraction 写入点直用。
    """
    return finalize(conn, analyze(conn, facts, tier), seq, tier)


def preview(conn: sqlite3.Connection, facts: list[dict],
            tier: str = "full") -> dict:
    """只读预演门面（cascade_check，Web/advanced 用）：跑档 + diff 预览不入队。

    conflicts 口径与 engine.diff_proposal 一致（major + detail → 冲突条目）。
    """
    violations = analyze(conn, facts, tier)
    conflicts = [v["detail"] | {"refs": v.get("refs", [])}
                 for v in violations
                 if v.get("level") == "major" and "detail" in v]
    return {"tier": tier, "violations": violations, "diff_preview": conflicts}
