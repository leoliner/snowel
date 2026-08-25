# src/snowel_core/consistency/retcon.py
"""显式 retcon 流程（C7 冻结线合法通道，TC-CC-07）：propose 全量级联 + 确认物化 + C5 精确 stale。

P5：影响分析在 propose_retcon 时跑全量档（facts + renames 对端节点 + track_updates
→ engine.run(full)），影响清单进提案 payload，确认后不重跑（分析与确认间世界
变化的窗口由 C5 stale 补偿）。P4：依赖图精确分析 v1 = 变更触及节点 id 集 ∩
pending 提案 payload json 串含该 id → 只标受影响提案（替代 T17 全 pending
保守标记；revision 面同步切换到本助手）。L14：stale 批量在单事务内完成
（逐条 stale_marked 事件 + UPDATE，不逐条开事务）。
"""
import json
import sqlite3

from ..storage import db, events, projector
from . import engine, wiring  # wiring 顶层导入即注册全部内置规则


def _touched_ids(facts: list[dict], renames: list[dict],
                 track_updates: list[dict]) -> set[str]:
    """变更触及节点 id 集（P4）：node fact id、edge fact src/dst、rename 的
    node_id、track_update 的 track_id。"""
    ids: set[str] = set()
    for f in facts:
        if f.get("fact") == "node":
            if f.get("id"):
                ids.add(f["id"])
        elif f.get("fact") == "edge":
            ids.update({f.get("src"), f.get("dst")})
    for r in renames:
        if r.get("node_id"):
            ids.add(r["node_id"])
    for t in track_updates:
        if t.get("track_id"):
            ids.add(t["track_id"])
    return {i for i in ids if i}


def affected_pending(conn: sqlite3.Connection, node_ids: set[str]) -> list[str]:
    """P4 依赖图精确分析：pending 提案 payload（json 串）包含任一触及 id → pid 列表。

    字符串包含是保守超集（误标不漏标），真正的语义依赖图属后续优化。
    """
    if not node_ids:
        return []
    return [r["id"] for r in conn.execute(
        "SELECT id, payload FROM proposals WHERE status='pending' ORDER BY created_ts")
        if any(i in r["payload"] for i in node_ids)]


def mark_stale_batch(conn: sqlite3.Connection, pids: list[str], hint: str) -> None:
    """L14：C5 stale 批量标记——单事务内逐条 stale_marked 事件 + UPDATE（不逐条开事务）。"""
    with db.transaction(conn):
        for pid in pids:
            events.append_event(conn, "stale_marked",
                                {"proposal_id": pid, "hint": hint})
            conn.execute(
                "UPDATE proposals SET status='stale', stale_hint=? WHERE id=?",
                (hint, pid))


def propose_retcon(api, facts: list[dict] | None = None,
                   renames: list[dict] | None = None,
                   track_updates: list[dict] | None = None,
                   reason: str = "") -> dict:
    """提案创建即全量级联（P5）：facts + renames 对端节点 + track_updates 跑
    engine.run(full)，影响清单（violations + 受影响 pending 提案）入提案 payload。

    返回 {"proposal_id", "impact"}；confirm_retcon 后不重跑分析。
    """
    facts, renames, track_updates = facts or [], renames or [], track_updates or []
    if not (facts or renames or track_updates):
        raise ValueError("retcon 至少需要一项变更（facts/renames/track_updates）")
    conn = api._conn
    seq = events.head_seq(conn)
    changes = wiring.change_set_from_facts(facts, seq)
    changes += [{"kind": "node",
                 "fact": {"id": r["node_id"], "name": r["new_name"]}, "seq": seq}
                for r in renames]
    changes += [{"kind": "track", "fact": t, "seq": seq} for t in track_updates]
    impact = {"violations": engine.run(conn, changes, "full"),
              "affected_proposals": affected_pending(
                  conn, _touched_ids(facts, renames, track_updates))}
    pid = api.proposals.create("retcon", {
        "facts": facts, "renames": renames, "track_updates": track_updates,
        "reason": reason, "impact": impact})
    return {"proposal_id": pid, "impact": impact}


def confirm_retcon(api, proposal_id: str) -> int:
    """retcon 专属确认（冻结线豁免，不拦 is_sealed）：单事务两条事件
    ——proposal_confirmed（facts 物化）+ retcon_applied（renames/track_updates
    物化 + impact 摘要），保 D1 检查点一致性；事务后 C5 精确 stale（L14 批量）。

    返回 proposal_confirmed 事件 seq。
    """
    p = api.proposals.get(proposal_id)
    if p is None or p["kind"] != "retcon":
        raise ValueError(f"提案 {proposal_id} 不是 retcon 提案，无法走 retcon 确认")
    if p["status"] != "pending":
        raise ValueError(f"提案 {proposal_id} 状态为 {p['status']}，仅 pending 可确认")
    payload = json.loads(p["payload"])
    facts, renames, track_updates = (payload.get("facts", []),
                                     payload.get("renames", []),
                                     payload.get("track_updates", []))
    with db.transaction(api._conn):
        seq = events.append_event(api._conn, "proposal_confirmed", {
            "proposal_id": proposal_id, "artifact_type": "retcon",
            "facts": facts, "appeared": []})
        events.append_event(api._conn, "retcon_applied", {
            "renames": renames, "track_updates": track_updates,
            "impact": payload.get("impact", {})})
        projector.apply(api._conn)
        api._conn.execute("UPDATE proposals SET status='confirmed' WHERE id=?",
                          (proposal_id,))
    pids = affected_pending(api._conn, _touched_ids(facts, renames, track_updates))
    if pids:
        mark_stale_batch(api._conn, pids,
                         f"上游 retcon：{payload.get('reason') or '设定变更'}")
    return seq
