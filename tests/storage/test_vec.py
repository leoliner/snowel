# tests/storage/test_vec.py
import pytest

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


def test_rebuild_embeddings_atomic_on_failure(core_conn, tmp_path, monkeypatch):
    # L8：DELETE+INSERT+config.set 须同事务——写入阶段中途失败整体回滚，
    # 不留"旧向量已清、新向量未灌"的空窗。第二次重建前追加新节点/新章，
    # 使"半提交"（node_vec 含新旧全部）与"完整回滚"（仅旧数据）可区分
    from snowel_core.writeback import mirror
    import snowel_core.storage.vec as vecmod
    vec.ensure(core_conn)
    _confirm(core_conn, [{"fact": "node", "id": "n1", "types": ["Character"],
                          "name": "林晚", "props": {}}])
    mirror.write_prose(core_conn, tmp_path, "ch1", "林晚攒积分")
    vec.rebuild_embeddings(core_conn)
    built = config.get(core_conn, "embedding.built_with")

    _confirm(core_conn, [{"fact": "node", "id": "n2", "types": ["Concept"],
                          "name": "灯塔", "props": {}}])
    mirror.write_prose(core_conn, tmp_path, "ch2", "第二章正文")

    def _boom(conn, key, value):
        raise RuntimeError("写 config 失败")
    monkeypatch.setattr(vecmod.config, "set", _boom)
    with pytest.raises(RuntimeError):
        vec.rebuild_embeddings(core_conn)  # 写阶段尾段失败
    assert core_conn.execute(
        "SELECT COUNT(*) c FROM node_vec").fetchone()["c"] == 1  # 新节点未半提交
    assert core_conn.execute(
        "SELECT COUNT(*) c FROM prose_vec").fetchone()["c"] == 1
    assert config.get(core_conn, "embedding.built_with") == built
