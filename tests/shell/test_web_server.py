# tests/shell/test_web_server.py
"""Web 壳（W2/W5）：app 工厂项目绑定、租约会话、写守卫 409、静态 SPA serve、
Task 6 写 API 面（确认/否决/改写/生成/封卷/retcon/伏笔/回写/修订）。"""
import json

import pytest
from httpx import ASGITransport, AsyncClient

from snowel_core.api import SnowelAPI
from snowel_core.storage import db, events, projector
from snowel_core.writeback import mirror
from snowel.web_server import create_app
from tests.conftest import FakeBackend

pytestmark = pytest.mark.anyio


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
def project(tmp_path):
    api = SnowelAPI.init_project(tmp_path)
    api.close()
    return tmp_path


async def test_session_and_binding(project):
    app = create_app(str(project))
    async with AsyncClient(transport=ASGITransport(app=app),
                           base_url="http://t") as c:
        r = await c.get("/api/session")
        assert r.status_code == 200
        body = r.json()
        assert body["readonly"] is False and "flow" in body
        assert (await c.get("/api/health")).json() == {"ok": True}


async def test_readonly_session_blocks_writes(project, monkeypatch):
    api = SnowelAPI.open(project)          # 抢占租约：模拟他端持锁（TC-SH-04）
    api.acquire_lease("mcp:test-holder")
    app = create_app(str(project))
    async with AsyncClient(transport=ASGITransport(app=app),
                           base_url="http://t") as c:
        sess = (await c.get("/api/session")).json()
        assert sess["readonly"] is True and sess["holder"] == "mcp:test-holder"
        r = await c.post("/api/proposals/xxx/confirm")
        assert r.status_code == 409 and "只读" in r.json()["detail"]
        # Task 6：写面全部挂同一守卫（readonly → 409，不触碰领域）
        assert (await c.post("/api/generate", json={
            "artifact_type": "premise"})).status_code == 409
        assert (await c.post("/api/seal", json={
            "volume_id": "v1"})).status_code == 409
        assert (await c.post("/api/writeback/extract", json={
            "chapter_id": "ch1"})).status_code == 409
    api.release_lease("mcp:test-holder")
    api.close()


async def test_static_serve_with_spa_fallback(project, tmp_path):
    # web/dist 缺失时跳过挂载（无 node 环境测试不破）；存在时挂 / + SPA 回落
    dist = tmp_path / "dist"
    dist.mkdir()
    (dist / "index.html").write_text("<html>snowel</html>", encoding="utf-8")
    (dist / "app.js").write_text("console.log(1)", encoding="utf-8")
    app = create_app(str(project), static_dir=dist)
    async with AsyncClient(transport=ASGITransport(app=app),
                           base_url="http://t") as c:
        assert (await c.get("/")).text == "<html>snowel</html>"
        assert (await c.get("/novel/abc")).text == "<html>snowel</html>"  # SPA 回落
        assert (await c.get("/app.js")).status_code == 200
        assert (await c.get("/api/health")).json() == {"ok": True}  # API 优先于静态


async def test_proposal_read_surface(project):
    api = SnowelAPI.open(project)
    pid = api.proposals.create("t", {"facts": [
        {"fact": "node", "id": "n1", "types": ["Concept"], "name": "x",
         "props": {}}]})
    api.close()
    app = create_app(str(project))
    async with AsyncClient(transport=ASGITransport(app=app),
                           base_url="http://t") as c:
        lst = (await c.get("/api/proposals", params={"status": "pending"}))
        assert lst.status_code == 200 and any(
            p["id"] == pid for p in lst.json())
        one = (await c.get(f"/api/proposals/{pid}")).json()
        assert one["kind"] == "t" and one["payload"]["facts"][0]["id"] == "n1"
        assert (await c.get("/api/proposals/nope")).status_code == 404
        prev = (await c.get(f"/api/proposals/{pid}/cascade_preview")).json()
        assert "violations" in prev            # 预演返回，队列长度不变


async def test_read_surface_missing_pid_and_404s(project):
    api = SnowelAPI.open(project)
    pid = api.proposals.create("t", {"facts": []})
    api.close()
    app = create_app(str(project))
    async with AsyncClient(transport=ASGITransport(app=app),
                           base_url="http://t") as c:
        # 不存在 pid：单查与级联预演统一 404
        assert (await c.get(f"/api/proposals/{pid}/cascade_preview")
                ).status_code == 200      # 空 facts 预演照常 200
        assert (await c.get("/api/proposals/nope/cascade_preview")
                ).status_code == 404
        # 检索/审计等无 pid 端点照常 200（不误伤）
        assert (await c.get("/api/search", params={"q": "x"})).status_code == 200
        assert (await c.get("/api/audit")).status_code == 200
        assert (await c.get("/api/writeback/auto")).status_code == 200
        assert (await c.get("/api/writeback/deviation/ch1")).status_code == 200
        assert (await c.get("/api/reconcile")).status_code == 200
        assert (await c.get("/api/sealed")).status_code == 200


async def test_node_flow_search_reconcile_happy_paths(project):
    api = SnowelAPI.open(project)
    pid = api.proposals.create("t", {"facts": [
        {"fact": "node", "id": "n1", "types": ["Concept"], "name": "雪",
         "props": {}}]})
    api.confirm(pid)
    api.close()
    app = create_app(str(project))
    async with AsyncClient(transport=ASGITransport(app=app),
                           base_url="http://t") as c:
        node = (await c.get("/api/nodes/n1")).json()
        assert node["node"]["id"] == "n1" and node["node"]["name"] == "雪"
        assert (await c.get("/api/nodes/nope")).json()["node"] is None
        flow = (await c.get("/api/flow")).json()
        assert isinstance(flow, dict)
        assert (await c.get("/api/state", params={"at": 1})).status_code == 200
        s = (await c.get("/api/search", params={"q": "雪"})).json()
        assert "nodes" in s and "paragraphs" in s
        assert (await c.get("/api/sealed")).json() == []   # 未封卷
        assert (await c.get("/api/reconcile")).json() == []  # 无镜像差异


async def test_readonly_session_reads_freely(project):
    # TC-SH-04：只读会话 GET 全部照常（只读降级读不限，仅写端点 409）
    api = SnowelAPI.open(project)          # 抢占租约：模拟他端持锁
    api.acquire_lease("mcp:test-holder")
    app = create_app(str(project))
    async with AsyncClient(transport=ASGITransport(app=app),
                           base_url="http://t") as c:
        sess = (await c.get("/api/session")).json()
        assert sess["readonly"] is True
        assert (await c.get("/api/flow")).status_code == 200
        assert (await c.get("/api/proposals")).status_code == 200
        assert (await c.get("/api/audit")).status_code == 200
        # T11 fix 1：按章正文读取无写守卫（TC-SH-04 读面不限）
        assert (await c.get("/api/chapters/ch1/prose")).status_code == 200
    api.release_lease("mcp:test-holder")
    api.close()


async def test_readonly_reconcile_is_pure_state_read(project):
    # Ruling（T5 复评）：只读会话 GET /api/reconcile 是纯状态读（dry-run），
    # 不得绕过租约写共享库（F2）——写穿透关闭锚
    seed = SnowelAPI.open(project)
    mirror.write_prose(seed._conn, project, "ch1", "旧正文")
    (project / "chapters" / "ch1.md").write_text("新正文（外部编辑）",
                                                 encoding="utf-8")
    seed.close()
    api = SnowelAPI.open(project)          # 抢占租约：模拟他端持锁
    api.acquire_lease("mcp:test-holder")
    app = create_app(str(project))
    async with AsyncClient(transport=ASGITransport(app=app),
                           base_url="http://t") as c:
        sess = (await c.get("/api/session")).json()
        assert sess["readonly"] is True
        r = await c.get("/api/reconcile")
        assert r.status_code == 200
        assert r.json() == [{"chapter_id": "ch1",
                             "status": "external_change"}]
    api.release_lease("mcp:test-holder")
    api.close()
    # 写穿透关闭锚：库内无 prose_external_change 事件、镜像未被重灌
    check = SnowelAPI.open(project)
    n = check._conn.execute(
        "SELECT count(*) c FROM events WHERE kind='prose_external_change'"
    ).fetchone()["c"]
    assert n == 0
    prose = check._conn.execute(
        "SELECT prose FROM chapter_prose WHERE chapter_id='ch1'").fetchone()
    assert prose["prose"] == "旧正文"
    check.close()


def test_web_rejects_non_project(tmp_path):
    # TC-SH-06：非项目目录启动 → 明确报错 + 非零退出（不阻塞 uvicorn）
    from typer.testing import CliRunner

    from snowel.cli import app

    res = CliRunner().invoke(app, ["web", "--project", str(tmp_path)])
    assert res.exit_code == 1
    assert "snowel init" in res.output


# ---- Task 6：写 API 面（确认/否决/改写/生成/封卷/retcon/伏笔/回写/修订）----

def _seed_event(api, facts):
    """直接事件种子（与 core 测试同款）：proposal_confirmed + 物化。"""
    with db.transaction(api._conn):
        events.append_event(api._conn, "proposal_confirmed", {
            "artifact_type": "t", "facts": facts})
    projector.apply(api._conn)


def _llm_resp(draft="生成稿", facts=None):
    return json.dumps({"draft": draft, "facts": facts or [], "appeared": []},
                      ensure_ascii=False)


async def test_confirm_returns_seq_and_cascade(project):
    # 种子机制节点（level=3）+ 变更提案（level=5）→ 确认返回 seq + cascade 键
    # （E5 接线：major 矛盾产 diff 提案，cascade 非 None）
    api = SnowelAPI.open(project)
    _seed_event(api, [{"fact": "node", "id": "m1", "types": ["Mechanism"],
                       "name": "积分兑换",
                       "props": {"mechanism": {"level": 3}}}])
    pid = api.proposals.create("t", {"facts": [
        {"fact": "node", "id": "m1", "types": ["Mechanism"],
         "name": "积分兑换", "props": {"mechanism": {"level": 5}}}]})
    api.close()
    app = create_app(str(project))
    async with AsyncClient(transport=ASGITransport(app=app),
                           base_url="http://t") as c:
        r = await c.post(f"/api/proposals/{pid}/confirm")
        assert r.status_code == 200
        body = r.json()
        assert isinstance(body["seq"], int) and body["seq"] > 0
        assert body["cascade"]["tier"] == "full"
        assert any(v["rule"] == "contradiction"
                   for v in body["cascade"]["violations"])
        # 已确认提案再确认 → ProposalStateError → 409（带状态机消息）
        r2 = await c.post(f"/api/proposals/{pid}/confirm")
        assert r2.status_code == 409 and "非法迁移" in r2.json()["detail"]
        # 缺失 pid → 404
        assert (await c.post("/api/proposals/nope/confirm")).status_code == 404


async def test_reject_records_reason(project):
    # 否决接线锚（评审 finding）：200 {"ok": True} + 状态落库 + 事件携带 reason
    api = SnowelAPI.open(project)
    pid = api.proposals.create("t", {"facts": []})
    api.close()
    app = create_app(str(project))
    async with AsyncClient(transport=ASGITransport(app=app),
                           base_url="http://t") as c:
        r = await c.post(f"/api/proposals/{pid}/reject",
                         json={"reason": "测试否决"})
        assert r.status_code == 200 and r.json() == {"ok": True}
    other = SnowelAPI.open(project)          # TC-SH-03 式独立句柄（共库）
    try:
        assert other.proposals.get(pid)["status"] == "rejected"
        ev = other._conn.execute(
            "SELECT payload FROM events WHERE kind='proposal_rejected'"
        ).fetchone()
        assert json.loads(ev["payload"]) == {
            "proposal_id": pid, "reason": "测试否决"}
    finally:
        other.close()


async def test_confirm_retcon_roundtrip(project):
    # 壳零分派（铁律 1）：retcon 提案走 confirm → core ValueError → 400；
    # confirm_retcon 端点返回 seq + cascade（propose 时同步进实例的影响清单，
    # 故 propose 与 confirm 须走同一 app 实例——与生产同进程语义一致）
    api = SnowelAPI.open(project)
    _seed_event(api, [{"fact": "node", "id": "m1", "types": ["Mechanism"],
                       "name": "积分兑换",
                       "props": {"mechanism": {"level": 3}}}])
    api.close()
    app = create_app(str(project))
    async with AsyncClient(transport=ASGITransport(app=app),
                           base_url="http://t") as c:
        r0 = await c.post("/api/retcon", json={
            "facts": [{"fact": "node", "id": "m1", "types": ["Mechanism"],
                       "name": "积分兑换",
                       "props": {"mechanism": {"level": 9}}}],
            "reason": "等级体系重排"})
        assert r0.status_code == 200
        rpid = r0.json()["proposal_id"]
        r = await c.post(f"/api/proposals/{rpid}/confirm")
        assert r.status_code == 400 and "confirm_retcon" in r.json()["detail"]
        r2 = await c.post(f"/api/proposals/{rpid}/confirm_retcon")
        assert r2.status_code == 200
        body = r2.json()
        assert isinstance(body["seq"], int) and body["seq"] > 0
        assert body["cascade"]["tier"] == "full"
        assert any(v["rule"] == "contradiction"
                   for v in body["cascade"]["violations"])


async def test_seal_and_reseal(project):
    api = SnowelAPI.open(project)
    _seed_event(api, [{"fact": "node", "id": "v1", "types": ["Volume"],
                       "name": "卷一",
                       "props": {"address": {"volume": 1, "chapter": 0,
                                             "scene": 0, "beat": 0}}}])
    api.close()
    app = create_app(str(project))
    async with AsyncClient(transport=ASGITransport(app=app),
                           base_url="http://t") as c:
        r = await c.post("/api/seal", json={"volume_id": "v1"})
        assert r.status_code == 200 and r.json() == {"sealed": "v1"}
        # 重复封卷 → ValueError → 400 带"已封"
        r2 = await c.post("/api/seal", json={"volume_id": "v1"})
        assert r2.status_code == 400 and "已封" in r2.json()["detail"]


async def test_rewrite_with_injected_backend(project):
    api = SnowelAPI.open(project)
    pid = api.proposals.create("premise", {"draft": "旧草稿", "facts": []})
    api.close()
    fake = FakeBackend([_llm_resp("改写稿")])
    app = create_app(str(project), llm_backend=fake)
    async with AsyncClient(transport=ASGITransport(app=app),
                           base_url="http://t") as c:
        r = await c.post(f"/api/proposals/{pid}/rewrite",
                         json={"instruction": "更黑暗"})
        assert r.status_code == 200
        new_pid = r.json()["proposal_id"]
        assert new_pid and new_pid != pid
        assert (await c.post(f"/api/proposals/{pid}/rewrite",
                             json={})).status_code == 400  # instruction 必填
    assert "更黑暗" in fake.calls[0]["prompt"]              # 指令进提示词
    check = SnowelAPI.open(project)
    p = json.loads(check.proposals.get(new_pid)["payload"])
    assert p["draft"] == "改写稿" and p["rewritten_from"] == pid
    check.close()


async def test_generate_with_injected_backend(project):
    fake = FakeBackend([_llm_resp("生成的设定")])
    app = create_app(str(project), llm_backend=fake)
    async with AsyncClient(transport=ASGITransport(app=app),
                           base_url="http://t") as c:
        r = await c.post("/api/generate", json={
            "artifact_type": "premise", "extra": {"notes": "无限流"}})
        assert r.status_code == 200
        pid = r.json()["proposal_id"]
        assert pid
        assert (await c.post("/api/generate", json={})).status_code == 400
    assert "无限流" in fake.calls[0]["prompt"]
    check = SnowelAPI.open(project)
    assert check.proposals.get(pid)["status"] == "pending"  # 产出必进提案队列
    check.close()


async def test_expand_chapter_with_injected_backend(project):
    api = SnowelAPI.open(project)
    _seed_event(api, [{"fact": "node", "id": "sc1", "types": ["Scene"],
                       "name": "雨夜", "props": {"chapter": "ch1",
                                                 "characters": [],
                                                 "required_elements": ["雨夜"]}}])
    api.close()
    fake = FakeBackend([_llm_resp("意图"), _llm_resp("微节拍组"), _llm_resp("正文")])
    app = create_app(str(project), llm_backend=fake)
    async with AsyncClient(transport=ASGITransport(app=app),
                           base_url="http://t") as c:
        r = await c.post("/api/expand/chapter", json={"chapter_id": "ch1"})
        assert r.status_code == 200
        assert len(r.json()["proposal_ids"]) == 3 and len(fake.calls) == 3


async def test_expand_volume_with_injected_backend(project):
    fake = FakeBackend([_llm_resp("主题"), _llm_resp("三幕")])
    app = create_app(str(project), llm_backend=fake)
    async with AsyncClient(transport=ASGITransport(app=app),
                           base_url="http://t") as c:
        r = await c.post("/api/expand/volume", json={"volume_id": "v1"})
        assert r.status_code == 200
        assert len(r.json()["proposal_ids"]) == 2 and len(fake.calls) == 2


async def test_retcon_endpoint_returns_impact(project):
    api = SnowelAPI.open(project)
    _seed_event(api, [{"fact": "node", "id": "m1", "types": ["Mechanism"],
                       "name": "积分兑换",
                       "props": {"mechanism": {"level": 3}}}])
    api.close()
    app = create_app(str(project))
    async with AsyncClient(transport=ASGITransport(app=app),
                           base_url="http://t") as c:
        r = await c.post("/api/retcon", json={
            "facts": [{"fact": "node", "id": "m1", "types": ["Mechanism"],
                       "name": "积分兑换",
                       "props": {"mechanism": {"level": 9}}}],
            "reason": "等级体系重排"})
        assert r.status_code == 200
        body = r.json()
        assert body["proposal_id"]
        assert "violations" in body["impact"]
        assert "affected_proposals" in body["impact"]


async def test_foreshadow_endpoint(project):
    api = SnowelAPI.open(project)
    _seed_event(api, [{"fact": "node", "id": "mb1", "types": ["MicroBeat"],
                       "name": "开场拍",
                       "props": {"address": {"volume": 1, "chapter": 1,
                                             "scene": 1, "beat": 1}}}])
    api.close()
    app = create_app(str(project))
    async with AsyncClient(transport=ASGITransport(app=app),
                           base_url="http://t") as c:
        r = await c.post("/api/foreshadow", json={
            "name": "怀表", "planted_at": "mb1", "note": "第3章回收"})
        assert r.status_code == 200 and r.json()["proposal_id"]
        # 非法 planted_at → core ValueError → 400
        r2 = await c.post("/api/foreshadow", json={
            "name": "怀表", "planted_at": "nope"})
        assert r2.status_code == 400 and "planted_at" in r2.json()["detail"]


async def test_writeback_extract_with_injected_backend(project):
    # 数字陷阱：low 敏感事实不得含 ASCII 数字（否则后校抬成 high 改走提案）
    api = SnowelAPI.open(project)
    mirror.write_prose(api._conn, project, "ch1", "林晚攒积分。")
    api.close()
    resp = json.dumps({"facts": [
        {"sensitivity": "low", "fact": {
            "fact": "node", "id": "m2", "types": ["Mechanism"],
            "name": "新机制", "props": {}}}], "appeared": []},
        ensure_ascii=False)
    app = create_app(str(project), llm_backend=FakeBackend([resp]))
    async with AsyncClient(transport=ASGITransport(app=app),
                           base_url="http://t") as c:
        r = await c.post("/api/writeback/extract", json={"chapter_id": "ch1"})
        assert r.status_code == 200
        body = r.json()                                    # 完整 extract 返回
        assert body["chapter_id"] == "ch1"
        assert body["proposal_id"] is None                 # 仅 low → auto 入典
        assert isinstance(body["auto_event_seq"], int)
        assert body["cascade"]["tier"] == "light"          # 含 cascade 键
        assert "deviation" in body


async def test_writeback_reject_auto(project):
    api = SnowelAPI.open(project)
    _seed_event(api, [{"fact": "node", "id": "m1", "types": ["Mechanism"],
                       "name": "积分兑换", "props": {}}])
    api.close()
    app = create_app(str(project))
    async with AsyncClient(transport=ASGITransport(app=app),
                           base_url="http://t") as c:
        r = await c.post("/api/writeback/reject_auto",
                         json={"entries": [["node", "m1"]]})
        assert r.status_code == 200
        assert r.json()["retracted"] == 1 and "cascade" in r.json()
    check = SnowelAPI.open(project)
    n = check._conn.execute(
        "SELECT count(*) c FROM events WHERE kind='retraction'").fetchone()["c"]
    assert n == 1
    check.close()


async def test_writeback_reregister(project):
    api = SnowelAPI.open(project)
    pid = api.proposals.create("prose", {
        "chapter_id": "ch1", "content": "正文内容", "facts": []})
    api.confirm(pid)                                       # 确认即代写
    api.close()
    (project / "chapters" / "ch1.md").unlink()             # 模拟文件丢失
    app = create_app(str(project))
    async with AsyncClient(transport=ASGITransport(app=app),
                           base_url="http://t") as c:
        r = await c.post("/api/writeback/reregister",
                         json={"proposal_id": pid})
        assert r.status_code == 200 and r.json() == {"chapter_id": "ch1"}
        assert (project / "chapters" / "ch1.md").exists()
        # 非 prose/未确认/缺失 → core ValueError → 400
        assert (await c.post("/api/writeback/reregister",
                             json={"proposal_id": "nope"})).status_code == 400


async def test_revision_endpoint(project):
    api = SnowelAPI.open(project)
    _seed_event(api, [{"fact": "node", "id": "c5", "types": ["Chapter"],
                       "name": "第5章",
                       "props": {"address": {"volume": 1, "chapter": 5,
                                             "scene": 0, "beat": 0}}}])
    api.close()
    app = create_app(str(project))
    async with AsyncClient(transport=ASGITransport(app=app),
                           base_url="http://t") as c:
        r = await c.post("/api/revision", json={
            "node_id": "c5", "reason": "章改卷",
            "new_address": {"volume": 1, "chapter": 9, "scene": 0, "beat": 0}})
        assert r.status_code == 200 and r.json()["proposal_id"]


async def test_web_confirm_visible_from_separate_handle(project):  # TC-SH-03
    # 三端视图一致：Web 确认后，独立 SnowelAPI 句柄（与 Web app 共库）读 confirmed
    api = SnowelAPI.open(project)
    pid = api.proposals.create("t", {"facts": [
        {"fact": "node", "id": "n1", "types": ["Concept"], "name": "雪",
         "props": {}}]})
    api.close()
    app = create_app(str(project))
    async with AsyncClient(transport=ASGITransport(app=app),
                           base_url="http://t") as c:
        assert (await c.post(f"/api/proposals/{pid}/confirm")).status_code == 200
    other = SnowelAPI.open(project)
    try:
        assert other.proposals.get(pid)["status"] == "confirmed"
    finally:
        other.close()


# ---- Task 7（W4）：统计四件端点（GET /api/stats/{stat}，一比一转发）----

def _seed_stats(project):
    """统计种子：双 POV 章/场/拍 + 三态伏笔 + 角色边 + 章正文（段镜像）。"""
    api = SnowelAPI.open(project)
    _seed_event(api, [
        {"fact": "node", "id": "v1", "types": ["Volume"], "name": "卷一",
         "props": {"address": {"volume": 1}}},
        {"fact": "node", "id": "ch1", "types": ["Chapter"], "name": "第一章",
         "props": {"address": {"volume": 1, "chapter": 1},
                   "pov": {"name": "江晚"}}},
        {"fact": "node", "id": "ch2", "types": ["Chapter"], "name": "第二章",
         "props": {"address": {"volume": 1, "chapter": 2},
                   "pov": {"name": "沈眠"}}},
        {"fact": "node", "id": "s1", "types": ["Scene"], "name": "场景一",
         "props": {"address": {"volume": 1, "chapter": 1, "scene": 1},
                   "pov": {"name": "沈眠"}}},
        {"fact": "node", "id": "mb1", "types": ["MicroBeat"], "name": "拍一",
         "props": {"address": {"volume": 1, "chapter": 1, "scene": 1, "beat": 1},
                   "pov": {"name": "江晚"}}},
        {"fact": "node", "id": "mb2", "types": ["MicroBeat"], "name": "拍二",
         "props": {"address": {"volume": 1, "chapter": 1, "scene": 1, "beat": 2}}},
        {"fact": "node", "id": "f1", "types": ["Foreshadow"], "name": "怀表",
         "props": {"foreshadow": {"planted_at": "mb1", "origin": "author",
                                  "payoff_beat": None, "note": ""}}},
        {"fact": "node", "id": "f2", "types": ["Foreshadow"], "name": "铜币",
         "props": {"foreshadow": {"planted_at": "mb1", "origin": "author",
                                  "payoff_beat": "mb2", "note": ""}}},
        {"fact": "node", "id": "f3", "types": ["Foreshadow"], "name": "钥匙",
         "props": {"foreshadow": {"planted_at": "mb1", "origin": "author",
                                  "payoff_beat": "mb9", "note": ""}}},
        {"fact": "node", "id": "a", "types": ["Character"], "name": "江晚",
         "props": {}},
        {"fact": "node", "id": "b", "types": ["Character"], "name": "沈眠",
         "props": {}},
        {"fact": "edge", "id": "e1", "src": "a", "dst": "b", "kind": "KNOWS",
         "props": {}},
    ])
    mirror.write_prose(api._conn, project, "ch1", "段一\n\n段二")
    api.close()


async def test_stats_pov_endpoint(project):
    _seed_stats(project)
    app = create_app(str(project))
    async with AsyncClient(transport=ASGITransport(app=app),
                           base_url="http://t") as c:
        body = (await c.get("/api/stats/pov")).json()
    by_volume = {v["volume_id"]: v for v in body["by_volume"]}
    assert by_volume["v1"]["volume_name"] == "卷一"
    assert by_volume["v1"]["counts"] == {"江晚": 2, "沈眠": 2}


async def test_stats_foreshadow_endpoint(project):
    _seed_stats(project)
    app = create_app(str(project))
    async with AsyncClient(transport=ASGITransport(app=app),
                           base_url="http://t") as c:
        body = (await c.get("/api/stats/foreshadow")).json()
    items = {it["id"]: it for it in body["items"]}
    assert items["f1"]["status"] == "planted"
    assert items["f2"]["status"] == "paid"
    assert items["f3"]["status"] == "stale"
    assert items["f2"]["payoff_beat"] == "mb2"


async def test_stats_relations_endpoint(project):
    _seed_stats(project)
    app = create_app(str(project))
    async with AsyncClient(transport=ASGITransport(app=app),
                           base_url="http://t") as c:
        body = (await c.get("/api/stats/relations")).json()
    assert {n["id"] for n in body["nodes"]} == {"a", "b"}
    assert [e["id"] for e in body["edges"]] == ["e1"]
    assert body["edges"][0]["kind"] == "KNOWS"


async def test_stats_pacing_endpoint(project):
    _seed_stats(project)
    app = create_app(str(project))
    async with AsyncClient(transport=ASGITransport(app=app),
                           base_url="http://t") as c:
        body = (await c.get("/api/stats/pacing")).json()
    by_id = {c["chapter_id"]: c for c in body["chapters"]}
    assert by_id["ch1"]["beats"] == 2 and by_id["ch1"]["paragraphs"] == 2
    assert by_id["ch2"]["beats"] == 0 and by_id["ch2"]["paragraphs"] == 0


async def test_stats_invalid_name_404(project):
    app = create_app(str(project))
    async with AsyncClient(transport=ASGITransport(app=app),
                           base_url="http://t") as c:
        assert (await c.get("/api/stats/nope")).status_code == 404


# ---- Task 8（W6）：聊天端点（SSE 流式 + 非流式聚合）----

def _chat_queue():
    """两轮队列（T3 Ruling：generate 内部再调 backend，故工具 JSON 后补生成稿）：
    工具调用 → 生成稿 → 回复 JSON。"""
    return [
        json.dumps({"tool": "generate",
                    "args": {"artifact_type": "premise",
                             "extra": {"notes": "无限流"}}}, ensure_ascii=False),
        _llm_resp("生成的设定"),
        json.dumps({"reply": "已生成前提提案，请到面板确认。"}, ensure_ascii=False),
    ]


def _sse_events(body: str) -> list[dict]:
    """SSE 响应体 → 事件序列（剥 "data: " 前缀，按空行分隔）。"""
    return [json.loads(line[len("data: "):])
            for line in body.split("\n\n") if line.startswith("data: ")]


async def test_chat_stream_sse_events(project):
    # 两轮（tool + reply）→ 恰 4 条 data 行：tool_call/tool_result/reply/done，
    # done 携带非空 proposal_ids（工具已产出）；history 进提示词
    fake = FakeBackend(_chat_queue())
    app = create_app(str(project), llm_backend=fake)
    async with AsyncClient(transport=ASGITransport(app=app),
                           base_url="http://t") as c:
        async with c.stream("POST", "/api/chat/stream", json={
                "message": "帮我想个无限流前提",
                "history": [{"role": "user", "text": "上一轮对话"},
                            {"role": "assistant", "text": "收到"}]}) as r:
            assert r.status_code == 200
            assert r.headers["content-type"].startswith("text/event-stream")
            body = (await r.aread()).decode()
    events = _sse_events(body)
    assert [e["type"] for e in events] == [
        "tool_call", "tool_result", "reply", "done"]
    assert events[0]["tool"] == "generate"
    assert events[1]["ok"] is True and "提案" in events[1]["summary"]
    assert events[3]["proposal_ids"]                   # 非空
    assert "无限流" in fake.calls[0]["prompt"]          # 消息与 history 进提示词
    assert "上一轮对话" in fake.calls[0]["prompt"]


async def test_chat_aggregate_endpoint(project):
    # 非流式聚合：events 除 done 外全部 + proposal_ids（与流式同源）
    fake = FakeBackend(_chat_queue())
    app = create_app(str(project), llm_backend=fake)
    async with AsyncClient(transport=ASGITransport(app=app),
                           base_url="http://t") as c:
        r = await c.post("/api/chat", json={"message": "帮我想个无限流前提"})
        assert r.status_code == 200
        body = r.json()
    assert [e["type"] for e in body["events"]] == [
        "tool_call", "tool_result", "reply"]
    assert body["proposal_ids"]                        # 非空
    assert all(e["type"] != "done" for e in body["events"])


async def test_chat_empty_message_400(project):
    # 空 message → 400（进流前校验；非流式同）
    app = create_app(str(project))
    async with AsyncClient(transport=ASGITransport(app=app),
                           base_url="http://t") as c:
        assert (await c.post("/api/chat", json={"message": ""})).status_code == 400
        async with c.stream("POST", "/api/chat/stream",
                            json={"message": ""}) as r:
            assert r.status_code == 400


async def test_chat_malformed_history_400(project):
    # history 条目须为 {role: user|assistant, text: str}；畸形 → 400（两端点同）
    app = create_app(str(project))
    async with AsyncClient(transport=ASGITransport(app=app),
                           base_url="http://t") as c:
        bad = ["not-a-dict",
               [{"role": "user"}],
               [{"role": "system", "text": "x"}],
               [{"role": "user", "text": 42}]]
        for h in bad:
            r = await c.post("/api/chat", json={"message": "hi", "history": h})
            assert r.status_code == 400, h
            async with c.stream("POST", "/api/chat/stream",
                                json={"message": "hi", "history": h}) as rs:
                assert rs.status_code == 400, h


async def test_chat_readonly_session_409(project):
    # 写守卫同 T6：聊天代理工具可产提案（写路径），只读会话统一 409（C10）
    api = SnowelAPI.open(project)          # 抢占租约：模拟他端持锁
    api.acquire_lease("mcp:test-holder")
    app = create_app(str(project))
    async with AsyncClient(transport=ASGITransport(app=app),
                           base_url="http://t") as c:
        r = await c.post("/api/chat", json={"message": "hi"})
        assert r.status_code == 409 and "只读" in r.json()["detail"]
        async with c.stream("POST", "/api/chat/stream",
                            json={"message": "hi"}) as rs:
            assert rs.status_code == 409
    api.release_lease("mcp:test-holder")
    api.close()


async def test_chat_stream_error_event_closes_stream(project):
    # 队列中途耗尽（IndexError 逃逸 run_stream）→ 流内 error 事件后收束，
    # 不吊死连接（error 为最后一条 data 行）
    fake = FakeBackend([json.dumps(
        {"tool": "generate", "args": {"artifact_type": "premise"}},
        ensure_ascii=False)])
    app = create_app(str(project), llm_backend=fake)
    async with AsyncClient(transport=ASGITransport(app=app),
                           base_url="http://t") as c:
        async with c.stream("POST", "/api/chat/stream",
                            json={"message": "hi"}) as r:
            body = (await r.aread()).decode()
    events = _sse_events(body)
    assert events[-1]["type"] == "error"
    assert "pop from empty list" in events[-1]["text"]


# ---- Task 11（T11）：正文保存端点（POST /api/prose，一比一 prose 提案创建）----

async def test_prose_endpoint(project):
    """正文保存锚：proposals.create("prose", {chapter_id, content}) → pending
    提案（payload 一比一）；缺字段 → 400（_require 统一口径）。"""
    app = create_app(str(project))
    async with AsyncClient(transport=ASGITransport(app=app),
                           base_url="http://t") as c:
        r = await c.post("/api/prose", json={
            "chapter_id": "ch1", "content": "段一\n\n段二"})
        assert r.status_code == 200
        pid = r.json()["proposal_id"]
        assert pid
        # 缺字段 → 400（body 空 / 缺 content 同口径）
        assert (await c.post("/api/prose", json={})).status_code == 400
        assert (await c.post("/api/prose", json={
            "chapter_id": "ch1"})).status_code == 400
    check = SnowelAPI.open(project)          # 独立句柄读回（TC-SH-03 式共库）
    try:
        row = check.proposals.get(pid)
        assert row["kind"] == "prose" and row["status"] == "pending"
        assert json.loads(row["payload"]) == {
            "chapter_id": "ch1", "content": "段一\n\n段二"}
    finally:
        check.close()


async def test_prose_endpoint_readonly_409(project):
    # 正文保存是写路径：只读会话 /api/prose → 409（守卫同 T6 写面）
    api = SnowelAPI.open(project)
    api.acquire_lease("mcp:test-holder")
    app = create_app(str(project))
    async with AsyncClient(transport=ASGITransport(app=app),
                           base_url="http://t") as c:
        r = await c.post("/api/prose", json={
            "chapter_id": "ch1", "content": "正文"})
        assert r.status_code == 409 and "只读" in r.json()["detail"]
    api.release_lease("mcp:test-holder")
    api.close()


async def test_chapter_prose_endpoint(project):
    """按章正文加载面（T11 fix 1）：有镜像行 → 全文；无行 → prose null（200，
    前端空白可输入）。"""
    seed = SnowelAPI.open(project)
    mirror.write_prose(seed._conn, project, "ch1", "段一\n\n段二")
    seed.close()
    app = create_app(str(project))
    async with AsyncClient(transport=ASGITransport(app=app),
                           base_url="http://t") as c:
        r = await c.get("/api/chapters/ch1/prose")
        assert r.status_code == 200
        assert r.json() == {"chapter_id": "ch1", "prose": "段一\n\n段二"}
        r2 = await c.get("/api/chapters/nope/prose")
        assert r2.status_code == 200
        assert r2.json() == {"chapter_id": "nope", "prose": None}


# ---- Task 14：TC-SH-08 API 级端到端（流程树/工作区/编辑页/聊天约束四断言面）----

async def test_tc_sh_08_api_e2e(project):
    """TC-SH-08 端到端：init → 种子一层（premise 确认 + 卷/章物化）→
    /api/flow（层进度+卷章树）→ /api/proposals（工作区数据源）→
    /api/reconcile（编辑页识别镜像状态）→ /api/chat（FakeBackend 一轮产提案，
    响应无已确认动作——确认只落结构化面板）→ confirm（结构化确认）→ confirmed。"""
    # 1. init + 种子一层：premise 走真实确认路径（事件+投影器+提案行，层进度
    #    done）；卷/章树随 structure 事件物化（tests/flow/test_state 同款）
    api = SnowelAPI.open(project)
    spid = api.proposals.create("premise", {"draft": "无限流前提"})
    api.confirm(spid)
    with db.transaction(api._conn):
        events.append_event(api._conn, "proposal_confirmed", {
            "artifact_type": "structure", "facts": [
                {"fact": "node", "id": "v1", "types": ["Volume"],
                 "name": "卷一", "props": {}},
                {"fact": "node", "id": "ch1", "types": ["Chapter"],
                 "name": "第一章", "props": {"volume": "v1"}}]})
        projector.apply(api._conn)
    mirror.write_prose(api._conn, project, "ch1", "段一")   # 中栏可编辑正文
    api.close()
    (project / "chapters" / "ch1.md").write_text("段一（外部改动）",
                                                 encoding="utf-8")

    fake = FakeBackend(_chat_queue())
    app = create_app(str(project), llm_backend=fake)
    async with AsyncClient(transport=ASGITransport(app=app),
                           base_url="http://t") as c:
        # 2. 流程树面：premise 层 done + 卷章树就位
        flow = (await c.get("/api/flow")).json()
        assert flow["layers"]["premise"] == "done"
        assert flow["current_layer"] == "synopsis"
        assert flow["volumes"] == [{"id": "v1", "name": "卷一",
                                    "chapters": [{"id": "ch1",
                                                  "name": "第一章"}]}]
        # 3. 工作区面：已确认种子在列表可见（面板数据源含历史）
        lst = (await c.get("/api/proposals")).json()
        assert any(p["id"] == spid and p["status"] == "confirmed"
                   for p in lst)
        # 4. 编辑页面：对账识别镜像外部改动（中栏 reconcile 警告数据源）
        rec = (await c.get("/api/reconcile")).json()
        assert {"chapter_id": "ch1", "status": "external_change"} in rec
        # 5. 聊天约束面：一轮工具调用产提案；响应无任何已确认动作
        body = (await c.post("/api/chat", json={
            "message": "帮我想个无限流前提"})).json()
        assert [e["type"] for e in body["events"]] == [
            "tool_call", "tool_result", "reply"]
        assert body["events"][0]["tool"] == "generate"
        assert all(e["type"] != "tool_call" or e["tool"] != "confirm"
                   for e in body["events"])      # 确认类不在工具白名单
        assert len(fake.calls) == 3               # 工具 JSON → 生成稿 → 回复
        assert len(body["proposal_ids"]) == 1
        pid = body["proposal_ids"][0]
        # 工作区数据源：新提案 pending（确认前不入生效集）
        pending = (await c.get("/api/proposals",
                               params={"status": "pending"})).json()
        assert any(p["id"] == pid for p in pending)
        # 6. 结构化确认路径：面板 confirm → confirmed
        r = await c.post(f"/api/proposals/{pid}/confirm")
        assert r.status_code == 200
        assert isinstance(r.json()["seq"], int) and "cascade" in r.json()
        assert (await c.get(f"/api/proposals/{pid}")
                ).json()["status"] == "confirmed"
    check = SnowelAPI.open(project)               # TC-SH-03 式独立句柄（共库）
    try:
        assert check.proposals.get(pid)["status"] == "confirmed"
    finally:
        check.close()
