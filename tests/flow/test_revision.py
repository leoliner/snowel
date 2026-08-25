# tests/flow/test_revision.py
import json
from tests.conftest import FakeBackend
from snowel_core.flow import revision
from snowel_core.storage import db, events, projector


def _seed_two_volumes(api):
    with db.transaction(api._conn):
        events.append_event(api._conn, "proposal_confirmed", {
            "artifact_type": "structure", "facts": [
                {"fact": "node", "id": "v1", "types": ["Volume"], "name": "卷一",
                 "props": {}},
                {"fact": "node", "id": "v2", "types": ["Volume"], "name": "卷二",
                 "props": {}},
                {"fact": "node", "id": "c5", "types": ["Chapter"], "name": "第5章",
                 "props": {"volume": "v2",
                           "address": {"volume": 2, "chapter": 1,
                                       "scene": 0, "beat": 0}}},
                {"fact": "node", "id": "c9", "types": ["Chapter"], "name": "第9章",
                 "props": {"volume": "v2",
                           "address": {"volume": 2, "chapter": 2,
                                       "scene": 0, "beat": 0}}}]})
        projector.apply(api._conn)


def test_revision_unified_flow(api):  # TC-FL-06：章改卷走统一提案→确认
    _seed_two_volumes(api)
    pid = api.propose_revision("c5", {"volume": 1, "chapter": 9,
                                      "scene": 0, "beat": 0}, reason="章改卷")
    assert api.proposals.get(pid)["kind"] == "revision"
    seq = api.confirm(pid)
    ev = api._conn.execute(
        "SELECT payload FROM events WHERE kind='revision_applied'").fetchone()
    p = json.loads(ev["payload"])
    assert p["structure_changes"][0]["node_id"] == "c5"
    assert json.loads(api.get_node("c5")["props"])["address"]["volume"] == 1
    assert api.get_node("c5")["story_order"] < api.get_node("c9")["story_order"]


def test_revision_marks_pending_stale(api):  # C5（revision 面，P4 精确）
    _seed_two_volumes(api)
    other = api.proposals.create("scene", {"draft": "x"})   # 不引用 c5 → 不标
    touched = api.proposals.create("scene", {
        "draft": "x", "mention": {"c5": "章节"}})           # 引用 c5 → 标 stale
    pid = api.propose_revision("c5", {"volume": 1, "chapter": 9,
                                      "scene": 0, "beat": 0})
    api.confirm(pid)
    assert api.proposals.get(other)["status"] == "pending"  # 精确 stale：无关不标
    row = api.proposals.get(touched)
    assert row["status"] == "stale"
    assert "revision" in row["stale_hint"]


def test_rewrite_proposal_keeps_original(api):
    p1 = api.proposals.create("premise", {"draft": "原稿"})
    fake = FakeBackend([json.dumps({"draft": "改写稿", "facts": [],
                                     "appeared": []}, ensure_ascii=False)])
    p2 = api.rewrite_proposal(p1, "更黑暗一点", backend=fake)
    assert api.proposals.get(p2)["status"] == "pending"
    assert json.loads(api.proposals.get(p2)["payload"])["rewritten_from"] == p1
    assert api.proposals.get(p1)["status"] == "pending"   # 原提案不动


def test_rewrite_accepts_fenced_response(api):  # T8 同款：真实模型裹围栏
    p1 = api.proposals.create("premise", {"draft": "原稿"})
    fenced = "```json\n" + json.dumps({"draft": "改写稿", "facts": [],
                                       "appeared": []},
                                      ensure_ascii=False) + "\n```"
    p2 = api.rewrite_proposal(p1, "更黑暗一点", backend=FakeBackend([fenced]))
    assert json.loads(api.proposals.get(p2)["payload"])["draft"] == "改写稿"


def test_rewrite_prose_syncs_content_for_confirm_chain(api):
    # 终审修复 F1：prose 提案改写后 content 须随 draft 同步——
    # 确认代写/重登记读 payload["content"]，不同步会落盘改写前旧文（静默错典）
    gen = FakeBackend([json.dumps({"draft": "旧正文V1", "facts": [],
                                   "appeared": []}, ensure_ascii=False)])
    pid = api.ai_generate("prose", locate={"chapter": "ch1"}, backend=gen)
    rw = FakeBackend([json.dumps({"draft": "改写后正文V2", "facts": [],
                                  "appeared": []}, ensure_ascii=False)])
    pid2 = api.rewrite_proposal(pid, "改写", backend=rw)
    assert json.loads(api.proposals.get(pid2)["payload"])["content"] == "改写后正文V2"
    api.confirm(pid2)
    f = api._root / "chapters" / "ch1.md"
    assert f.read_text(encoding="utf-8") == "改写后正文V2"   # 落盘的是改写稿
    assert api._conn.execute(
        "SELECT prose FROM chapter_prose WHERE chapter_id='ch1'"
    ).fetchone()["prose"] == "改写后正文V2"
    from snowel_core.writeback import mirror
    assert mirror.reconcile(api._conn, api._root) == []     # 哈希按新文登记
    f.unlink()                                             # 模拟崩溃窗口
    assert api.reregister_prose(pid2) == "ch1"              # 重放同样拿新文
    assert f.read_text(encoding="utf-8") == "改写后正文V2"
