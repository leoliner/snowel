import shutil

import pytest

from snowel_core import api as sapi
from snowel_core.api import SnowelAPI

def test_api_facade_end_to_end(tmp_path):
    core = sapi.SnowelAPI.init_project(tmp_path / "book")
    pid = core.proposals.create("scene", {"facts": [
        {"fact": "node", "id": "n1", "types": ["Character"], "name": "林晚",
         "props": {"core": {"motivation": "活下去", "lie": "x", "fear": "y", "arc": "z"}}}]})
    core.proposals.confirm(pid)
    n = core.get_node("n1")
    assert n["name"] == "林晚"
    assert core.find_nodes(name="林晚")[0]["id"] == "n1"
    core.rebuild()
    assert core.get_node("n1")["name"] == "林晚"     # rebuild 后状态一致
    core.close()


def test_backup_roundtrip_equivalent(tmp_path):
    api = SnowelAPI.init_project(tmp_path)
    pid = api.proposals.create("scene", {"facts": [
        {"fact": "node", "id": "n1", "types": ["Character"],
         "name": "林晚", "props": {}}]})
    api.proposals.confirm(pid)
    out = tmp_path / "b.db"
    api.backup(out)
    restore = tmp_path / "restore"
    restore.mkdir()
    shutil.copy(out, restore / "snowel.db")
    api2 = SnowelAPI.open(restore)
    try:
        assert api2.graph_stats() == api.graph_stats()
        assert [r["status"] for r in api2.proposals.list()] == ["confirmed"]
    finally:
        api2.close()
    api.close()


def test_backup_refuses_overwrite(tmp_path):
    api = SnowelAPI.init_project(tmp_path)
    out = tmp_path / "b.db"
    out.write_bytes(b"x")
    with pytest.raises(FileExistsError):
        api.backup(out)
    api.close()


def test_search_and_audit_recent_facades(tmp_path):
    from snowel_core.storage import config
    api = SnowelAPI.init_project(tmp_path)
    try:
        # 改写层默认开会尝试 LLM（无 backend 环境即失败落审计）——本测锚定
        # 门面接线的确定性路径，显式关闭
        config.set(api._conn, "retrieval.rewrite", False)
        assert api.search("林晚") == {"nodes": [], "paragraphs": []}
        assert api.audit_recent() == []  # 空 audit 表（Task 18 门面接线）
    finally:
        api.close()


def test_search_default_limit_unified_with_fts(tmp_path, monkeypatch):
    # L21：门面默认 limit=100（与 fts 内部默认统一）；不传 limit 时向下逐层
    # 透传的行为锚（替换 retrieval.hybrid.search 捕获实收值）
    import snowel_core.retrieval.hybrid as hybrid

    seen = {}

    def _capture(conn, q, limit, mode):
        seen["limit"] = limit
        return {}

    monkeypatch.setattr(hybrid, "search", _capture)
    api = SnowelAPI.init_project(tmp_path)
    try:
        api.search("林晚")
    finally:
        api.close()
    assert seen["limit"] == 100


def test_export_prose_ordered_from_mirror(tmp_path):
    api = SnowelAPI.init_project(tmp_path)
    try:
        for cid, text in (("ch2", "第二章。"), ("ch1", "第一章。")):
            pid = api.proposals.create("prose", {
                "chapter_id": cid, "content": text})
            api.confirm(pid)
        rows = api.export_prose()
        assert rows == [{"chapter_id": "ch1", "prose": "第一章。"},
                        {"chapter_id": "ch2", "prose": "第二章。"}]  # 按 chapter_id 排序
    finally:
        api.close()


def test_current_lease_holder_readonly_facade(tmp_path):
    api = SnowelAPI.init_project(tmp_path)
    try:
        assert api.current_lease_holder() is None
        assert api.acquire_lease("holder-a")
        assert api.current_lease_holder() == "holder-a"
    finally:
        api.close()


def test_latest_extract_proposal_facade(tmp_path):
    # 终审修复 F4：壳 writeback result 的"最近抽取提案"领域语义下沉 core 门面
    api = SnowelAPI.init_project(tmp_path)
    try:
        assert api.latest_extract_proposal() is None
        api.proposals.create("extract_facts", {"facts": []})
        # 时间戳钉死确保排序确定（Windows 上连续 now 可能同值）
        api._conn.execute(
            "UPDATE proposals SET created_ts='2000-01-01T00:00:00+00:00' "
            "WHERE kind='extract_facts'")
        api._conn.commit()
        newer = api.proposals.create("extract_facts", {"facts": []})
        api._conn.execute(
            "UPDATE proposals SET created_ts='2001-01-01T00:00:00+00:00' "
            "WHERE id=?", (newer,))
        api._conn.commit()
        # 更晚创建的非抽取提案不参与（kind 过滤在 core）
        api.proposals.create("premise", {"draft": "x"})
        api._conn.execute(
            "UPDATE proposals SET created_ts='2002-01-01T00:00:00+00:00' "
            "WHERE kind='premise'")
        api._conn.commit()
        row = api.latest_extract_proposal()
        assert row["id"] == newer          # 取 created_ts 最新的 extract_facts
        assert row["kind"] == "extract_facts"
    finally:
        api.close()
