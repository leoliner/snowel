# tests/storage/test_vec.py
from snowel_core.llm.embed import DeterministicEmbed
from snowel_core.storage import config, db, events, projector, vec


def _confirm(conn, facts):
    with db.transaction(conn):
        events.append_event(conn, "proposal_confirmed",
                            {"facts": facts, "artifact_type": "t"})
    projector.apply(conn)


def test_rebuild_and_knn_search(core_conn, tmp_path):
    from snowel_core.writeback import mirror
    vec.ensure(core_conn)
    _confirm(core_conn, [{"fact": "node", "id": "n1", "types": ["Character"],
                          "name": "林晚", "props": {}}])
    mirror.write_prose(core_conn, tmp_path, "ch1", "林晚在轮回游戏里攒积分")
    core_conn.execute("UPDATE chapter_prose SET prose=? WHERE chapter_id='ch1'",
                      ("林晚在轮回游戏里攒积分",))
    stats = vec.rebuild_embeddings(core_conn)
    assert stats == {"provider": "deterministic-hash-64",
                     "nodes": 1, "paragraphs": 1}
    r = vec.search(core_conn, "林晚", limit=5)
    assert {h["kind"] for h in r} == {"node", "paragraph"}


def test_switch_provider_rebuilds_per_project(core_conn, api, tmp_path):  # TC-RT-06
    # core_conn 与 api 是两个独立库：切换只重建该书
    vec.ensure(core_conn); vec.ensure(api._conn)
    _confirm(core_conn, [{"fact": "node", "id": "n1", "types": ["Character"],
                          "name": "林晚", "props": {}}])
    config.set(core_conn, "embedding.provider", "deterministic")  # 模拟"切换"
    a = vec.rebuild_embeddings(core_conn)
    assert config.get(core_conn, "embedding.built_with") == a["provider"]
    assert config.get(api._conn, "embedding.built_with") is None  # 另一书未动
