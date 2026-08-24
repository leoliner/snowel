# src/snowel_core/llm/ports.py
import sqlite3

from ..storage import config
from .backend import GenerationBackend, LitellmBackend


def rewrite_query(query: str, context: dict, backend=None) -> str | None:
    """检索改写口（E3 可选）：v1 未启用，恒 None（testcases §11.3 豁免）。"""
    return None


def get_backend(conn: sqlite3.Connection) -> GenerationBackend:
    kind = config.get(conn, "llm.backend", "litellm")
    if kind == "litellm":
        return LitellmBackend.for_conn(conn)
    raise ValueError(f"未知 llm.backend：{kind}")
