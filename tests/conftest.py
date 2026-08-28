import os
import threading
from pathlib import Path

import pytest
from snowel_core.storage import config, db

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


@pytest.fixture(scope="session", autouse=True)
def _isolated_home(tmp_path_factory):
    """会话级家目录隔离：SnowelAPI.init_project/open 尾部 reload 总会 discover
    真实全局 ~/.snowel/extensions——本机部署过全局扩展包时会把包注册进进程态
    注册表，翻转 writeback/consistency 等消费共享 api fixture 的测试语义
    （CI 绿本地红的无声漂移）。HOME/USERPROFILE/Path.home 三处钉死到空目录；
    个别用例自行的 monkey_patch_home 叠加其上无害。monkeypatch 是函数级
    fixture，会话级只能手工存取恢复。"""
    home = tmp_path_factory.mktemp("isolated_home")
    saved_env = {k: os.environ.get(k) for k in ("HOME", "USERPROFILE")}
    saved_home = Path.home
    os.environ["HOME"] = str(home)
    os.environ["USERPROFILE"] = str(home)
    Path.home = staticmethod(lambda: home)  # type: ignore[method-assign]
    yield home
    Path.home = saved_home                  # type: ignore[method-assign]
    for k, v in saved_env.items():
        if v is None:
            os.environ.pop(k, None)
        else:
            os.environ[k] = v


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


@pytest.fixture(autouse=True)
def _rewrite_off_by_default(monkeypatch):
    """套件封闭性（TC-RT-07）：retrieval.rewrite 生产默认开，开启时检索热路径
    经惰性 get_backend 触及真实 litellm——真实 key 下发真调用且结果受改写
    影响，无 key 时每条检索路径白付一次失败调用。

    注入设计：包 db.migrate 而非 autouse 依赖 core_conn/api——后者的 autouse
    依赖会强迫每个测试实例化两个用不到的 tmp 库，且罩不住 shell 各测试文件
    本地 project fixture（直调 SnowelAPI.init_project/open）的独立连接；全部
    测试库创建路径必经 migrate，一处包裹即全覆盖（调用方均为模块属性访问，
    无 from-import 直取，setattr 可见）。rewrite 语义测试在
    tests/retrieval/test_rewrite.py 显式 config.set(True) 回锚（含生产默认值
    断言）。teardown 不还原：monkeypatch 撤包裹即可，库随 tmp_path 即焚。
    """
    orig = db.migrate

    def _migrate_then_rewrite_off(conn):
        orig(conn)
        config.set(conn, "retrieval.rewrite", False)

    monkeypatch.setattr(db, "migrate", _migrate_then_rewrite_off)


class FakeBackend:
    """确定性生成端（tests/README §3）：按预设队列返回响应，记录调用供断言。"""

    def __init__(self, responses: list[str]):
        self.calls: list[dict] = []
        self._responses = list(responses)

    def generate(self, prompt: str, *, model: str | None = None,
                 system: str | None = None) -> str:
        self.calls.append({"prompt": prompt, "model": model, "system": system})
        return self._responses.pop(0)
