# tests/llm/test_backend.py
import pytest
from snowel_core.llm import backend, ports


def test_rewrite_query_stub_returns_none():  # §11.3 v1 豁免
    assert ports.rewrite_query("林晚", {"sections": []}) is None


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
