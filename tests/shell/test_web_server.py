# tests/shell/test_web_server.py
"""Web 壳（W2/W5）：app 工厂项目绑定、租约会话、写守卫 409、静态 SPA serve。"""
import pytest
from httpx import ASGITransport, AsyncClient

from snowel_core.api import SnowelAPI
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


def test_web_rejects_non_project(tmp_path):
    # TC-SH-06：非项目目录启动 → 明确报错 + 非零退出（不阻塞 uvicorn）
    from typer.testing import CliRunner

    from snowel.cli import app

    res = CliRunner().invoke(app, ["web", "--project", str(tmp_path)])
    assert res.exit_code == 1
    assert "snowel init" in res.output
