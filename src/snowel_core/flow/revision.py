# src/snowel_core/flow/revision.py
import json

from ..llm.ports import parse_llm_json


def propose_revision(api, node_id: str, new_address: dict, reason: str = "") -> str:
    """统一 revision（§5.2）：提案 → （级联影响分析位）→ 确认，三层复用。"""
    return api.proposals.create("revision", {
        "node_id": node_id, "reason": reason,
        "structure_changes": [{"op": "move", "node_id": node_id,
                               "address": new_address}],
        "cascade_hint": {"wired": False, "planned_in": "级联检查计划"}})


def rewrite_proposal(api, proposal_id: str, instruction: str, backend) -> str:
    """提案改写（壳 proposal.rewrite 的 core 面）：新提案标 rewritten_from。"""
    p = api.proposals.get(proposal_id)
    payload = json.loads(p["payload"])
    resp = backend.generate(
        f"按指示改写以下草稿，返回 JSON（draft/facts/appeared）。\n"
        f"指示：{instruction}\n\n原草稿：{payload.get('draft', '')}")
    parsed = parse_llm_json(resp)  # facts/appeared 仍继承原 payload（控制器裁决）
    new_payload = {**payload, "draft": parsed.get("draft", ""),
                   "rewritten_from": proposal_id}
    if p["kind"] == "prose" and "content" in payload:
        # C1 确认链契约：确认/重登记读 payload["content"]，须随改写稿同步
        new_payload["content"] = new_payload["draft"]
    return api.proposals.create(p["kind"], new_payload)
