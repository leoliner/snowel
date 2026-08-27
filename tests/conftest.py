import threading

import pytest
from snowel_core.storage import db

# L20 测试卫生：create_app 启动的心跳线程是 daemon，且 ASGITransport 不送
# lifespan 消息（_lifespan 的停止逻辑不触发）→ 线程+sqlite 连接随进程存活至
# 退出（良性但拖住 tmp 项目目录清理）。装了 Web 壳时包一层 create_app 登记
# 线程引用，会话收尾统一停（复用生产既有 Stop Event + join，与 _lifespan 同
# 款）；core-only 环境（未装 shell 包、fastapi 缺席）整块跳过，web 测试由
# importorskip 收集期跳过，套件其余部分照常跑。
_heartbeats: list[tuple[threading.Event, threading.Thread]] = []

try:
    _web_server_mod = __import__("snowel.web_server", fromlist=["x"])
except ImportError:
    _web_server_mod = None

if _web_server_mod is not None:
    _orig_create_app = _web_server_mod.create_app

    def _tracked_create_app(*args, **kwargs):
        app = _orig_create_app(*args, **kwargs)
        if app.state._heartbeat_thread is not None:
            _heartbeats.append((app.state._heartbeat_stop,
                                app.state._heartbeat_thread))
        return app

    _web_server_mod.create_app = _tracked_create_app


@pytest.fixture(scope="session", autouse=True)
def _stop_heartbeat_threads():
    """L20：会话收尾停掉全部遗留心跳线程（daemon，进程退出生前不回收）。"""
    yield
    for stop, _ in _heartbeats:
        stop.set()
    for _, t in _heartbeats:
        t.join(timeout=5)
    _heartbeats.clear()


@pytest.fixture
def core_conn(tmp_path):
    conn = db.connect(tmp_path / "snowel.db")
    db.migrate(conn)
    yield conn
    conn.close()


@pytest.fixture
def api(tmp_path):
    from snowel_core.api import SnowelAPI
    # 独立子目录：与 core_conn（tmp_path/snowel.db）分开，两库互不影响
    a = SnowelAPI.init_project(tmp_path / "api")
    yield a
    a.close()


class FakeBackend:
    """确定性生成端（tests/README §3）：按预设队列返回响应，记录调用供断言。"""

    def __init__(self, responses: list[str]):
        self.calls: list[dict] = []
        self._responses = list(responses)

    def generate(self, prompt: str, *, model: str | None = None,
                 system: str | None = None) -> str:
        self.calls.append({"prompt": prompt, "model": model, "system": system})
        return self._responses.pop(0)
