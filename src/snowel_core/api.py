# src/snowel_core/api.py
import json
from pathlib import Path

from .proposal.queue import ProposalQueue
from .storage import db, lease, queries, vec
from .storage.projector import rebuild as _rebuild

class ProjectNotFoundError(Exception):
    """open() 目标目录缺少 snowel.db（L3：不静默新建空库）"""

class SnowelAPI:
    def __init__(self, conn, root: Path | None = None):
        self._conn = conn
        self._root = root          # 项目根（写文件 IO 用，C1）
        self.proposals = ProposalQueue(conn)

    @classmethod
    def init_project(cls, path) -> "SnowelAPI":
        p = Path(path); p.mkdir(parents=True, exist_ok=True)
        conn = db.connect(p / "snowel.db"); db.migrate(conn); vec.ensure(conn)
        return cls(conn, root=p)

    @classmethod
    def open(cls, path) -> "SnowelAPI":
        db_path = Path(path) / "snowel.db"
        if not db_path.exists():
            raise ProjectNotFoundError(f"未找到项目库：{db_path}")
        conn = db.connect(db_path)
        db.migrate(conn)  # 旧库补新表（schema 全 IF NOT EXISTS，幂等）；apply 尾部 fts.refresh 依赖新表
        vec.ensure(conn)
        return cls(conn, root=Path(path))

    def close(self):
        self._conn.close()

    # 只读查询（代理 storage.queries）
    def state_at(self, story_order: int):
        return queries.state_at(self._conn, story_order)

    def get_node(self, node_id):
        return queries.get_node(self._conn, node_id)

    def find_nodes(self, name=None, type=None):
        return queries.find_nodes(self._conn, name, type)

    def edges_of(self, node_id, direction="both"):
        return queries.edges_of(self._conn, node_id, direction)

    def descendants(self, node_id, kinds=None, max_depth=10):
        return queries.descendants(self._conn, node_id, kinds, max_depth)

    def graph_stats(self) -> dict:
        return queries.graph_stats(self._conn)

    def rebuild(self):
        _rebuild(self._conn)

    def backup(self, out_path) -> None:
        db.backup(self._conn, out_path)

    # 流程状态（FL-03）
    def flow_state(self) -> dict:
        from .flow import state
        return state.flow_state(self._conn)

    # 生成环（E3/D7）：产出必进提案队列，门面不暴露任何直接返回生成文本的路径
    def ai_generate(self, artifact_type: str, locate: dict | None = None,
                    extra: dict | None = None, backend=None) -> str:
        from .flow import generate
        return generate.ai_generate(self, artifact_type, locate, extra, backend)

    # 租约（C10）
    def acquire_lease(self, holder: str, stale_after: float = 30.0) -> bool:
        return lease.acquire(self._conn, holder, stale_after)

    def renew_lease(self, holder: str) -> bool:
        return lease.renew(self._conn, holder)

    def release_lease(self, holder: str) -> None:
        lease.release(self._conn, holder)

    # 确认即写文件编排（C1）
    def confirm(self, proposal_id: str, exclude: list[str] | None = None) -> int:
        """统一确认入口：正文类提案确认即代写文件并登记哈希（C1）。"""
        p = self.proposals.get(proposal_id)
        seq = self.proposals.confirm(proposal_id, exclude=exclude)
        if p["kind"] == "prose":
            payload = json.loads(p["payload"])
            from .writeback import mirror
            mirror.write_prose(self._conn, self._root,
                               payload["chapter_id"], payload["content"])
        return seq

    # 抽取回写（铁律 1：三端唯一入口，口签名住 llm/ports.py）
    def extract_and_writeback(self, chapter_id: str, backend, model=None):
        from .llm.ports import extract_and_writeback as _port
        return _port(self, chapter_id, backend, model=model)

    # 对账/手动抽取门面（§3.3，P4 三模式通用）
    def reconcile_prose(self) -> list:
        from .writeback import mirror
        return mirror.reconcile(self._conn, self._root)

    def trigger_extract(self, chapter_id: str, backend, model=None):
        return self.extract_and_writeback(chapter_id, backend, model=model)

    def deviation(self, chapter_id: str) -> dict:
        from .writeback import deviation
        return deviation.report(self._conn, chapter_id)

    # auto 条目事后否决 + 轻量反查（C2/C11）
    def list_auto(self) -> list[dict]:
        from .writeback import review
        return review.list_auto(self._conn)

    def reject_auto(self, entries: list[tuple[str, str]],
                    reason: str | None = None) -> dict:
        from .writeback import review
        return review.reject_auto(self._conn, entries, reason=reason)
