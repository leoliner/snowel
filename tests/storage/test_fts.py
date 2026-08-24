# tests/storage/test_fts.py
from snowel_core.storage import db, events, fts, projector


def _confirm(conn, facts):
    with db.transaction(conn):
        events.append_event(conn, "proposal_confirmed",
                            {"facts": facts, "artifact_type": "t"})
    projector.apply(conn)


def test_fts_finds_node_by_name_and_alias(core_conn):
    _confirm(core_conn, [{"fact": "node", "id": "n1",
                          "types": ["Character"], "name": "江晚",
                          "props": {"core": {"motivation": "活下去"}}}])
    with db.transaction(core_conn):
        events.append_event(core_conn, "retcon_applied", {"renames": [
            {"node_id": "n1", "old_name": "林晚", "new_name": "江晚"}]})
    projector.apply(core_conn)
    r = fts.search(core_conn, "林晚")          # TC-ON-02 FTS 面：旧名经 alias 命中
    assert [h["node_id"] for h in r["nodes"]] == ["n1"]
    r2 = fts.search(core_conn, "活下去")        # props 扁平文本命中
    assert [h["node_id"] for h in r2["nodes"]] == ["n1"]


def test_fts_finds_prose_paragraph(core_conn, tmp_path):
    from snowel_core.writeback import mirror
    mirror.write_prose(core_conn, tmp_path, "ch1", "第一段：林晚登场\n\n第二段：积分兑换")
    core_conn.execute(
        "UPDATE chapter_prose SET prose=? WHERE chapter_id='ch1'",
        ("第一段：林晚登场\n\n第二段：积分兑换",))
    fts.refresh(core_conn)
    r = fts.search(core_conn, "积分兑换")
    assert r["paragraphs"] and r["paragraphs"][0]["para_idx"] == 1
    assert r["paragraphs"][0]["chapter_id"] == "ch1"


def test_fts_retraction_removes_hit(core_conn):
    _confirm(core_conn, [{"fact": "node", "id": "n1", "types": ["Concept"],
                          "name": "临时设定", "props": {}}])
    assert fts.search(core_conn, "临时设定")["nodes"]
    with db.transaction(core_conn):
        events.append_event(core_conn, "retraction",
                            {"target": "node", "target_id": "n1"})
    projector.apply(core_conn)
    assert fts.search(core_conn, "临时设定")["nodes"] == []
