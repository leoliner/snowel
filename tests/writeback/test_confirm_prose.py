# tests/writeback/test_confirm_prose.py
import json

import pytest


@pytest.fixture
def api(tmp_path):
    # 本地遮蔽 conftest.api：C1 断言文件落在 tmp_path/chapters 下，
    # 项目根须就是 tmp_path（conftest 版本在 tmp_path/api 子目录）
    from snowel_core.api import SnowelAPI
    a = SnowelAPI.init_project(tmp_path)
    yield a
    a.close()


def test_confirm_prose_writes_file_and_registers_hash(api, tmp_path):  # TC-WB-01
    pid = api.proposals.create("prose", {
        "chapter_id": "ch1", "content": "第一章：雨夜。"})
    seq = api.confirm(pid)
    assert seq > 0
    f = tmp_path / "chapters" / "ch1.md"
    assert f.read_text(encoding="utf-8") == "第一章：雨夜。"
    kinds = [r["kind"] for r in api._conn.execute(
        "SELECT kind FROM events ORDER BY seq")]
    assert kinds == ["proposal_confirmed", "prose_hash_registered"]
    row = api._conn.execute(
        "SELECT status FROM proposals WHERE id=?", (pid,)).fetchone()
    assert row["status"] == "confirmed"


def test_registered_write_shortcircuits_hook(api, tmp_path):  # TC-WB-02
    pid = api.proposals.create("prose", {
        "chapter_id": "ch1", "content": "第一章：雨夜。"})
    api.confirm(pid)
    from snowel_core.writeback import mirror
    assert mirror.reconcile(api._conn, tmp_path) == []  # 已登记写入不视为外部改动
    n = api._conn.execute(
        "SELECT count(*) c FROM events WHERE kind='prose_external_change'"
    ).fetchone()["c"]
    assert n == 0


def test_confirm_non_prose_unchanged(api):  # 回归：非正文提案路径不变
    pid = api.proposals.create("scene", {"facts": [
        {"fact": "node", "id": "sc9", "types": ["Scene"],
         "name": "s", "props": {}}]})
    seq = api.confirm(pid)
    assert seq > 0
    assert api.get_node("sc9") is not None


def test_confirm_exclude_filters_facts(api):  # TC-PR-09：整组确认可剔除（Task 14 消费）
    pid = api.proposals.create("scene", {"facts": [
        {"fact": "node", "id": "sc-a", "types": ["Scene"], "name": "a", "props": {}},
        {"fact": "node", "id": "sc-b", "types": ["Scene"], "name": "b", "props": {}}]})
    api.confirm(pid, exclude=["sc-a"])
    assert api.get_node("sc-a") is None  # 被剔除：不入图谱
    assert api.get_node("sc-b") is not None
    ev = api._conn.execute(
        "SELECT payload FROM events WHERE kind='proposal_confirmed'").fetchone()
    ids = [f["id"] for f in json.loads(ev["payload"])["facts"]]
    assert ids == ["sc-b"]  # 事件审计流也只携带保留事实
