# src/snowel_core/writeback/hook.py
import threading

from ..storage import config
from ..writeback import mirror

MODES = ("auto", "manual", "timer")


class HookScheduler:
    """正文同步 hook（§3.3，P4 轮询对账）：auto=改动即抽取（短周期轮询）、
    manual=只登记不抽取（作者显式触发）、timer=按周期抽取。"""

    def __init__(self, api, backend, mode: str, interval: float):
        if mode not in MODES:
            raise ValueError(f"未知 hook 模式：{mode}（可用：{'/'.join(MODES)}）")
        self.api, self.backend, self.mode, self.interval = api, backend, mode, interval
        self._stop = threading.Event()
        self._renewer: threading.Thread | None = None

    @classmethod
    def from_config(cls, api, backend) -> "HookScheduler":
        mode = config.get(api._conn, "hook.mode", "manual")
        default_iv = {"auto": 2.0, "timer": 300.0, "manual": 0.0}[mode]
        return cls(api, backend, mode,
                   config.get(api._conn, "hook.interval", default_iv))

    def tick(self) -> list[dict]:
        out = []
        for ch in mirror.reconcile(self.api._conn, self.api._root):
            if ch["status"] == "external_change" and self.mode in ("auto", "timer"):
                try:
                    ch["extract"] = self.api.extract_and_writeback(
                        ch["chapter_id"], backend=self.backend)
                except Exception as e:  # 单章毒化不杀轮询线程：记错误继续余章
                    ch["extract_error"] = str(e)
            out.append(ch)
        return out

    def start(self) -> None:
        if self._renewer is not None or self.interval <= 0:
            return
        def _loop():
            while not self._stop.wait(self.interval):
                self.tick()
        self._renewer = threading.Thread(target=_loop, daemon=True)
        self._renewer.start()

    def stop(self) -> None:
        self._stop.set()
        if self._renewer is not None:
            self._renewer.join(timeout=5)
