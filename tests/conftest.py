import pytest
from snowel_core.storage import db


@pytest.fixture
def core_conn(tmp_path):
    conn = db.connect(tmp_path / "snowel.db")
    db.migrate(conn)
    yield conn
    conn.close()


@pytest.fixture
def api(tmp_path):
    from snowel_core.api import SnowelAPI
    a = SnowelAPI.init_project(tmp_path)
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
