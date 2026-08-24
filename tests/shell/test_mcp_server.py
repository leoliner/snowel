# tests/shell/test_mcp_server.py
import json
from contextlib import asynccontextmanager

import pytest
from mcp.shared.memory import create_connected_server_and_client_session

from snowel.mcp_server import build_mcp
from snowel.project import open_project
from snowel_core.api import SnowelAPI

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
async def _connected(project, **kw):
    ctx = open_project(project, **kw)
    try:
        mcp = build_mcp(ctx)
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
        _assert_not_wired(d["flow"], "flow")


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
        _assert_not_wired(searched, "query.search")


async def test_generate_writeback_not_wired(project):
    async with _connected(project) as (ctx, client):
        g = await _call(client, "snowel_generate",
                        {"artifact_type": "premise"})
        _assert_not_wired(g, "generate")
        w = await _call(client, "snowel_writeback", {"action": "run"})
        _assert_not_wired(w, "writeback")
        r = await _call(client, "snowel_proposal",
                        {"action": "rewrite", "proposal_id": "x"})
        _assert_not_wired(r, "proposal.rewrite")


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
        assert all(not v["wired"] for k, v in ops.items() if k != "rebuild")
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
