# tests/shell/test_web_server.py
"""Web 壳（W2/W5）：app 工厂项目绑定、租约会话、写守卫 409、静态 SPA serve。"""
import pytest
from httpx import ASGITransport, AsyncClient

from snowel_core.api import SnowelAPI
from snowel_core.writeback import mirror
from snowel.web_server import create_app

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
        r = await c.post("/api/proposal/xxx/confirm")
        assert r.status_code == 409 and "只读" in r.json()["detail"]
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
