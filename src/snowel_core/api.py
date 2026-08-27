# src/snowel_core/api.py
import json
import uuid
from pathlib import Path
from typing import Iterator

from .proposal.queue import ProposalQueue
from .storage import db, events, lease, projector, queries, vec
from .storage.projector import rebuild as _rebuild

class ProjectNotFoundError(Exception):
    """open() 目标目录缺少 snowel.db（L3：不静默新建空库）"""


def _default_llm(conn):
    """backend 未注入时的生产缺省（配置驱动，默认 litellm）。"""
    from .llm.ports import get_backend
    return get_backend(conn)


def _register_derived_edges(conn, pairs) -> None:
    """DERIVED_FROM 补边共享实现（L25）：单事务一条 derived_from_registered
    携带全部 (src, dst) 对，随投影物化、重建可重放。

    TC-ON-12/§4.7：灵感提炼物建边（src=产物节点，dst=灵感节点）——同
    beat_merged/volume_sealed 模式：域操作自带事件 kind。confirm 与崩溃恢复
    共用此实现；幂等性（不补已存在的边）由调用方保证。
    """
    if not pairs:
        return
    with db.transaction(conn):
        events.append_event(
            conn, "derived_from_registered",
            {"facts": [{"fact": "edge", "id": str(uuid.uuid4()),
                        "src": src, "dst": dst,
                        "kind": "DERIVED_FROM", "props": {}}
                       for src, dst in pairs]})
        projector.apply(conn)

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

    def get_node(self, node_id, active_only=True):
        """节点反查（L17：默认仅活跃实体；读撤回行显式传 active_only=False）。"""
        return queries.get_node(self._conn, node_id, active_only)

    def find_nodes(self, name=None, type=None):
        return queries.find_nodes(self._conn, name, type)

    def edges_of(self, node_id, direction="both", active_only=True):
        """关联边反查（L17：默认仅两端均活跃的边；读撤回行显式传 active_only=False）。"""
        return queries.edges_of(self._conn, node_id, direction, active_only)

    def descendants(self, node_id, kinds=None, max_depth=10):
        return queries.descendants(self._conn, node_id, kinds, max_depth)

    def graph_stats(self) -> dict:
        return queries.graph_stats(self._conn)

    # 统计四件（W4 可视化数据面，铁律 1：纯统计留在 core）
    def stats_pov(self) -> dict:
        return queries.stats_pov(self._conn)

    def stats_foreshadow(self) -> dict:
        return queries.stats_foreshadow(self._conn)

    def stats_relations(self) -> dict:
        return queries.stats_relations(self._conn)

    def stats_pacing(self) -> dict:
        return queries.stats_pacing(self._conn)

    def rebuild(self):
        _rebuild(self._conn)

    def backup(self, out_path) -> None:
        db.backup(self._conn, out_path)

    # 混合检索（Task 5/6）：壳一比一映射的只读门面
    def search(self, q: str, mode: str = "hybrid", limit: int = 100) -> dict:
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

    # 按章正文（T11 加载面）：镜像水化全文，无行 → None
    def chapter_prose(self, chapter_id: str) -> str | None:
        row = self._conn.execute(
            "SELECT prose FROM chapter_prose WHERE chapter_id=?",
            (chapter_id,)).fetchone()
        return row["prose"] if row is not None else None

    # 流程状态（FL-03）
    def flow_state(self) -> dict:
        from .flow import state
        return state.flow_state(self._conn)

    # 生成环（E3/D7）：产出必进提案队列，门面不暴露任何直接返回生成文本的路径
    def ai_generate(self, artifact_type: str, locate: dict | None = None,
                    extra: dict | None = None, backend=None,
                    derive_from: list[str] | None = None) -> str:
        from .flow import generate
        return generate.ai_generate(self, artifact_type, locate, extra,
                                    backend, derive_from)

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
        if p["kind"] == "retcon":
            # 拦截：retcon 有专属确认流程（confirm_retcon，Task 8）——通用确认会
            # 静默丢弃 renames/track_updates、不跑 C5 stale，半应用且无恢复路径
            raise ValueError(
                f"提案 {proposal_id} 是 retcon 提案，须走 confirm_retcon 确认")
        payload = json.loads(p["payload"])
        facts = payload.get("facts", [])
        if exclude:  # TC-PR-09：剔除的事实不入事件 → 也不构成级联分析对象
            facts = [f for f in facts if f.get("id") not in set(exclude)]
        pre_violations = None
        if p["kind"] not in ("revision",) and facts:
            # 冻结线（C7）：变更落已封卷内设定 → 事务前拦截，提示走显式 retcon；
            # revision 无事实语义（结构变更走二段物化）；retcon 已在函数入口整体拒绝
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
        # TC-ON-12/§4.7：灵感提炼物确认后建 DERIVED_FROM 边（src=产物节点，
        # dst=灵感节点）——补边实现见 _register_derived_edges（L25 与恢复共用）
        if payload.get("derive_from"):
            product_ids = [f["id"] for f in facts if f.get("fact") == "node"]
            _register_derived_edges(
                self._conn,
                [(src, dst) for src in product_ids
                 for dst in payload["derive_from"]])
        if p["kind"] == "prose":
            from .writeback import mirror
            mirror.write_prose(self._conn, self._root,
                               payload["chapter_id"], payload["content"])
        if p["kind"] == "revision":  # §5.2：结构变更二段物化（E2 维持 int 返回）
            with db.transaction(self._conn):
                events.append_event(self._conn, "revision_applied", {
                    "structure_changes": payload.get("structure_changes", [])})
                projector.apply(self._conn)
            # C5（revision 面，P4 精确）：变更触及节点 id ∩ pending 提案 payload
            # 含该 id → 只标受影响提案（替代 T17 全 pending 保守标记，L14 单事务批量）
            from .consistency import retcon
            node_ids = {ch["node_id"] for ch in payload.get("structure_changes", [])
                        if ch.get("node_id")}
            pids = retcon.affected_pending(self._conn, node_ids)
            if pids:
                retcon.mark_stale_batch(
                    self._conn, pids,
                    f"上游 revision：{payload.get('node_id', '')} 结构变更")
        self._last_cascade = None
        if pre_violations is not None:  # 事务后收尾：major 矛盾产 diff 提案
            self._last_cascade = wiring.finalize(
                self._conn, pre_violations, seq, "full")
        return seq

    def recover_derived_from(self) -> int:
        """两阶段崩溃恢复（L25/addendum §2.2）：补齐 confirm 崩溃窗口丢失的边。

        confirm 先物化产物（proposal_confirmed 事务）、后补 DERIVED_FROM 边
        （derived_from_registered 事务），两事务间崩溃会留下"产物已物化、
        边缺失"的缺口。此处扫描已确认提案补录：LIKE 粗筛 → json 解析精筛 →
        候选 (产物 id, 灵感 id) 仅在两端节点均存在且边缺失时补——exclude 剔除
        的事实未物化、自然跳过。单条事件携带全部缺边，幂等；无缺口返回 0，
        有补录返回补录事件数（1）。
        """
        conn = self._conn
        rows = conn.execute(
            "SELECT payload FROM proposals "
            "WHERE status='confirmed' AND payload LIKE ?",
            ('%"derive_from"%',)).fetchall()
        missing = []
        for r in rows:
            payload = json.loads(r["payload"])
            dsts = payload.get("derive_from")
            if not dsts:  # 粗筛可被草稿文本误中，json 精筛为准
                continue
            srcs = [f["id"] for f in payload.get("facts", [])
                    if f.get("fact") == "node"]
            for src in srcs:
                node = conn.execute(
                    "SELECT 1 FROM nodes WHERE id=?", (src,)).fetchone()
                if node is None:  # R4：两端节点均存在才补（src 缺失整组跳过）
                    continue
                for dst in dsts:
                    dst_node = conn.execute(
                        "SELECT 1 FROM nodes WHERE id=?", (dst,)).fetchone()
                    edge = conn.execute(
                        "SELECT 1 FROM edges WHERE src=? AND dst=? "
                        "AND kind='DERIVED_FROM'", (src, dst)).fetchone()
                    if dst_node is not None and edge is None:
                        missing.append((src, dst))
        _register_derived_edges(conn, missing)
        return 1 if missing else 0

    def last_cascade(self) -> dict | None:
        """最近一次 confirm 的级联结果（该次未跑级联则为 None）。

        E2 契约下 confirm 仍返回 int；级联结果经此暴露（MCP 壳增补
        "cascade" 键的数据面，壳任务接线）。
        """
        return self._last_cascade

    def proposal_kind(self, proposal_id: str) -> str:
        """只读门面：查提案 kind（MCP 壳 confirm 分派用：retcon → confirm_retcon）。"""
        p = self.proposals.get(proposal_id)
        if p is None:
            raise ValueError(f"提案 {proposal_id} 不存在")
        return p["kind"]

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
    def reconcile_prose(self, dry_run: bool = False) -> list:
        """正文镜像对账（D8）：文件是真相源，哈希不一致以文件为准重灌镜像。

        dry_run=True 只收集 changed/missing 清单不写库（Web 只读对账状态
        用，F2：readonly 会话不得写库）；MCP 写动作走默认 dry_run=False。
        """
        from .writeback import mirror
        return mirror.reconcile(self._conn, self._root, dry_run=dry_run)

    def trigger_extract(self, chapter_id: str, backend=None, model=None):
        backend = backend or _default_llm(self._conn)
        return self.extract_and_writeback(chapter_id, backend, model=model)

    # 批量抽取（R3/TC-RT-05）：循环便捷入口——省操作不省调用，单章一次调用不变
    def extract_many(self, chapter_ids: list[str], backend) -> list[dict]:
        """按序循环单章抽取，返回逐章结果列表。

        单章失败不吞：成功条目为抽取结果（含 chapter_id），失败条目为
        {"chapter_id": ..., "error": ...}，调用方按 chapter_id 对齐。
        """
        results = []
        for cid in chapter_ids:
            try:
                results.append(self.extract_and_writeback(cid, backend))
            except Exception as e:
                results.append({"chapter_id": cid, "error": str(e)})
        return results

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

    # 显式 retcon（C7 冻结线合法通道，TC-CC-07）：propose 全量级联 → 专属确认
    def propose_retcon(self, facts=None, renames=None, track_updates=None,
                       reason: str = "") -> dict:
        """创建 kind="retcon" 提案（payload 携带影响清单），创建时跑全量级联（P5）。

        retcon 的级联在 propose 时跑（P5），确认时不再重跑——此处把影响清单
        同步进 _last_cascade，MCP 壳 confirm 响应的 "cascade" 键才能反映
        本次 retcon 流程（T10 接线面，与 revision 确认置 None 同理）。
        """
        from .consistency import retcon
        out = retcon.propose_retcon(self, facts, renames, track_updates, reason)
        self._last_cascade = {"tier": "full",
                              "violations": out["impact"]["violations"],
                              "cascade_proposal_id": None}
        return out

    def confirm_retcon(self, proposal_id: str) -> int:
        """retcon 专属确认（冻结线豁免）：单事务双事件物化 + 事务后 C5 精确 stale。"""
        from .consistency import retcon
        return retcon.confirm_retcon(self, proposal_id)

    # 伏笔注册（§4.8，TC-ON-14 手动 author 通道）：校验 → 建 kind="foreshadow"
    # 提案（铁律 3），确认走 api.confirm（级联/冻结线随 confirm 接线自然生效）
    def register_foreshadow(self, name: str, planted_at: str,
                            origin: str = "author", payoff_beat: str | None = None,
                            note: str = "") -> str:
        """注册伏笔：校验 planted_at（已有 MicroBeat/Scene/Chapter 节点 id）
        与 origin ∈ {"author", "ai"} 后建提案，返回 pid。"""
        from .consistency import foreshadow
        return foreshadow.register(self, name, planted_at, origin,
                                   payoff_beat, note)

    # 拍合并（D6/TC-ON-08）：校验 → 单事件 beat_merged（R1/R2）→ 物化
    def merge_beats(self, source_beat_id: str, target_beat_id: str) -> int:
        """合并两拍：源拍失效，其伏笔引用与边有效期迁移到目标拍，返回事件 seq。

        校验两节点存在且活跃、均含 MicroBeat 类型、id 不同；事务内预查
        props.foreshadow.planted_at == source 的 Foreshadow 节点与
        props.valid_until_beat == source 的边，把迁移清单（old/new）先算后写
        进事件载荷——投影器严格按载荷执行。
        """
        conn = self._conn
        if source_beat_id == target_beat_id:
            raise ValueError(f"源拍与目标拍不能相同: {source_beat_id}")
        # L23：两端任一已失效即拒（重复合并同一源拍自然拒绝，无新错误分支）
        for nid in (source_beat_id, target_beat_id):
            row = conn.execute(
                "SELECT types FROM nodes WHERE id=? AND active=1",
                (nid,)).fetchone()
            if row is None:
                raise ValueError(f"拍节点不存在或已失效: {nid}")
            if "MicroBeat" not in json.loads(row["types"]):
                raise ValueError(f"合并两端必须是 MicroBeat 节点: {nid}")
        with db.transaction(conn):
            # 预查全部在事务内、append_event 之前（TOCTOU：预查与写入同锁窗口）
            moved = [{"foreshadow_id": r["id"], "old": source_beat_id,
                      "new": target_beat_id} for r in conn.execute(
                """SELECT id FROM nodes
                   WHERE types LIKE '%"Foreshadow"%'
                     AND json_extract(props, '$.foreshadow.planted_at') = ?""",
                (source_beat_id,))]
            moved_valid_until = [
                {"edge_id": r["id"], "old": source_beat_id,
                 "new": target_beat_id} for r in conn.execute(
                """SELECT id FROM edges
                   WHERE json_extract(props, '$.valid_until_beat') = ?""",
                (source_beat_id,))]
            seq = events.append_event(conn, "beat_merged", {
                "source_beat_id": source_beat_id,
                "target_beat_id": target_beat_id,
                "moved_foreshadows": moved,
                "moved_valid_until": moved_valid_until})
            projector.apply(conn)
        return seq

    # 拍删除（addendum §2.1/TC-ON-17）：校验 → 事务内预查伏笔引用 → 单事件 beat_deleted
    def delete_beat(self, beat_id: str, reason: str | None = None) -> int:
        """删除拍：追加 beat_deleted 事件使该拍失效，返回事件 seq。

        校验节点存在、含 MicroBeat 类型（R1：不查 active——已合并失效的拍
        仍可显式删除）；事务内预查 props.foreshadow.planted_at 引用，
        >0 则拒绝（严格拒绝语义）。通过则单事务追加事件并物化。
        """
        conn = self._conn
        row = conn.execute(
            "SELECT types FROM nodes WHERE id=?", (beat_id,)).fetchone()
        if row is None:
            raise ValueError(f"拍节点不存在: {beat_id}")
        if "MicroBeat" not in json.loads(row["types"]):
            raise ValueError(f"删除对象必须是 MicroBeat 节点: {beat_id}")
        payload = {"beat_id": beat_id}
        if reason is not None:
            payload["reason"] = reason
        with db.transaction(conn):
            refs = conn.execute(
                """SELECT id FROM nodes
                   WHERE types LIKE '%"Foreshadow"%'
                     AND json_extract(props, '$.foreshadow.planted_at') = ?""",
                (beat_id,)).fetchall()
            if refs:  # 事务内预查：拒绝不留半事件，与追加同锁窗口无 TOCTOU
                raise ValueError(
                    f"该拍承载 {len(refs)} 个伏笔引用，"
                    "先 merge_beats 到承接拍或迁移伏笔")
            seq = events.append_event(conn, "beat_deleted", payload)
            projector.apply(conn)
        return seq

    # 低重要标记（R4/§6.3，TC-RT-05）：作者显式操作——单事件 + 投影，不走提案
    def set_chapter_importance(self, chapter_id: str, importance: str) -> int:
        """标记章重要度：importance ∈ {"low", "normal"} → chapter_importance_set 事件。

        校验取值与 Chapter 节点存在后落事件并物化（R4：元数据改动事件化，
        rebuild 后不漂移）。返回事件 seq。
        """
        if importance not in ("low", "normal"):
            raise ValueError(f"importance 只允许 low/normal：{importance}")
        conn = self._conn
        row = conn.execute("SELECT types FROM nodes WHERE id=?",
                           (chapter_id,)).fetchone()
        if row is None:
            raise ValueError(f"章节节点不存在: {chapter_id}")
        if "Chapter" not in json.loads(row["types"]):
            raise ValueError(f"节点 {chapter_id} 不是 Chapter 节点")
        with db.transaction(conn):
            seq = events.append_event(conn, "chapter_importance_set", {
                "chapter_id": chapter_id, "importance": importance})
            projector.apply(conn)
        return seq

    # 灵感层（§4.7，TC-ON-12）：作者手输原话直接落事件（不走提案，铁律 3 不约束作者）
    def save_inspiration(self, text: str) -> str:
        """保存灵感原话：追加 inspiration_saved 事件（facts 含 Inspiration 节点）。

        作者手输属显式操作——原话全文存 props.inspiration.text 永久保留，
        后续提炼物经 DERIVED_FROM 边指回本节点（R2）。
        """
        iid = str(uuid.uuid4())
        with db.transaction(self._conn):
            events.append_event(self._conn, "inspiration_saved", {
                "facts": [{"fact": "node", "id": iid, "types": ["Inspiration"],
                           "name": text,
                           "props": {"inspiration": {"text": text}}}]})
            projector.apply(self._conn)
        return iid

    def inspirations(self) -> list[dict]:
        """灵感列表：Inspiration 活跃节点全集（text 取 props.inspiration.text）。"""
        return [{"id": r["id"], "name": r["name"],
                 "text": json.loads(r["props"])["inspiration"]["text"]}
                for r in self.find_nodes(type="Inspiration")]

    # 聊天代理（W1/W6）：JSON 指令循环；工具白名单不含确认类（§7.1 红线）
    def chat(self, message: str, history=None, backend=None,
             max_turns: int = 8) -> dict:
        """非流式聚合门面：{"events": [除 done 外全部事件], "proposal_ids": [...]}。"""
        from .llm import chat
        return chat.run(self, message, history, backend, max_turns)

    def chat_stream(self, message: str, history=None, backend=None,
                    max_turns: int = 8) -> Iterator[dict]:
        """流式门面：同步生成器逐事件 yield，末事件 done 携带 proposal_ids。"""
        from .llm import chat
        return chat.run_stream(self, message, history, backend, max_turns)
