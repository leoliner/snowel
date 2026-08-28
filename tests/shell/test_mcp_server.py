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
        for k in ("seal", "retcon", "foreshadow_register"):
            assert ops[k]["wired"] is True
            assert ops[k]["via"] == "snowel_writeback"
        assert all(not v["wired"] for k, v in ops.items()
                   if k not in ("rebuild", "audit",
                                "seal", "retcon", "foreshadow_register",
                                "inspiration_save", "inspiration_list",
                                "beat_merge", "beat_delete"))
        done = await _call(client, "snowel_advanced", {"op": "rebuild"})
        assert done == {"rebuilt": True}
        guide = await _call(client, "snowel_advanced", {"op": "seal"})
        assert guide == {"wired": True, "via": "snowel_writeback",
                         "hint": "经 snowel_writeback 对应 action 调用"}
        miss = await _call(client, "snowel_advanced", {"op": "setting_gap"})
        _assert_not_wired(miss, "setting_gap")


async def test_advanced_new_ops_catalog(project):  # TC-SH-11 锚
    async with _connected(project) as (ctx, client):
        ops = (await _call(client, "snowel_advanced", {}))["operations"]
        for k in ("inspiration_save", "inspiration_list",
                  "beat_merge", "beat_delete"):
            assert ops[k]["wired"] is True
        assert "text" in ops["inspiration_save"]["params"]
        assert {"source", "target"} <= set(ops["beat_merge"]["params"])
        assert "beat_id" in ops["beat_delete"]["params"]
        # 裁决 6：扩展包不做 Web/MCP 面，仅 CLI 管理
        assert ops["extension_packs"]["wired"] is False
        assert "仅 CLI" in ops["extension_packs"]["planned_in"]
        assert "snowel ext" in ops["extension_packs"]["planned_in"]


async def test_advanced_inspiration_save_and_list(project):
    async with _connected(project) as (ctx, client):
        s = await _call(client, "snowel_advanced", {
            "op": "inspiration_save", "params": {"text": "雨夜钥匙的灵感"}})
        assert s["wired"] is True
        assert s["inspiration_id"]
        listed = await _call(client, "snowel_advanced",
                             {"op": "inspiration_list"})
        assert listed["wired"] is True
        assert [r["id"] for r in listed["result"]] == [s["inspiration_id"]]
        assert listed["result"][0]["text"] == "雨夜钥匙的灵感"
        empty = await client.call_tool("snowel_advanced", {
            "op": "inspiration_save", "params": {"text": "   "}})
        assert empty.isError  # 空文本拒绝 → MCP 错误响应（400 语义）
        assert "灵感文本不能为空" in empty.content[0].text


async def test_advanced_beat_merge_delete_ops(project):
    api = SnowelAPI.open(project)
    pid = api.proposals.create("t", {"facts": [
        {"fact": "node", "id": "mb1", "types": ["MicroBeat"], "name": "开场拍",
         "props": {"address": {"volume": 1, "chapter": 1, "scene": 1,
                               "beat": 1}}},
        {"fact": "node", "id": "mb2", "types": ["MicroBeat"], "name": "承接拍",
         "props": {"address": {"volume": 1, "chapter": 1, "scene": 1,
                               "beat": 2}}}]})
    api.confirm(pid)
    api.close()
    async with _connected(project) as (ctx, client):
        f = await _call(client, "snowel_writeback", {
            "action": "foreshadow",
            "params": {"name": "怀表", "planted_at": "mb1"}})
        await _call(client, "snowel_proposal", {
            "action": "confirm", "proposal_id": f["proposal_id"]})
        ref = await client.call_tool("snowel_advanced", {
            "op": "beat_delete", "params": {"beat_id": "mb1"}})
        assert ref.isError  # 被 planted_at 引用 → 拒绝
        assert "伏笔引用" in ref.content[0].text
        m = await _call(client, "snowel_advanced", {
            "op": "beat_merge", "params": {"source": "mb1", "target": "mb2"}})
        assert m["wired"] is True
        assert m["event_seq"] >= 1
        gone = await _call(client, "snowel_advanced", {
            "op": "beat_delete", "params": {"beat_id": "mb1",
                                            "reason": "并入承接拍"}})
        assert gone["wired"] is True  # 合并迁移引用后源拍可删
        assert gone["event_seq"] >= 1


async def test_advanced_write_ops_require_lease(project):
    blocker = open_project(project, heartbeat=False)
    try:
        async with _connected(project) as (ctx, client):
            assert ctx.readonly is True
            for args in ({"op": "inspiration_save",
                          "params": {"text": "灵感"}},
                         {"op": "beat_merge",
                          "params": {"source": "a", "target": "b"}},
                         {"op": "beat_delete", "params": {"beat_id": "a"}}):
                res = await client.call_tool("snowel_advanced", args)
                assert res.isError  # require_write 拒绝 → MCP 错误响应
                assert "写操作被拒绝" in res.content[0].text
            lst = await _call(client, "snowel_advanced",
                              {"op": "inspiration_list"})
            assert lst["wired"] is True  # 只读 op 不受租约约束
    finally:
        blocker.close()


async def test_writeback_seal_and_retcon_wired(project, tmp_path):
    api = SnowelAPI.open(project)
    pid = api.proposals.create("t", {"facts": [
        {"fact": "node", "id": "v1", "types": ["Volume"], "name": "卷一",
         "props": {"address": {"volume": 1, "chapter": 0, "scene": 0,
                               "beat": 0}}}]})
    api.confirm(pid)
    api.close()
    async with _connected(project) as (ctx, client):
        w = await _call(client, "snowel_writeback",
                        {"action": "seal", "params": {"volume_id": "v1"}})
        assert w["sealed"] == "v1"
        r = await _call(client, "snowel_writeback", {
            "action": "retcon",
            "params": {"facts": [{"fact": "node", "id": "v1",
                                  "types": ["Volume"], "name": "卷一",
                                  "props": {}}], "reason": "测试"}})
        assert "proposal_id" in r and "impact" in r
        cat = await _call(client, "snowel_advanced", {})
        assert cat["operations"]["seal"]["wired"] is True


async def test_writeback_foreshadow_registers_proposal(project):
    api = SnowelAPI.open(project)
    pid = api.proposals.create("t", {"facts": [
        {"fact": "node", "id": "mb1", "types": ["MicroBeat"],
         "name": "开场拍", "props": {"address": {"volume": 1, "chapter": 1,
                                                 "scene": 1, "beat": 1}}}]})
    api.confirm(pid)
    api.close()
    async with _connected(project) as (ctx, client):
        f = await _call(client, "snowel_writeback", {
            "action": "foreshadow",
            "params": {"name": "怀表", "planted_at": "mb1", "note": "第3章回收"}})
        assert "proposal_id" in f
        rows = await _call(client, "snowel_proposal", {"action": "list"})
        assert any(r["kind"] == "foreshadow" for r in rows["result"])


async def test_confirm_response_carries_cascade(project):
    api = SnowelAPI.open(project)
    p1 = api.proposals.create("t", {"facts": [
        {"fact": "node", "id": "m1", "types": ["Mechanism"], "name": "M",
         "props": {"mechanism": {"level": 3}}}]})
    api.confirm(p1)
    p2 = api.proposals.create("t", {"facts": [
        {"fact": "node", "id": "m1", "types": ["Mechanism"], "name": "M",
         "props": {"mechanism": {"level": 5}}}]})
    api.close()
    async with _connected(project) as (ctx, client):
        done = await _call(client, "snowel_proposal",
                           {"action": "confirm", "proposal_id": p2})
        assert done["cascade"]["tier"] == "full"
        assert any(v["rule"] == "contradiction"
                   for v in done["cascade"]["violations"])


async def test_proposal_confirm_dispatches_retcon(project):  # retcon 专属确认分派协议锚
    async with _connected(project) as (ctx, client):
        r = await _call(client, "snowel_writeback", {
            "action": "retcon",
            "params": {"facts": [{"fact": "node", "id": "m1",
                                  "types": ["Mechanism"], "name": "积分兑换",
                                  "props": {}}], "reason": "测试"}})
        done = await _call(client, "snowel_proposal", {
            "action": "confirm", "proposal_id": r["proposal_id"]})
        # 错路由到 api.confirm 时 core 抛错 → 本调用即红；断言确认面数据
        assert done["event_seq"] >= 1
        assert done["cascade"]["tier"] == "full"
        assert "violations" in done["cascade"]


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
