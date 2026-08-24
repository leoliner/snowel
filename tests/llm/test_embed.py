# tests/llm/test_embed.py
import json
import pytest
from snowel_core.storage import config
from snowel_core.storage.db import transaction
from snowel_core.llm.embed import DeterministicEmbed, get_provider


def test_config_kv_roundtrip(core_conn):
    config.set(core_conn, "embedding.provider", "deterministic")
    assert config.get(core_conn, "embedding.provider") == "deterministic"
    assert config.get(core_conn, "nope", default=42) == 42


def test_deterministic_embed_stable_and_dim():
    e = DeterministicEmbed()
    v1, v2 = e.embed(["林晚握紧了积分卡", "林晚握紧了积分卡"])
    assert v1 == v2 and len(v1) == e.dim == 64
    assert e.embed(["另一段"])[0] != v1


def test_get_provider_default_and_fastembed_missing(core_conn):
    assert isinstance(get_provider(core_conn), DeterministicEmbed)
    config.set(core_conn, "embedding.provider", "fastembed")
    with pytest.raises(ImportError, match="pip install snowel-core\\[embed\\]"):
        get_provider(core_conn)
