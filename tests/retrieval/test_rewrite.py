# tests/retrieval/test_rewrite.py
"""TC-RT-07：检索改写层三态——改写生效（审计可见）/ 失败回落（标记）/ 关闭（纯确定性）。"""
import json

from tests.conftest import FakeBackend

from snowel_core.retrieval import audit, context
from snowel_core.storage import config, db, events, projector


def _confirm(conn, facts, kind="t"):
    with db.transaction(conn):
        events.append_event(conn, "proposal_confirmed",
                            {"facts": facts, "artifact_type": kind})
    projector.apply(conn)


def _seed(conn, extra=()):
    _confirm(conn, [
        {"fact": "node", "id": "w1", "types": ["Concept"], "name": "轮回游戏",
         "props": {}},
        *extra])


def _rearm_rewrite_on(conn):
    """conftest 预置关闭（套件封闭性）后的回锚：删键还原"未 set"态断言生产
    默认开（TC-RT-07 裁决 9 不因测试预置失锚），再显式置 True 不依赖预置顺序。"""
    conn.execute("DELETE FROM config WHERE key='retrieval.rewrite'")
    assert config.get(conn, "retrieval.rewrite", True) is True
    config.set(conn, "retrieval.rewrite", True)


def test_rewrite_changes_search_terms_visible_in_audit(api, monkeypatch):
    # 前半：改写生效——以改写词命中（原词本不命中），检索词变化可见于
    # strategy="search" 条件审计行（original→rewritten）
    _rearm_rewrite_on(api._conn)
    _seed(api._conn)
    fake = FakeBackend(["轮回"])
    monkeypatch.setattr("snowel_core.llm.ports.get_backend", lambda conn: fake)
    out = api.search("无限流")
    assert "w1" in [n["node_id"] for n in out["nodes"]]
    row = audit.recent(api._conn)[0]
    assert row["strategy"] == "search"
    assert json.loads(row["bundle"])["rewrite"] \
        == {"original": "无限流", "rewritten": "轮回"}
    assert "无限流" in fake.calls[0]["prompt"]
    # 对照：原词直查不命中——证明改写真实改变了检索词
    config.set(api._conn, "retrieval.rewrite", False)
    assert "w1" not in [n["node_id"] for n in
                        api.search("无限流")["nodes"]]
    assert len(audit.recent(api._conn)) == 1  # 关闭路径零新增审计行


def test_rewrite_failure_falls_back_with_marker(api, monkeypatch):
    # 中段：改写 LLM 失败——回落原词检索（结果仍出）+ rewrite_failed 标记
    _rearm_rewrite_on(api._conn)
    _seed(api._conn, extra=[
        {"fact": "node", "id": "h1", "types": ["Character"], "name": "林晚",
         "props": {}}])

    class Boom:
        def generate(self, prompt, *, model=None, system=None):
            raise TimeoutError("改写超时")

    monkeypatch.setattr("snowel_core.llm.ports.get_backend", lambda conn: Boom())
    out = api.search("林晚")
    assert "h1" in [n["node_id"] for n in out["nodes"]]
    assert json.loads(audit.recent(api._conn)[0]["bundle"])["rewrite"] \
        == {"failed": True, "original": "林晚"}


def test_rewrite_disabled_pure_deterministic(api, monkeypatch):
    # 末段：开关关 = 纯确定性路径——零审计行、零 LLM 调用、检索直查
    _seed(api._conn)
    config.set(api._conn, "retrieval.rewrite", False)
    fake = FakeBackend(["轮回"])  # 若被误用会改写检索词并留下调用记录
    monkeypatch.setattr("snowel_core.llm.ports.get_backend", lambda conn: fake)
    out = api.search("轮回游戏")
    assert "w1" in [n["node_id"] for n in out["nodes"]]
    assert fake.calls == []
    assert audit.recent(api._conn) == []


def test_compose_context_fallback_recalls_rewritten(core_conn, monkeypatch):
    # 入口 B：compose_context 兜底召回以改写词检索；不新增 search 行——
    # 改写明细并入既有 compose 审计行（R2 "天然携带同一 rewrite 键"）
    _rearm_rewrite_on(core_conn)
    _seed(core_conn)
    fake = FakeBackend(["轮回"])
    monkeypatch.setattr("snowel_core.llm.ports.get_backend", lambda conn: fake)
    bundle = context.compose_context(core_conn, "generic",
                                     locate={"query": "无限流"})
    fb = [s for s in bundle["sections"] if s["kind"] == "fallback_recall"]
    assert fb and fb[0]["refs"] == ["w1"]
    rows = audit.recent(core_conn)
    assert len(rows) == 1
    assert json.loads(rows[0]["bundle"])["rewrite"] \
        == {"original": "无限流", "rewritten": "轮回"}
    assert "无限流" in fake.calls[0]["prompt"]
