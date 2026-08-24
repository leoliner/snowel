# shell/src/snowel/project.py
"""项目绑定（C4）与单写者租约的壳侧上下文（C10）。

每进程绑定一个项目；租约获取失败降级只读。心跳线程用独立连接
renew（sqlite 连接不跨线程共用），进程死亡 = 心跳停止，
租约经 stale_after 过期后他端可抢（无永久锁死）。
"""
from __future__ import annotations

import itertools
import os
import socket
import threading
from pathlib import Path

from snowel_core.api import ProjectNotFoundError, SnowelAPI


class ProjectError(Exception):
    """壳层可读错误：项目无效、只读越权等。"""


def resolve_project_path(explicit: str | Path | None = None) -> Path:
    """项目定位优先级（C4）：显式参数 > 环境变量 SNOWEL_PROJECT > cwd。"""
    if explicit is not None:
        return Path(explicit).resolve()
    env = os.environ.get("SNOWEL_PROJECT")
    if env:
        return Path(env).resolve()
    return Path.cwd()


class ProjectContext:
    def __init__(self, api: SnowelAPI, readonly: bool, holder: str | None,
                 project_path: Path):
        self.api = api
        self.readonly = readonly
        self.holder = holder
        self.project_path = project_path
        self._stop = threading.Event()
        self._renewer: threading.Thread | None = None

    def require_write(self) -> None:
        if self.readonly:
            raise ProjectError(
                "另一进程持有写租约，当前只读；写操作被拒绝"
                "（租约释放或过期后自动恢复）")

    def start_heartbeat(self, interval: float) -> None:
        def _loop() -> None:
            try:
                api2 = SnowelAPI.open(self.project_path)
            except ProjectNotFoundError:
                return
            try:
                while not self._stop.wait(interval):
                    if not api2.renew_lease(self.holder):
                        break  # 租约已被他端夺走，停止续期
            finally:
                api2.close()

        self._renewer = threading.Thread(target=_loop, daemon=True)
        self._renewer.start()

    def close(self) -> None:
        self._stop.set()
        if self._renewer is not None:
            self._renewer.join(timeout=5)
        if not self.readonly and self.holder:
            self.api.release_lease(self.holder)  # 按 holder 定向，失租后为 no-op
        self.api.close()


_ctx_seq = itertools.count()


def open_project(path: str | Path, want_write: bool = True,
                 stale_after: float = 30.0, heartbeat: bool = True,
                 ) -> ProjectContext:
    p = Path(path)
    try:
        api = SnowelAPI.open(p)
    except ProjectNotFoundError as e:
        raise ProjectError(
            f"目录不是 Snowel 项目（未找到 {p / 'snowel.db'}）；"
            f"请先运行 snowel init，或用 --project / SNOWEL_PROJECT 指定正确目录"
        ) from e
    # 同进程多次 open 也须互斥：holder 追加进程内序号，
    # 否则 core.acquire 会把同 holder 的重复获取当作幂等重入
    holder = f"snowel@{socket.gethostname()}:{os.getpid()}:{next(_ctx_seq)}"
    got = api.acquire_lease(holder, stale_after=stale_after) if want_write else False
    ctx = ProjectContext(api, readonly=not got,
                         holder=holder if got else None, project_path=p)
    if got and heartbeat:
        ctx.start_heartbeat(interval=max(stale_after / 3, 0.05))
    return ctx
