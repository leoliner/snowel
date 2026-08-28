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


_REWRITE_PROMPT = """你是小说检索词改写器。把原检索词改写成更适合关键词检索的形式：\
展开代称与别名、补全同义关键词，不引入与原检索词语义无关的实体名。
只输出改写后的检索词本身，不要解释、引号或任何前后缀。

原检索词：{query}"""


def rewrite_query(conn: sqlite3.Connection, query: str, context: dict,
                  backend: GenerationBackend | None = None) -> str | None:
    """检索改写口（E3/TC-RT-07）：LLM 把检索词改写为更适合召回的形式。

    返回值三态（调用方据此决定是否落改写审计）：
    - 非 None 且 != query：改写生效，以返回词检索并记改写明细；
    - == query：无有效改写（开关关，或模型原样回显）——零审计；
    - None：已尝试但失败（任何异常/超时/空产出）——回落原词并记
      rewrite_failed。
    开关关时在解析 backend 之前早退（检索热路径零 LLM 调用）。
    """
    if not config.get(conn, "retrieval.rewrite", True):
        return query
    try:
        b = backend if backend is not None else get_backend(conn)
        out = (b.generate(
            _REWRITE_PROMPT.format(query=query),
            model=config.get(conn, "retrieval.rewrite_model") or None)
            or "").strip()
    except Exception:  # 失败回落是特性而非缺陷：调用方以 None 识别并落标记
        return None
    return out or None


def get_backend(conn: sqlite3.Connection) -> GenerationBackend:
    kind = config.get(conn, "llm.backend", "litellm")
    if kind == "litellm":
        return LitellmBackend.for_conn(conn)
    raise ValueError(f"未知 llm.backend：{kind}")
