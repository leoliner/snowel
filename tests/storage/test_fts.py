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


def test_fts_searchable_immediately_after_write_prose(core_conn, tmp_path):
    # 修复轮：write_prose 事务内 prose 水化后即重灌 FTS——无手动 UPDATE/refresh，
    # 首写章节立即可检（T6 混合回退、T12 引用提示依赖此语义）
    from snowel_core.writeback import mirror
    mirror.write_prose(core_conn, tmp_path, "chE",
                       "开篇\n\n林晚在雪夜里点燃了第七盏灯塔")
    r = fts.search(core_conn, "第七盏灯塔")
    assert r["paragraphs"] and r["paragraphs"][0]["chapter_id"] == "chE"
    assert r["paragraphs"][0]["para_idx"] == 1


def test_fts_searchable_immediately_after_reconcile(core_conn, tmp_path):
    # 修复轮扩展：reconcile 两分支（external_change / 空稿修复）水化后同事务重灌 FTS
    from snowel_core.writeback import mirror
    mirror.write_prose(core_conn, tmp_path, "chR", "旧稿\n\n第一段")
    f = mirror.prose_path(tmp_path, "chR")
    f.write_text("新稿\n\n管理员在雪夜换了灯塔钥匙", encoding="utf-8")
    mirror.reconcile(core_conn, tmp_path)  # (a) external_change 分支
    r = fts.search(core_conn, "灯塔钥匙")
    assert r["paragraphs"] and r["paragraphs"][0]["chapter_id"] == "chR"
    projector.rebuild(core_conn)  # (b) rebuild 模拟：重放后 prose 列回空、FTS 灌入空串
    mirror.reconcile(core_conn, tmp_path)  # 空稿修复分支
    r2 = fts.search(core_conn, "灯塔钥匙")
    assert r2["paragraphs"] and r2["paragraphs"][0]["chapter_id"] == "chR"


def test_fts_retraction_removes_hit(core_conn):
    _confirm(core_conn, [{"fact": "node", "id": "n1", "types": ["Concept"],
                          "name": "临时设定", "props": {}}])
    assert fts.search(core_conn, "临时设定")["nodes"]
    with db.transaction(core_conn):
        events.append_event(core_conn, "retraction",
                            {"target": "node", "target_id": "n1"})
    projector.apply(core_conn)
    assert fts.search(core_conn, "临时设定")["nodes"] == []
