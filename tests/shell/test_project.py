# tests/shell/test_project.py
import time

import pytest

from snowel_core.api import SnowelAPI
from snowel.project import ProjectError, open_project, resolve_project_path


@pytest.fixture
def project(tmp_path):
    SnowelAPI.init_project(tmp_path)
    return tmp_path


def test_resolve_priority_explicit_env_cwd(tmp_path, monkeypatch):
    (tmp_path / "a").mkdir()
    (tmp_path / "b").mkdir()
    monkeypatch.setenv("SNOWEL_PROJECT", str(tmp_path / "a"))
    assert resolve_project_path(str(tmp_path / "b")) == tmp_path / "b"
    assert resolve_project_path(None) == tmp_path / "a"
    monkeypatch.delenv("SNOWEL_PROJECT")
    monkeypatch.chdir(tmp_path / "b")
    assert resolve_project_path(None) == tmp_path / "b"


def test_open_missing_project_readable_error(tmp_path):
    with pytest.raises(ProjectError, match="snowel init"):
        open_project(tmp_path)


def test_open_holds_lease(project):
    ctx = open_project(project, heartbeat=False)
    try:
        assert ctx.readonly is False
        assert ctx.holder
    finally:
        ctx.close()


def test_second_instance_readonly_and_reads_ok(project):
    a = open_project(project, heartbeat=False)
    b = open_project(project, heartbeat=False)
    try:
        assert b.readonly is True
        with pytest.raises(ProjectError, match="只读"):
            b.require_write()
        assert b.api.find_nodes() == []  # 读操作不受影响（TC-SH-04）
    finally:
        b.close()
        a.close()


def test_release_then_next_can_write(project):
    a = open_project(project, heartbeat=False)
    a.close()
    b = open_project(project, heartbeat=False)
    try:
        assert b.readonly is False
    finally:
        b.close()


def test_heartbeat_keeps_lease_alive(project):
    a = open_project(project, stale_after=0.6, heartbeat=True)
    time.sleep(0.9)  # 超过 stale_after，但心跳在续
    b = open_project(project, heartbeat=False)
    try:
        assert b.readonly is True
    finally:
        b.close()
    a.close()


def test_lease_lost_flips_readonly(tmp_path):
    # L5：心跳失租后 readonly 必须翻转，require_write 拒绝
    from snowel import project as P
    from snowel_core.api import SnowelAPI
    SnowelAPI.init_project(tmp_path)
    ctx = P.open_project(tmp_path, stale_after=0.2, heartbeat=True)
    assert not ctx.readonly
    # 模拟持租进程僵死：把心跳戳拨回过去，他端抢租
    other = SnowelAPI.open(tmp_path)
    other._conn.execute("UPDATE lease SET heartbeat_ts=0")
    assert other.acquire_lease("rival@x:1", stale_after=0.2)
    other.close()
    import time; time.sleep(0.5)  # 等心跳线程 renew 失败（interval≈0.067s）
    assert ctx.readonly
    with pytest.raises(P.ProjectError):
        ctx.require_write()
    ctx.close()


def test_heartbeat_renew_exception_flips_readonly(project, monkeypatch):
    # L7：renew 抛异常（库文件锁等）按失租处理，readonly 翻转关死双写窗口
    def _raise(self, holder):
        raise RuntimeError("database is locked")
    monkeypatch.setattr(SnowelAPI, "renew_lease", _raise)
    ctx = open_project(project, stale_after=0.3, heartbeat=True)
    try:
        time.sleep(0.5)  # interval≈0.1s：多个续租周期均异常
        assert ctx.readonly
        with pytest.raises(ProjectError):
            ctx.require_write()
    finally:
        ctx.close()
