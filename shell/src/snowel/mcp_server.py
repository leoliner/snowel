# shell/src/snowel/mcp_server.py
"""Snowel MCP Server（stdio 薄壳）。

一个 server 进程绑定一个项目（C4）；六工具一比一映射 api 门面
（design §10，无编排逻辑）；未接线能力返回结构化 not_wired 响应
（用户裁决 2026-08-24：接通后工具签名不变，壳零改动）。
"""
from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from .project import (ProjectContext, ProjectError, open_project,
                      resolve_project_path)

_NOT_WIRED_PLANNED: dict[str, str] = {}  # 阶段三接线完毕；新能力先登记再实现

ADVANCED_CATALOG: dict[str, dict] = {
    "rebuild": {"wired": True, "desc": "从事件日志全量重建物化图（损坏恢复）"},
    "setting_gap": {"wired": False, "planned_in": "设定库纵向轨道（flow）"},
    "mechanism_detail": {"wired": False, "planned_in": "属性组接线（挂账 L1）"},
    "foreshadow_register": {"wired": False, "planned_in": "本体语义门面（级联检查计划）"},
    "seal": {"wired": False, "planned_in": "级联检查计划（volume_sealed 事件）"},
    "retcon": {"wired": False, "planned_in": "级联检查计划（consistency 模块）"},
    "extension_packs": {"wired": False, "planned_in": "E4 目录式发现"},
    "audit": {"wired": True, "desc": "最近 N 条检索上下文审计（retrieval_audit）"},
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


def build_mcp(ctx: ProjectContext, backend=None) -> FastMCP:
    """backend 为测试注入点（生产缺省在 core 侧解析为配置驱动 LLM）。"""
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
            "lease_holder": ctx.holder or ctx.api.current_lease_holder(),
            "proposals": counts,
            "graph": ctx.api.graph_stats(),
            "flow": ctx.api.flow_state(),
        }

    @mcp.tool()
    def snowel_generate(artifact_type: str,
                        locate: dict | None = None,
                        extra: dict | None = None) -> dict:
        """创作主力：按产物类型路由对应层 ai_generate（产出必进提案队列）。"""
        ctx.require_write()
        pid = ctx.api.ai_generate(artifact_type, locate, extra, backend=backend)
        return {"proposal_id": pid}

    @mcp.tool()
    def snowel_query(action: str, params: dict | None = None) -> dict:
        """图谱查询：find / node / edges / descendants / state_at / search。"""
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
            return {"result": ctx.api.search(p["q"],
                                             mode=p.get("mode", "hybrid"))}
        raise ValueError(
            f"未知 query action：{action}"
            "（可用：find/node/edges/descendants/state_at/search）")

    @mcp.tool()
    def snowel_proposal(action: str, proposal_id: str | None = None,
                        status: str | None = None,
                        reason: str | None = None) -> dict:
        """提案队列：list / confirm / reject / void / rewrite（改写指示经 reason 传）。"""
        if action == "list":
            return {"result": _rows(ctx.api.proposals.list(status))}
        if action == "rewrite":
            if not proposal_id:
                raise ValueError("rewrite 需要 proposal_id")
            ctx.require_write()
            new_pid = ctx.api.rewrite_proposal(
                proposal_id, reason or "", backend)
            return {"proposal_id": new_pid, "rewritten_from": proposal_id}
        if not proposal_id:
            raise ValueError(f"{action} 需要 proposal_id")
        ctx.require_write()
        if action == "confirm":
            seq = ctx.api.confirm(proposal_id)  # 统一编排（C1 代写/revision 物化）
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
        """回写环：trigger / result / list_auto / reject_auto / reconcile / re-register。"""
        p = params or {}
        if action == "trigger":
            ctx.require_write()
            return {"result": ctx.api.trigger_extract(
                p["chapter_id"], backend=backend, model=p.get("model"))}
        if action == "result":
            out = {"deviation": ctx.api.deviation(p["chapter_id"])}
            extracts = [r for r in ctx.api.proposals.list()
                        if r["kind"] == "extract_facts"]
            if extracts:
                out["proposal"] = dict(extracts[-1])  # 最近一次抽取提案
            return {"result": out}
        if action == "list_auto":
            return {"result": ctx.api.list_auto()}
        if action == "reject_auto":
            ctx.require_write()
            entries = [(e["target"], e["target_id"])
                       for e in p.get("entries", [])]
            return {"result": ctx.api.reject_auto(entries,
                                                  reason=p.get("reason"))}
        if action == "reconcile":
            ctx.require_write()  # 对账会写事件+镜像（F2：readonly 不得写库）
            return {"result": ctx.api.reconcile_prose()}
        if action == "re-register":  # L6：崩溃窗口恢复（重放已确认 prose 提案）
            ctx.require_write()
            return {"re_registered": ctx.api.reregister_prose(p["proposal_id"])}
        raise ValueError(
            f"未知 writeback action：{action}"
            "（可用：trigger/result/list_auto/reject_auto/reconcile/re-register）")

    @mcp.tool()
    def snowel_advanced(op: str | None = None) -> dict:
        """长尾入口：无参返回操作目录；已接线子操作直接路由。"""
        if op is None:
            return {"operations": ADVANCED_CATALOG}
        if op == "rebuild":
            ctx.require_write()
            ctx.api.rebuild()
            return {"rebuilt": True}
        if op == "audit":
            return {"result": ctx.api.audit_recent()}
        if op in ADVANCED_CATALOG:
            return _not_wired(op, ADVANCED_CATALOG[op]["planned_in"])
        raise ValueError(f"未知 advanced op：{op}")

    return mcp


def main() -> None:
    try:
        ctx = open_project(resolve_project_path(None))  # env SNOWEL_PROJECT 或 cwd
    except ProjectError as e:
        import sys
        print(f"snowel-mcp 启动失败：{e}", file=sys.stderr)
        raise SystemExit(1) from e
    try:
        mcp = build_mcp(ctx)
        mcp.run("stdio")
    finally:
        ctx.close()  # 释放写租约并停止心跳，避免他端等 stale_after 过期
