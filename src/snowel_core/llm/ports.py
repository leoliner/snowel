# src/snowel_core/llm/ports.py
import json
import sqlite3

from ..storage import config
from ..writeback.extract import extract_and_writeback  # 口签名住 ports（design §7），实现住 writeback
from .backend import GenerationBackend, LitellmBackend


def parse_llm_json(resp: str) -> dict:
    """容忍 Markdown 围栏的 LLM 响应解析；非法/缺键给结构化 ValueError（铁律 3）。"""
    text = resp
    if "```" in resp:  # 真实模型常裹 ```json 围栏，剥壳后再解析
        seg = resp.split("```")[1] if resp.count("```") >= 2 else resp
        first, _, rest = seg.partition("\n")
        if "{" not in first:  # 首行是语言标签行（如 json），丢弃
            seg = rest
        text = seg.strip()
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError as e:
        raise ValueError(f"LLM 响应不是合法 JSON：{e}") from e
    if "facts" not in parsed:
        raise ValueError("LLM 响应缺少 facts 键")
    return parsed


def rewrite_query(query: str, context: dict, backend=None) -> str | None:
    """检索改写口（E3 可选）：v1 未启用，恒 None（testcases §11.3 豁免）。"""
    return None


def get_backend(conn: sqlite3.Connection) -> GenerationBackend:
    kind = config.get(conn, "llm.backend", "litellm")
    if kind == "litellm":
        return LitellmBackend.for_conn(conn)
    raise ValueError(f"未知 llm.backend：{kind}")
