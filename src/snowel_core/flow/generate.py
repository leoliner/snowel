# src/snowel_core/flow/generate.py
import json

from ..llm.ports import get_backend, parse_llm_json
from ..retrieval.context import compose_context, scene_of_chapter
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
        scene = scene_of_chapter(conn, locate["chapter"])
        if scene is not None:
            props = json.loads(scene["props"])
            locate["query"] = " ".join(
                [scene["name"], *props.get("required_elements", [])])
    return locate


def ai_generate(api, artifact_type: str, locate: dict | None = None,
                extra: dict | None = None, backend=None,
                derive_from: list[str] | None = None) -> str:
    """三口之一（E3）：内部固定第一步 compose_context；产出必进提案队列。"""
    if artifact_type not in ARTIFACTS:
        raise ValueError(f"未知产物类型 {artifact_type}（可用：{sorted(ARTIFACTS)}）")
    if derive_from:  # TC-ON-12/§4.7：仅 Inspiration 节点可作为提炼来源（fail-fast）
        for nid in derive_from:
            row = api._conn.execute(
                "SELECT types FROM nodes WHERE id=? AND active=1",
                (nid,)).fetchone()
            if row is None or "Inspiration" not in json.loads(row["types"]):
                raise ValueError(
                    f"derive_from 必须是已有 Inspiration 节点 id: {nid}")
    extra = extra or {}
    backend = backend or _default_backend(api._conn)
    spec = ARTIFACTS[artifact_type]
    locate = _prepare_locate(api._conn, spec["strategy"], locate)
    bundle = compose_context(api._conn, spec["strategy"], locate)  # 审计自动覆盖
    prompt = "\n".join([
        spec["template"], RETURN_CONTRACT,
        "=== 上下文 ===",
        "\n".join(s["text"] for s in bundle["sections"]),
        # E1 裁决：locate 带 start_state 时注入卷首世界状态（卷级展开用）
        *([f"=== 卷首世界状态 ===\n{json.dumps(locate['start_state'], ensure_ascii=False)}"]
          if (locate or {}).get("start_state") else []),
        "=== 近期被否提案（勿重复提出） ===", rejected_digest(api._conn),
        *([f"=== 作者附言 ===\n{extra['notes']}"] if extra.get("notes") else []),
    ])
    resp = backend.generate(prompt, model=extra.get("model"))
    parsed = parse_llm_json(resp)  # T17 共享解析：容忍围栏（真实模型常裹 ```json）
    payload = {"locate": locate or {}, "draft": parsed.get("draft", ""),
               "facts": parsed.get("facts", []),
               "appeared": parsed.get("appeared", [])}
    if derive_from:  # TC-ON-12/§4.7：提炼来源透传（confirm 时建 DERIVED_FROM 边；
        # R5 重复 id 入口去重一次——重复防御只在此处，confirm/恢复不设防）
        payload["derive_from"] = list(dict.fromkeys(derive_from))
    if artifact_type == "prose":  # C1 确认链契约：补文件代写两键（纯增量，四键不动）
        payload["chapter_id"] = (locate or {}).get("chapter")
        payload["content"] = parsed.get("draft", "")
    return api.proposals.create(artifact_type, payload)


def _default_backend(conn):
    # 与 api._default_llm 同路径（ports.get_backend）：尊重配置 llm.backend
    return get_backend(conn)
