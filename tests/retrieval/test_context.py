# tests/retrieval/test_context.py
import json
from snowel_core.retrieval import audit, context, hybrid
from snowel_core.storage import db, events, projector


def _confirm(conn, facts, kind="t"):
    with db.transaction(conn):
        events.append_event(conn, "proposal_confirmed",
                            {"facts": facts, "artifact_type": kind})
    projector.apply(conn)


def _seed_book(conn):
    _confirm(conn, [
        {"fact": "node", "id": "sc1", "types": ["Scene"], "name": "雨夜初见",
         "props": {"characters": ["hero"], "required_elements": ["雨夜"],
                   "chapter": "ch1"}},
        {"fact": "node", "id": "hero", "types": ["Character"], "name": "林晚",
         "props": {"core": {"motivation": "活下来", "lie": "没人会救我",
                            "fear": "深渊", "arc": "学会信任"}}},
        {"fact": "node", "id": "dead1", "types": ["Character"], "name": "旧队友",
         "props": {"core": {"death_beat": "mb0", "motivation": "x",
                            "lie": "x", "fear": "x", "arc": "x"}}},
        {"fact": "node", "id": "mb0", "types": ["MicroBeat"], "name": "开场",
         "props": {"address": {"volume": 1, "chapter": 1, "scene": 1, "beat": 1}}},
        {"fact": "node", "id": "mb1", "types": ["MicroBeat"], "name": "遇难",
         "props": {"address": {"volume": 1, "chapter": 1, "scene": 1, "beat": 2}}},
        {"fact": "node", "id": "fs1", "types": ["Foreshadow"], "name": "怀表",
         "props": {"planted_at": "mb0"}},
        {"fact": "node", "id": "todo1", "types": ["Concept"], "name": "待补设定",
         "props": {"core": {"todo": True}}},
        {"fact": "node", "id": "w1", "types": ["Concept"], "name": "轮回游戏",
         "props": {}},
    ])


def test_compose_context_prose_strategy(core_conn):  # TC-RT-01
    _seed_book(core_conn)
    bundle = context.compose_context(
        core_conn, "prose", locate={"chapter": "ch1", "story_order": 1})
    kinds = [s["kind"] for s in bundle["sections"]]
    assert kinds == ["scene_card", "characters", "foreshadows", "worldview"]
    chars = bundle["sections"][1]
    assert chars["refs"] == ["hero"]                    # 死亡角色（death_beat=mb0≤1）被过滤
    world = bundle["sections"][3]
    assert "todo1" not in [r for s in bundle["sections"] for r in s["refs"]]  # TODO 排除
    assert "w1" in world["refs"]


def test_compose_context_dry_run_audited(core_conn):  # TC-RT-02
    _seed_book(core_conn)
    b1 = context.compose_context(core_conn, "generic", locate={"query": "轮回"},
                                 dry_run=True)
    rows = audit.recent(core_conn)
    assert len(rows) == 1 and rows[0]["dry_run"] == 1
    assert rows[0]["id"] == b1["audit_id"]
    context.compose_context(core_conn, "generic", locate={"query": "轮回"})
    assert audit.recent(core_conn)[0]["dry_run"] == 0   # 非 dry_run 标注 0


def test_hybrid_search_marks_dead(core_conn):  # TC-RT-03 兜底标记
    _seed_book(core_conn)
    r = hybrid.search(core_conn, "旧队友")
    dead = [h for h in r["nodes"] if h["node_id"] == "dead1"]
    # mb0 → story_order 0（recompute_story_order 派生序 0 基），附"已死亡@拍"
    assert dead and dead[0]["dead_beat"] == 0


def test_fallback_recall_excludes_todo(core_conn):  # TODO 不进任何 section：兜底召回同理
    _seed_book(core_conn)
    _confirm(core_conn, [
        {"fact": "node", "id": "todo2", "types": ["Concept"], "name": "轮回规则草稿",
         "props": {"core": {"todo": True}}}])
    bundle = context.compose_context(
        core_conn, "generic", locate={"query": "轮回"})
    fb = [s for s in bundle["sections"] if s["kind"] == "fallback_recall"]
    assert fb and "w1" in fb[0]["refs"]
    assert "todo2" not in fb[0]["refs"]        # refs 不含 TODO 命中
    assert "todo2" not in fb[0]["text"]        # text 载荷同样排除


def test_foreshadows_only_unrecovered(core_conn):  # 已回收伏笔不进 section
    _seed_book(core_conn)
    _confirm(core_conn, [
        {"fact": "node", "id": "fs2", "types": ["Foreshadow"], "name": "信物",
         "props": {"core": {"payoff_beat": "mb0"}}},  # 回收拍 mb0→story_order 0≤1：已回收
        {"fact": "node", "id": "fs3", "types": ["Foreshadow"], "name": "暗门",
         "props": {"core": {"payoff_beat": "nb"}}},   # 回收拍未编址（序 None）：仍开放
        {"fact": "node", "id": "nb", "types": ["MicroBeat"], "name": "终局",
         "props": {}},
    ])
    bundle = context.compose_context(
        core_conn, "prose", locate={"chapter": "ch1", "story_order": 1})
    fs = bundle["sections"][2]
    assert fs["refs"] == ["fs1", "fs3"]        # fs1 无 payoff 开放；fs2 已回收剔除
