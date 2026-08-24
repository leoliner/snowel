# tests/shell/test_lease_integration.py
"""跨壳租约行为（TC-SH-04/05）：降级只读、崩溃恢复、心跳保活。"""
import time

import pytest

from snowel_core.api import SnowelAPI
from snowel.project import ProjectError, open_project

pytestmark = pytest.mark.anyio


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
def project(tmp_path):
    SnowelAPI.init_project(tmp_path)
    return tmp_path


def test_readonly_blocks_write_allows_read(project):  # TC-SH-04
    a = open_project(project, heartbeat=False)
    b = open_project(project, heartbeat=False)
    try:
        assert a.readonly is False and b.readonly is True
        with pytest.raises(ProjectError, match="只读"):
            b.require_write()
        assert b.api.graph_stats()["nodes"] == 0  # 读全部正常
    finally:
        b.close()
        a.close()


def test_lease_recoverable_after_crash(project):  # TC-SH-05：心跳停 = 进程死
    a = open_project(project, stale_after=0.5, heartbeat=False)
    assert a.readonly is False
    time.sleep(0.7)  # 无心跳 → 过期
    b = open_project(project, stale_after=0.5, heartbeat=False)
    try:
        assert b.readonly is False  # 可抢，无永久锁死
    finally:
        b.close()
    a.close()  # a 已失租：close 的 release 按 holder 定向，为 no-op


async def test_mcp_write_blocked_by_cli_holder(project):  # TC-SH-04 跨壳
    from mcp.shared.memory import create_connected_server_and_client_session

    from snowel.mcp_server import build_mcp

    blocker = open_project(project, heartbeat=False)  # CLI/他进程持租约
    ctx = open_project(project)  # MCP 实例：抢不到 → readonly
    try:
        assert ctx.readonly is True
        mcp = build_mcp(ctx)
        async with create_connected_server_and_client_session(
                mcp._mcp_server) as client:
            res = await client.call_tool(
                "snowel_advanced", {"op": "rebuild"})
            assert res.isError  # 写类操作被拒
            ok = await client.call_tool("snowel_status", {})
            assert not ok.isError  # 读操作正常
    finally:
        ctx.close()
        blocker.close()
