# src/snowel_core/api.py
import json
from pathlib import Path

from .proposal.queue import ProposalQueue
from .storage import db, events, lease, projector, queries, vec
from .storage.projector import rebuild as _rebuild

class ProjectNotFoundError(Exception):
    """open() 目标目录缺少 snowel.db（L3：不静默新建空库）"""


def _default_llm(conn):
    """backend 未注入时的生产缺省（配置驱动，默认 litellm）。"""
    from .llm.ports import get_backend
    return get_backend(conn)

class SnowelAPI:
    def __init__(self, conn, root: Path | None = None):
        self._conn = conn
        self._root = root          # 项目根（写文件 IO 用，C1）
        self.proposals = ProposalQueue(conn)
        self._last_cascade = None  # 最近一次 confirm 的级联结果（E5 接线缓存）

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

    # 混合检索（Task 5/6）：壳一比一映射的只读门面
    def search(self, q: str, mode: str = "hybrid", limit: int = 20) -> dict:
        from .retrieval import hybrid
        return hybrid.search(self._conn, q, limit, mode)

    # 检索上下文审计（Task 6：TC-RT-02 排查面）
    def audit_recent(self, limit: int = 50) -> list[dict]:
        from .retrieval import audit
        return audit.recent(self._conn, limit)

    # 正文镜像导出（D8：CLI export 数据面，按章排序）
    def export_prose(self) -> list[dict]:
        return [dict(r) for r in self._conn.execute(
            "SELECT chapter_id, prose FROM chapter_prose ORDER BY chapter_id")]

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
    def rewrite_proposal(self, proposal_id: str, instruction: str,
                         backend=None) -> str:
        from .flow import revision
        backend = backend or _default_llm(self._conn)
        return revision.rewrite_proposal(self, proposal_id, instruction, backend)

    # 租约（C10）
    def acquire_lease(self, holder: str, stale_after: float = 30.0) -> bool:
        return lease.acquire(self._conn, holder, stale_after)

    def renew_lease(self, holder: str) -> bool:
        return lease.renew(self._conn, holder)

    def release_lease(self, holder: str) -> None:
        lease.release(self._conn, holder)

    def current_lease_holder(self) -> str | None:
        """只读门面：查当前写租约持有者（无租约或已释放则 None）。"""
        row = self._conn.execute(
            "SELECT holder FROM lease WHERE id=1").fetchone()
        return row["holder"] if row else None

    # 确认即写文件编排（C1）
    def confirm(self, proposal_id: str, exclude: list[str] | None = None) -> int:
        """统一确认入口：正文类提案确认即代写文件并登记哈希（C1）。

        级联接线（E5 四写入点之一，全量档）：分析在主事务前只读跑——比对
        基线=变更前生效值（projector 在确认事务内覆写物化值，事后分析回看
        不到旧值）；diff 提案在主事务后独立产出（P1/P2）。
        revision/retcon 不走此处（revision 无事实语义变更；retcon 有专属流程）。
        """
        p = self.proposals.get(proposal_id)
        payload = json.loads(p["payload"])
        facts = payload.get("facts", [])
        if exclude:  # TC-PR-09：剔除的事实不入事件 → 也不构成级联分析对象
            facts = [f for f in facts if f.get("id") not in set(exclude)]
        pre_violations = None
        if p["kind"] not in ("revision", "retcon") and facts:
            # 冻结线（C7）：变更落已封卷内设定 → 事务前拦截，提示走显式 retcon；
            # retcon 专属流程豁免（Task 8 的确认路径不走此处）；revision 无事实语义
            from .consistency import seal
            for f in facts:
                if f.get("fact") == "node":
                    vid = seal.sealed_volume_of(
                        self._conn, f.get("id"),
                        f.get("props", {}).get("address"))
                    if vid is not None:
                        raise seal.SealedVolumeError(
                            f"卷 {vid} 已封卷，设定改动须走显式 retcon")
            from .consistency import wiring
            pre_violations = wiring.analyze(self._conn, facts, "full")
        seq = self.proposals.confirm(proposal_id, exclude=exclude)
        if p["kind"] == "prose":
            from .writeback import mirror
            mirror.write_prose(self._conn, self._root,
                               payload["chapter_id"], payload["content"])
        if p["kind"] == "revision":  # §5.2：结构变更二段物化（E2 维持 int 返回）
            with db.transaction(self._conn):
                events.append_event(self._conn, "revision_applied", {
                    "structure_changes": payload.get("structure_changes", [])})
                projector.apply(self._conn)
            # C5（revision 面）：pending 全标 stale，受影响分析归级联检查计划
            for row in self.proposals.list(status="pending"):
                self.proposals.mark_stale(
                    row["id"],
                    f"上游 revision：{payload.get('node_id', '')} 结构变更")
        self._last_cascade = None
        if pre_violations is not None:  # 事务后收尾：major 矛盾产 diff 提案
            self._last_cascade = wiring.finalize(
                self._conn, pre_violations, seq, "full")
        return seq

    def last_cascade(self) -> dict | None:
        """最近一次 confirm 的级联结果（该次未跑级联则为 None）。

        E2 契约下 confirm 仍返回 int；级联结果经此暴露（MCP 壳增补
        "cascade" 键的数据面，壳任务接线）。
        """
        return self._last_cascade

    # 级联只读预演门面（E5）：Web/advanced 预演用，跑档返回 violations
    # + diff 预览，不入队任何提案
    def cascade_check(self, facts: list[dict], tier: str = "full") -> dict:
        from .consistency import wiring
        return wiring.preview(self._conn, facts, tier)

    # 崩溃窗口恢复（L6）：按已确认 prose 提案重放"确认即代写"
    def reregister_prose(self, proposal_id: str) -> str:
        p = self.proposals.get(proposal_id)
        if p is None or p["kind"] != "prose" or p["status"] != "confirmed":
            raise ValueError(
                f"提案 {proposal_id} 不是已确认（confirmed）的 prose 提案，无法重登记")
        payload = json.loads(p["payload"])
        from .writeback import mirror
        mirror.write_prose(self._conn, self._root,
                           payload["chapter_id"], payload["content"])
        return payload["chapter_id"]

    # 抽取回写（铁律 1：三端唯一入口，口签名住 llm/ports.py）
    def extract_and_writeback(self, chapter_id: str, backend, model=None):
        from .llm.ports import extract_and_writeback as _port
        return _port(self, chapter_id, backend, model=model)

    # 对账/手动抽取门面（§3.3，P4 三模式通用）
    def reconcile_prose(self) -> list:
        from .writeback import mirror
        return mirror.reconcile(self._conn, self._root)

    def trigger_extract(self, chapter_id: str, backend=None, model=None):
        backend = backend or _default_llm(self._conn)
        return self.extract_and_writeback(chapter_id, backend, model=model)

    def deviation(self, chapter_id: str) -> dict:
        from .writeback import deviation
        return deviation.report(self._conn, chapter_id)

    def latest_extract_proposal(self) -> dict | None:
        """最近一条抽取提案（按 created_ts 倒序取首；无则 None）。

        壳 writeback result 一比一映射此门面（铁律 1：领域语义留 core）。
        """
        row = self._conn.execute(
            "SELECT * FROM proposals WHERE kind='extract_facts' "
            "ORDER BY created_ts DESC LIMIT 1").fetchone()
        return dict(row) if row is not None else None

    # auto 条目事后否决 + 轻量反查（C2/C11）
    def list_auto(self) -> list[dict]:
        from .writeback import review
        return review.list_auto(self._conn)

    def reject_auto(self, entries: list[tuple[str, str]],
                    reason: str | None = None) -> dict:
        from .writeback import review
        return review.reject_auto(self._conn, entries, reason=reason)

    # 封卷（C7）与冻结线数据面（TC-CC-05/06/08）
    def seal(self, volume_id: str) -> int:
        """封卷：校验 Volume 节点存在且未封 → 追加 volume_sealed 事件并物化。

        已封卷拒绝（ValueError）；封卷后设定改动被冻结线拦截，须走显式 retcon。
        """
        from .consistency import seal
        return seal.seal_volume(self._conn, volume_id)

    def sealed_volumes(self) -> list:
        """已封卷列表（TC-CC-05 警告面数据源）：壳/Web 与 flow_state 卷树
        对减即未封卷集合——未封卷内写作仅警告不阻断（冻结线只拦已封卷）。"""
        return [dict(r) for r in self._conn.execute(
            "SELECT volume_id, sealed_seq FROM sealed_volumes "
            "ORDER BY sealed_seq")]
