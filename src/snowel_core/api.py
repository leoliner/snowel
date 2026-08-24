# src/snowel_core/api.py
import json
from pathlib import Path

from .proposal.queue import ProposalQueue
from .storage import db, events, lease, projector, queries, vec
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

    # 小雪花章级展开（FL-04）：按序产三提案（意图→微节拍组→正文），不自动确认
    def expand_chapter(self, chapter_id: str, backend,
                       extra: dict | None = None) -> list[str]:
        from .flow import snowflake
        return snowflake.expand_chapter(self, chapter_id, backend, extra)

    # 卷级展开（FL-01/02）：卷首世界状态实时重放（C8，不落快照）
    def volume_start_state(self, volume_id: str) -> dict:
        from .flow import snowflake
        return snowflake.volume_start_state(self._conn, volume_id)

    # 卷级展开：主题→三幕两提案，locate 携带卷首状态进卷级上下文，不自动确认
    def expand_volume(self, volume_id: str, backend,
                      extra: dict | None = None) -> list[str]:
        from .flow import snowflake
        return snowflake.expand_volume(self, volume_id, backend, extra)

    # 统一 revision（§5.2/FL-06）：三层同口，提案→确认→revision_applied
    def propose_revision(self, node_id: str, new_address: dict,
                         reason: str = "") -> str:
        from .flow import revision
        return revision.propose_revision(self, node_id, new_address, reason)

    # 提案改写（D7 rewrite）：新提案标 rewritten_from，原提案留队不动
    def rewrite_proposal(self, proposal_id: str, instruction: str, backend) -> str:
        from .flow import revision
        return revision.rewrite_proposal(self, proposal_id, instruction, backend)

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
        if p["kind"] == "revision":  # §5.2：结构变更二段物化（E2 维持 int 返回）
            payload = json.loads(p["payload"])
            with db.transaction(self._conn):
                events.append_event(self._conn, "revision_applied", {
                    "structure_changes": payload.get("structure_changes", [])})
                projector.apply(self._conn)
            # C5（revision 面）：pending 全标 stale，受影响分析归级联检查计划
            for row in self.proposals.list(status="pending"):
                self.proposals.mark_stale(
                    row["id"],
                    f"上游 revision：{payload.get('node_id', '')} 结构变更")
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
