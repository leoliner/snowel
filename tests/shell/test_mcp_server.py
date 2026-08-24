# tests/shell/test_mcp_server.py
import json
from contextlib import asynccontextmanager

import pytest
from mcp.shared.memory import create_connected_server_and_client_session

from snowel.mcp_server import build_mcp
from snowel.project import open_project
from snowel_core.api import SnowelAPI
from tests.conftest import FakeBackend

pytestmark = pytest.mark.anyio


@pytest.fixture
def anyio_backend():
    return "asyncio"


FACTS = [{"fact": "node", "id": "n1", "types": ["Character"],
          "name": "林晚", "props": {}}]


@pytest.fixture
def project(tmp_path):
    SnowelAPI.init_project(tmp_path)
    return tmp_path


@asynccontextmanager
async def _connected(project, backend=None, **kw):
    ctx = open_project(project, **kw)
    try:
        mcp = build_mcp(ctx, backend=backend)
        async with create_connected_server_and_client_session(
                mcp._mcp_server) as client:
            yield ctx, client
    finally:
        ctx.close()


async def _call(client, name, args):
    res = await client.call_tool(name, args)
    assert not res.isError
    return json.loads(res.content[0].text)


def _assert_not_wired(d, capability):
    assert d["wired"] is False
    assert d["capability"] == capability
    assert d["planned_in"]
    assert d["message"]


async def test_exactly_six_tools(project):  # TC-SH-01
    async with _connected(project) as (ctx, client):
        tools = await client.list_tools()
        assert {t.name for t in tools.tools} == {
            "snowel_status", "snowel_generate", "snowel_query",
            "snowel_proposal", "snowel_writeback", "snowel_advanced"}


async def test_status_reports_graph_and_proposals(project):
    api = SnowelAPI.open(project)
    api.proposals.create("premise", {"facts": FACTS})
    api.close()
    async with _connected(project) as (ctx, client):
        d = await _call(client, "snowel_status", {})
        assert d["readonly"] is False
        assert d["proposals"] == {"pending": 1}
        assert d["graph"]["nodes"] == 0
        assert d["flow"]["layers"]


async def test_status_reports_flow(project):
    api = SnowelAPI.open(project)
    pid = api.proposals.create("premise", {"draft": "x"})
    api.proposals.confirm(pid)
    api.close()
    async with _connected(project) as (ctx, client):
        d = await _call(client, "snowel_status", {})
        assert d["flow"]["layers"]["premise"] == "done"
        assert d["flow"]["current_layer"] == "synopsis"


async def test_proposal_end_to_end(project):
    api = SnowelAPI.open(project)
    pid = api.proposals.create("scene", {"facts": FACTS})
    api.close()
    async with _connected(project) as (ctx, client):
        listed = await _call(client, "snowel_proposal", {"action": "list"})
        assert listed["result"][0]["id"] == pid
        done = await _call(client, "snowel_proposal",
                           {"action": "confirm", "proposal_id": pid})
        assert done["event_seq"] >= 1
    api = SnowelAPI.open(project)
    try:
        assert [r["status"] for r in api.proposals.list()] == ["confirmed"]
        assert api.graph_stats()["nodes"] == 1
    finally:
        api.close()


async def test_query_routes_graph_actions(project):
    api = SnowelAPI.open(project)
    pid = api.proposals.create("scene", {"facts": FACTS})
    api.proposals.confirm(pid)
    api.close()
    async with _connected(project) as (ctx, client):
        found = await _call(client, "snowel_query",
                            {"action": "find", "params": {"name": "林晚"}})
        assert found["result"][0]["id"] == "n1"
        node = await _call(client, "snowel_query",
                           {"action": "node", "params": {"node_id": "n1"}})
        assert node["result"]["name"] == "林晚"
        st = await _call(client, "snowel_query",
                         {"action": "state_at", "params": {"story_order": 100}})
        assert isinstance(st["result"], dict)
        searched = await _call(client, "snowel_query",
                               {"action": "search", "params": {"q": "林晚"}})
        assert "result" in searched


async def test_generate_and_search_wired(project):
    async with _connected(project, backend=FakeBackend([
            json.dumps({"draft": "灵感", "facts": [], "appeared": []})
    ])) as (ctx, client):
        g = await _call(client, "snowel_generate",
                        {"artifact_type": "premise"})
        assert "proposal_id" in g                     # 不再 not_wired
        s = await _call(client, "snowel_query",
                        {"action": "search", "params": {"q": "林晚"}})
        assert "result" in s


async def test_writeback_actions_wired(project, tmp_path):
    api = SnowelAPI.open(project)
    from snowel_core.writeback import mirror
    mirror.write_prose(api._conn, tmp_path, "ch1", "正文")
    api.close()
    async with _connected(project, backend=FakeBackend([
            json.dumps({"facts": [], "appeared": []})])) as (ctx, client):
        w = await _call(client, "snowel_writeback", {"action": "reconcile"})
        assert w == {"result": []}
        la = await _call(client, "snowel_writeback", {"action": "list_auto"})
        assert "result" in la


async def test_advanced_audit_wired(project):
    async with _connected(project) as (ctx, client):
        a = await _call(client, "snowel_advanced", {"op": "audit"})
        assert a["result"] == []                       # 空 audit 表
        cat = await _call(client, "snowel_advanced", {})
        assert cat["operations"]["audit"]["wired"] is True


async def test_writeback_trigger_result_reject_wired(project):
    api = SnowelAPI.open(project)
    from snowel_core.writeback import mirror
    mirror.write_prose(api._conn, project, "ch1", "林晚获得一枚银色钥匙。")
    api.close()
    async with _connected(project, backend=FakeBackend([
            json.dumps({"facts": [{"sensitivity": "low",
                                   "fact": {"fact": "node", "id": "key1",
                                            "types": ["Concept"],
                                            "name": "银钥匙", "props": {}}}],
                        "appeared": []}),
    ])) as (ctx, client):
        t = await _call(client, "snowel_writeback", {
            "action": "trigger", "params": {"chapter_id": "ch1"}})
        assert t["result"]["chapter_id"] == "ch1"
        assert t["result"]["deviation"]["microbeat"] is None
        la = await _call(client, "snowel_writeback", {"action": "list_auto"})
        assert la["result"][0]["fact_id"] == "key1"
        res = await _call(client, "snowel_writeback", {
            "action": "result", "params": {"chapter_id": "ch1"}})
        assert res["result"]["deviation"]["microbeat"] is None
        rj = await _call(client, "snowel_writeback", {
            "action": "reject_auto",
            "params": {"entries": [{"target": "node", "target_id": "key1"}],
                       "reason": "误抽"}})
        assert rj["result"]["retracted"] == 1


async def test_writeback_reregister_recovers_crash_window(project):
    api = SnowelAPI.open(project)
    pid = api.proposals.create("prose", {
        "chapter_id": "ch1", "content": "第一章：雨夜。"})
    api.confirm(pid)
    api.close()
    (project / "chapters" / "ch1.md").unlink()  # L6 崩溃窗口：文件失登
    async with _connected(project) as (ctx, client):
        rr = await _call(client, "snowel_writeback", {
            "action": "re-register", "params": {"proposal_id": pid}})
        assert rr == {"re_registered": "ch1"}
    assert (project / "chapters" / "ch1.md").read_text(
        encoding="utf-8") == "第一章：雨夜。"


async def test_proposal_rewrite_wired(project):
    api = SnowelAPI.open(project)
    pid = api.proposals.create("premise", {
        "draft": "旧稿", "facts": [], "appeared": []})
    api.close()
    async with _connected(project, backend=FakeBackend([
            json.dumps({"draft": "新稿", "facts": [], "appeared": []})
    ])) as (ctx, client):
        r = await _call(client, "snowel_proposal", {
            "action": "rewrite", "proposal_id": pid,
            "reason": "更热血一点"})
        assert r["rewritten_from"] == pid
    api = SnowelAPI.open(project)
    try:
        new = api.proposals.get(r["proposal_id"])
        assert json.loads(new["payload"])["draft"] == "新稿"
        assert api.proposals.get(pid)["status"] == "pending"  # 原提案留队
    finally:
        api.close()


async def test_status_readonly_reports_actual_holder(project):
    blocker = open_project(project, heartbeat=False)
    try:
        async with _connected(project) as (ctx, client):
            d = await _call(client, "snowel_status", {})
            assert d["readonly"] is True
            assert d["lease_holder"] == blocker.holder
    finally:
        blocker.close()


async def test_advanced_catalog_and_rebuild(project):  # TC-SH-02
    api = SnowelAPI.open(project)
    pid = api.proposals.create("scene", {"facts": FACTS})
    api.proposals.confirm(pid)
    api.close()
    async with _connected(project) as (ctx, client):
        cat = await _call(client, "snowel_advanced", {})
        ops = cat["operations"]
        assert set(ops) >= {"rebuild", "setting_gap", "foreshadow_register",
                            "seal", "retcon", "extension_packs", "audit"}
        assert ops["rebuild"]["wired"] is True
        assert all(not v["wired"] for k, v in ops.items()
                   if k not in ("rebuild", "audit"))
        done = await _call(client, "snowel_advanced", {"op": "rebuild"})
        assert done == {"rebuilt": True}
        miss = await _call(client, "snowel_advanced", {"op": "seal"})
        _assert_not_wired(miss, "seal")


async def test_write_rejected_when_readonly(project):  # TC-SH-04 壳层
    api = SnowelAPI.open(project)
    pid = api.proposals.create("scene", {"facts": FACTS})
    api.close()
    blocker = open_project(project, heartbeat=False)
    try:
        async with _connected(project) as (ctx, client):
            assert ctx.readonly is True
            res = await client.call_tool(
                "snowel_proposal",
                {"action": "confirm", "proposal_id": pid})
            assert res.isError  # require_write 拒绝 → MCP 错误响应
    finally:
        blocker.close()


async def test_confirm_prose_via_mcp_writes_chapter_file(project):
    # 修复轮 F1：confirm 必须经 api.confirm 编排——prose 提案确认即代写文件（C1）
    async with _connected(project, backend=FakeBackend([
            json.dumps({"draft": "雨夜正文", "facts": [], "appeared": []})
    ])) as (ctx, client):
        g = await _call(client, "snowel_generate", {
            "artifact_type": "prose", "locate": {"chapter": "ch1"}})
        done = await _call(client, "snowel_proposal", {
            "action": "confirm", "proposal_id": g["proposal_id"]})
        assert done["event_seq"] >= 1
    assert (project / "chapters" / "ch1.md").read_text(
        encoding="utf-8") == "雨夜正文"


async def test_reconcile_rejected_when_readonly(project):
    # 修复轮 F2：reconcile 会写库（事件+镜像），readonly 上下文必须拒绝（L5 同类窗口）
    api = SnowelAPI.open(project)
    from snowel_core.writeback import mirror
    mirror.write_prose(api._conn, project, "ch1", "旧稿")
    api.close()
    (project / "chapters" / "ch1.md").write_text("外部新稿", encoding="utf-8")
    blocker = open_project(project, heartbeat=False)
    try:
        async with _connected(project) as (ctx, client):
            assert ctx.readonly is True
            res = await client.call_tool("snowel_writeback",
                                         {"action": "reconcile"})
            assert res.isError  # require_write 拒绝 → MCP 错误响应
    finally:
        blocker.close()
