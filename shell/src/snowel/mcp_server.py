# shell/src/snowel/mcp_server.py
"""Snowel MCP Server（stdio 薄壳）。

一个 server 进程绑定一个项目（C4）；六工具一比一映射 api 门面
（design §10，无编排逻辑）；未接线能力返回结构化 not_wired 响应
（用户裁决 2026-08-24：接通后工具签名不变，壳零改动）。
"""
from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from .project import ProjectContext, open_project, resolve_project_path

_NOT_WIRED_PLANNED = {
    "generate": "阶段三 生成环（llm/flow/retrieval，E3 三口）",
    "writeback": "阶段三 回写环（writeback 模块 + 正文镜像 D8）",
    "query.search": "阶段三 混合检索（FTS5 / sqlite-vec）",
    "proposal.rewrite": "生成环接线后的提案改写",
    "flow": "阶段三 flow 模块（雪花流程编排）",
}

ADVANCED_CATALOG: dict[str, dict] = {
    "rebuild": {"wired": True, "desc": "从事件日志全量重建物化图（损坏恢复）"},
    "setting_gap": {"wired": False, "planned_in": "设定库纵向轨道（flow）"},
    "mechanism_detail": {"wired": False, "planned_in": "属性组接线（挂账 L1）"},
    "foreshadow_register": {"wired": False, "planned_in": "本体语义门面（级联检查计划）"},
    "seal": {"wired": False, "planned_in": "级联检查计划（volume_sealed 事件）"},
    "retcon": {"wired": False, "planned_in": "级联检查计划（consistency 模块）"},
    "extension_packs": {"wired": False, "planned_in": "E4 目录式发现"},
    "audit": {"wired": False, "planned_in": "阶段三 retrieval_audit"},
}


def _rows(rows) -> list[dict]:
    # sqlite3.Row 无法被 FastMCP 的 pydantic 序列化（退化为 "<Row object>"），
    # 边界处统一转 dict（Row 可按列名索引，dict() 直接可用）
    return [dict(r) for r in rows]


def _not_wired(capability: str, planned_in: str | None = None) -> dict:
    return {
        "wired": False,
        "capability": capability,
        "planned_in": planned_in or _NOT_WIRED_PLANNED[capability],
        "message": "底层模块尚未实现，当前为占位响应；接通后本工具签名不变。",
    }


def build_mcp(ctx: ProjectContext) -> FastMCP:
    mcp = FastMCP("snowel")

    @mcp.tool()
    def snowel_status() -> dict:
        """项目状态：租约、待确认提案、图谱统计、流程进度。"""
        counts: dict[str, int] = {}
        for row in ctx.api.proposals.list():
            counts[row["status"]] = counts.get(row["status"], 0) + 1
        return {
            "project": str(ctx.project_path),
            "readonly": ctx.readonly,
            "lease_holder": ctx.holder,
            "proposals": counts,
            "graph": ctx.api.graph_stats(),
            "flow": _not_wired("flow"),
        }

    @mcp.tool()
    def snowel_generate(artifact_type: str,
                        locate: dict | None = None,
                        extra: dict | None = None) -> dict:
        """创作主力：按产物类型路由对应层 ai_generate（未接线）。"""
        return _not_wired("generate")

    @mcp.tool()
    def snowel_query(action: str, params: dict | None = None) -> dict:
        """图谱查询：find / node / edges / descendants / state_at；search 未接线。"""
        p = params or {}
        if action == "find":
            return {"result": _rows(ctx.api.find_nodes(name=p.get("name"),
                                                       type=p.get("type")))}
        if action == "node":
            row = ctx.api.get_node(p["node_id"])
            return {"result": dict(row) if row is not None else None}
        if action == "edges":
            return {"result": _rows(ctx.api.edges_of(
                p["node_id"], direction=p.get("direction", "both")))}
        if action == "descendants":
            return {"result": _rows(ctx.api.descendants(
                p["node_id"], kinds=p.get("kinds"),
                max_depth=p.get("max_depth", 10)))}
        if action == "state_at":
            return {"result": ctx.api.state_at(p["story_order"])}
        if action == "search":
            return _not_wired("query.search")
        raise ValueError(
            f"未知 query action：{action}"
            "（可用：find/node/edges/descendants/state_at/search）")

    @mcp.tool()
    def snowel_proposal(action: str, proposal_id: str | None = None,
                        status: str | None = None,
                        reason: str | None = None) -> dict:
        """提案队列：list / confirm / reject / void；rewrite 未接线。"""
        if action == "list":
            return {"result": _rows(ctx.api.proposals.list(status))}
        if action == "rewrite":
            return _not_wired("proposal.rewrite")
        if not proposal_id:
            raise ValueError(f"{action} 需要 proposal_id")
        ctx.require_write()
        if action == "confirm":
            seq = ctx.api.proposals.confirm(proposal_id)
            return {"confirmed": proposal_id, "event_seq": seq}
        if action == "reject":
            ctx.api.proposals.reject(proposal_id, reason)
            return {"rejected": proposal_id}
        if action == "void":
            ctx.api.proposals.void(proposal_id)
            return {"voided": proposal_id}
        raise ValueError(
            f"未知 proposal action：{action}（可用：list/confirm/reject/void/rewrite）")

    @mcp.tool()
    def snowel_writeback(action: str | None = None,
                         params: dict | None = None) -> dict:
        """回写环：手动触发抽取、查抽取结果、否决 auto 条目（未接线）。"""
        return _not_wired("writeback")

    @mcp.tool()
    def snowel_advanced(op: str | None = None) -> dict:
        """长尾入口：无参返回操作目录；已接线子操作直接路由。"""
        if op is None:
            return {"operations": ADVANCED_CATALOG}
        if op == "rebuild":
            ctx.require_write()
            ctx.api.rebuild()
            return {"rebuilt": True}
        if op in ADVANCED_CATALOG:
            return _not_wired(op, ADVANCED_CATALOG[op]["planned_in"])
        raise ValueError(f"未知 advanced op：{op}")

    return mcp


def main() -> None:
    ctx = open_project(resolve_project_path(None))  # env SNOWEL_PROJECT 或 cwd
    mcp = build_mcp(ctx)
    mcp.run("stdio")
