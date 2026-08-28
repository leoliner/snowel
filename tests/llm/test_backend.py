# tests/llm/test_backend.py
import pytest
from tests.conftest import FakeBackend

from snowel_core.llm import backend, ports


def test_rewrite_query_rewrites_with_backend(core_conn):  # TC-RT-07 桩转正
    from snowel_core.storage import config
    fake = FakeBackend(["雨夜旧友", "旧队友"])
    assert ports.rewrite_query(core_conn, "那晚的人", {}, backend=fake) \
        == "雨夜旧友"
    assert fake.calls[0]["model"] is None  # 未配 rewrite_model → backend 默认模型
    config.set(core_conn, "retrieval.rewrite_model", "small-x")
    assert ports.rewrite_query(core_conn, "那晚的人", {}, backend=fake) \
        == "旧队友"
    assert fake.calls[1]["model"] == "small-x"  # 小模型路由（仿 extraction.small_model）
    # 模型原样回显 = 无有效改写：返回原文本身（调用方不落改写审计）
    assert ports.rewrite_query(core_conn, "林晚", {},
                               backend=FakeBackend(["林晚"])) == "林晚"
    # 开关关：在解析 backend 之前早退——返回原样且零 LLM 调用
    config.set(core_conn, "retrieval.rewrite", False)
    off = FakeBackend(["x"])
    assert ports.rewrite_query(core_conn, "林晚", {}, backend=off) == "林晚"
    assert off.calls == []


def test_rewrite_query_failure_returns_none(core_conn):  # 失败回落信号
    class Boom:
        def generate(self, prompt, *, model=None, system=None):
            raise TimeoutError("rewrite timeout")

    assert ports.rewrite_query(core_conn, "林晚", {}, backend=Boom()) is None
    # 空产出（strip 后为空）同视为失败
    assert ports.rewrite_query(core_conn, "林晚", {},
                               backend=FakeBackend(["   "])) is None


def test_litellm_backend_lazy_and_default_model(core_conn, monkeypatch):
    from snowel_core.storage import config
    config.set(core_conn, "llm.model", "gpt-dummy")
    b = backend.LitellmBackend.for_conn(core_conn)
    assert b.default_model == "gpt-dummy"

    calls = {}
    monkeypatch.setattr("litellm.completion",
                        lambda **kw: calls.update(kw) or {
                            "choices": [{"message": {"content": "ok"}}]})
    assert b.generate("你好", model="small-model") == "ok"
    assert calls["model"] == "small-model"        # per-call 模型覆盖（§6.3 成本控制）


def test_get_backend_default_and_unknown(core_conn):
    from snowel_core.storage import config
    b = ports.get_backend(core_conn)
    assert isinstance(b, backend.LitellmBackend)
    assert b.default_model == "gpt-4o-mini"

    config.set(core_conn, "llm.model", "gpt-dummy")
    assert ports.get_backend(core_conn).default_model == "gpt-dummy"

    config.set(core_conn, "llm.backend", "nope")
    with pytest.raises(ValueError, match="未知 llm.backend"):
        ports.get_backend(core_conn)
