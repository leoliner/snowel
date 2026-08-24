# src/snowel_core/flow/generate.py
import json

from ..retrieval.context import _scene_of_chapter, compose_context
from .registry import ARTIFACTS

RETURN_CONTRACT = (
    '返回 JSON：{"draft": str, "facts": [节点/边事实数组], "appeared": [id]}')


def rejected_digest(conn, limit: int = 10) -> str:  # D7：被否提案防重复注入
    rows = conn.execute(
        "SELECT kind, payload FROM proposals WHERE status='rejected' "
        "ORDER BY created_ts DESC LIMIT ?", (limit,)).fetchall()
    if not rows:
        return "（无近期被否提案）"
    return "\n".join(
        f"- [{r['kind']}] {json.loads(r['payload']).get('draft', '')[:80]}"
        for r in rows)


def _prepare_locate(conn, strategy: str, locate: dict | None) -> dict:
    """L9：prose+chapter 定位补 query——场景卡 name+required_elements 拼接
    （chapter id 兜底不可接受）；无场景卡时沿用调用方显式 query。"""
    locate = dict(locate or {})
    if strategy == "prose" and locate.get("chapter"):
        scene = _scene_of_chapter(conn, locate["chapter"])
        if scene is not None:
            props = json.loads(scene["props"])
            locate["query"] = " ".join(
                [scene["name"], *props.get("required_elements", [])])
    return locate


def ai_generate(api, artifact_type: str, locate: dict | None = None,
                extra: dict | None = None, backend=None) -> str:
    """三口之一（E3）：内部固定第一步 compose_context；产出必进提案队列。"""
    if artifact_type not in ARTIFACTS:
        raise ValueError(f"未知产物类型 {artifact_type}（可用：{sorted(ARTIFACTS)}）")
    extra = extra or {}
    backend = backend or _default_backend(api._conn)
    spec = ARTIFACTS[artifact_type]
    locate = _prepare_locate(api._conn, spec["strategy"], locate)
    bundle = compose_context(api._conn, spec["strategy"], locate)  # 审计自动覆盖
    prompt = "\n".join([
        spec["template"], RETURN_CONTRACT,
        "=== 上下文 ===",
        "\n".join(s["text"] for s in bundle["sections"]),
        "=== 近期被否提案（勿重复提出） ===", rejected_digest(api._conn),
        *([f"=== 作者附言 ===\n{extra['notes']}"] if extra.get("notes") else []),
    ])
    resp = backend.generate(prompt, model=extra.get("model"))
    parsed = json.loads(resp)
    payload = {"locate": locate or {}, "draft": parsed.get("draft", ""),
               "facts": parsed.get("facts", []),
               "appeared": parsed.get("appeared", [])}
    if artifact_type == "prose":  # C1 确认链契约：补文件代写两键（纯增量，四键不动）
        payload["chapter_id"] = (locate or {}).get("chapter")
        payload["content"] = parsed.get("draft", "")
    return api.proposals.create(artifact_type, payload)


def _default_backend(conn):
    from ..llm.backend import LitellmBackend
    return LitellmBackend.for_conn(conn)
