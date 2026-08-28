# shell/src/snowel/mcp_server.py
"""Snowel MCP Server（stdio 薄壳）。

一个 server 进程绑定一个项目（C4）；六工具一比一映射 api 门面
（design §10，无编排逻辑）；未接线能力返回结构化 not_wired 响应
（用户裁决 2026-08-24：接通后工具签名不变，壳零改动）。
"""
from __future__ import annotations

import secrets

from mcp.server.auth.provider import AccessToken
from mcp.server.auth.settings import AuthSettings
from mcp.server.fastmcp import FastMCP

from .project import (ProjectContext, ProjectError, open_project,
                      resolve_project_path)

_NOT_WIRED_PLANNED: dict[str, str] = {}  # 阶段三接线完毕；新能力先登记再实现


class StaticTokenVerifier:
    """静态 Bearer token 校验（R3，单用户本地/局域网场景）。

    compare_digest 按字节比较：str 形态要求 ASCII，畸形 Authorization 头
    （非 ASCII，真实客户端可发原始字节）会 TypeError 穿透成 500——编码后
    比较使畸形输入正常走 401；scopes 恒空（SDK 必填字段，未做细粒度授权）。"""

    def __init__(self, token: str) -> None:
        self._token = token

    async def verify_token(self, token: str) -> AccessToken | None:
        if secrets.compare_digest(token.encode("utf-8"),
                                  self._token.encode("utf-8")):
            return AccessToken(token=token, client_id="snowel-mcp", scopes=[])
        return None

ADVANCED_CATALOG: dict[str, dict] = {
    "rebuild": {"wired": True, "desc": "从事件日志全量重建物化图（损坏恢复）"},
    "setting_gap": {"wired": False, "planned_in": "设定库纵向轨道（flow）"},
    "mechanism_detail": {"wired": False, "planned_in": "属性组接线（挂账 L1）"},
    "foreshadow_register": {"wired": True, "via": "snowel_writeback",
                            "desc": "伏笔注册（§4.8 author 通道，foreshadow action）"},
    "seal": {"wired": True, "via": "snowel_writeback",
             "desc": "封卷（C7 冻结线，seal action）"},
    "retcon": {"wired": True, "via": "snowel_writeback",
               "desc": "显式 retcon（C7 合法通道，retcon action）"},
    "inspiration_save": {"wired": True,
                         "desc": "保存灵感原话（api.save_inspiration）",
                         "params": {"text": "灵感原话全文，空/纯空白拒绝"}},
    "inspiration_list": {"wired": True,
                         "desc": "灵感列表（api.inspirations，只读）"},
    "beat_merge": {"wired": True,
                   "desc": "合并两拍，伏笔引用与边有效期随迁（api.merge_beats）",
                   "params": {"source": "源拍 id", "target": "承接拍 id"}},
    "beat_delete": {"wired": True,
                    "desc": "删除拍，被伏笔引用则拒绝（api.delete_beat）",
                    "params": {"beat_id": "拍 id", "reason": "可选删除原因"}},
    "extension_packs": {"wired": False,
                        "planned_in": "仅 CLI 管理（snowel ext）；"
                                      "不做 Web/MCP 面（裁决 6）"},
    "audit": {"wired": True, "desc": "最近 N 条检索上下文审计（retrieval_audit）"},
}


def _rows(rows) -> list[dict]:
    # sqlite3.Row 无法被 FastMCP 的 pydantic 序列化（退化为 "<Row object>"），
    # 边界处统一转 dict（Row 可按列名索引，dict() 直接可用）
    return [dict(r) for r in rows]


def _require_params(p: dict, keys: list[str]) -> None:
    """带参 op 分派前守卫：缺失/空值键 → ValueError 中文文案（SH-②，
    与 Web `_require` 400 语义对齐；直取 p[key] 会 KeyError 机翻）。"""
    missing = [k for k in keys if not p.get(k)]
    if missing:
        raise ValueError("参数缺失：" + "、".join(missing))


def _not_wired(capability: str, planned_in: str | None = None) -> dict:
    return {
        "wired": False,
        "capability": capability,
        "planned_in": planned_in or _NOT_WIRED_PLANNED[capability],
        "message": "底层模块尚未实现，当前为占位响应；接通后本工具签名不变。",
    }


def build_mcp(ctx: ProjectContext, backend=None, host: str = "127.0.0.1",
              port: int = 8642, token_verifier=None) -> FastMCP:
    """backend 为测试注入点（生产缺省在 core 侧解析为配置驱动 LLM）。

    host/port/token_verifier 仅 streamable HTTP 消费（stdio 不读），
    默认值保持既有调用形状零变化。"""
    # mcp 1.29.0 构造期强校验：token_verifier 必须伴随 auth 设置；纯资源
    # 服务器不做 OAuth 签发，issuer 仅占位，bearer 路径只消费 token_verifier。
    # resource_server_url 进 WWW-Authenticate/受保护资源元数据，IPv6 形态
    # host（含 ":"，如通配 "::"）必须方括号——裸拼接 "http://:::8642" 构造即崩
    base = (f"http://[{host}]:{port}" if ":" in host
            else f"http://{host}:{port}")
    auth = (AuthSettings(issuer_url="http://localhost",
                         resource_server_url=base)
            if token_verifier is not None else None)
    mcp = FastMCP("snowel", host=host, port=port,
                  token_verifier=token_verifier, auth=auth)

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
                        extra: dict | None = None,
                        derive_from: list[str] | None = None) -> dict:
        """创作主力：按产物类型路由对应层 ai_generate（产出必进提案队列）。"""
        ctx.require_write()
        # derive_from 仅显式为 list 才透传门面（与 Web /api/generate 同款条件；
        # 缺席调用形状逐参不变）；空列表由 core truthy-gate 挡下，不进载荷
        kw = ({"derive_from": derive_from}
              if isinstance(derive_from, list) else {})
        pid = ctx.api.ai_generate(artifact_type, locate, extra, backend=backend,
                                  **kw)
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
            # retcon 有专属确认流程（core 通用 confirm 对 retcon 显式拒绝），
            # 壳读一次 kind 分派（proposal_kind 只读门面，仍零领域逻辑）
            if ctx.api.proposal_kind(proposal_id) == "retcon":
                seq = ctx.api.confirm_retcon(proposal_id)
            else:
                seq = ctx.api.confirm(proposal_id)
            return {"confirmed": proposal_id, "event_seq": seq,
                    "cascade": ctx.api.last_cascade()}
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
        """回写环与一致性动作：trigger / result / list_auto / reject_auto /
        reconcile / re-register / seal / retcon / foreshadow。"""
        p = params or {}
        if action == "trigger":
            ctx.require_write()
            return {"result": ctx.api.trigger_extract(
                p["chapter_id"], backend=backend, model=p.get("model"))}
        if action == "result":
            out = {"deviation": ctx.api.deviation(p["chapter_id"])}
            latest = ctx.api.latest_extract_proposal()
            if latest is not None:
                out["proposal"] = latest  # 最近一次抽取提案（core 门面取最新）
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
        if action == "seal":  # 封卷（C7 冻结线）：设定改动走显式 retcon
            ctx.require_write()
            ctx.api.seal(p["volume_id"])
            return {"sealed": p["volume_id"]}
        if action == "retcon":  # 显式 retcon 提案（propose 全量级联），确认走 snowel_proposal
            ctx.require_write()
            return ctx.api.propose_retcon(
                facts=p.get("facts"), renames=p.get("renames"),
                track_updates=p.get("track_updates"), reason=p.get("reason", ""))
        if action == "foreshadow":  # 伏笔注册（§4.8 author 通道），确认走 snowel_proposal
            ctx.require_write()
            return {"proposal_id": ctx.api.register_foreshadow(
                p["name"], p["planted_at"], origin=p.get("origin", "author"),
                payoff_beat=p.get("payoff_beat"), note=p.get("note", ""))}
        raise ValueError(
            f"未知 writeback action：{action}"
            "（可用：trigger/result/list_auto/reject_auto/reconcile/re-register"
            "/seal/retcon/foreshadow）")

    @mcp.tool()
    def snowel_advanced(op: str | None = None,
                        params: dict | None = None) -> dict:
        """长尾入口：无参返回操作目录；已接线子操作经 params 传参直接路由。"""
        p = params or {}
        if op is None:
            return {"operations": ADVANCED_CATALOG}
        if op == "rebuild":
            ctx.require_write()
            ctx.api.rebuild()
            return {"rebuilt": True}
        if op == "audit":
            return {"result": ctx.api.audit_recent()}
        if op == "inspiration_save":
            _require_params(p, ["text"])
            ctx.require_write()
            return {"wired": True,
                    "inspiration_id": ctx.api.save_inspiration(p["text"])}
        if op == "inspiration_list":
            return {"wired": True, "result": ctx.api.inspirations()}
        if op == "beat_merge":
            _require_params(p, ["source", "target"])
            ctx.require_write()
            return {"wired": True,
                    "event_seq": ctx.api.merge_beats(p["source"],
                                                     p["target"])}
        if op == "beat_delete":
            _require_params(p, ["beat_id"])
            ctx.require_write()
            return {"wired": True,
                    "event_seq": ctx.api.delete_beat(p["beat_id"],
                                                     reason=p.get("reason"))}
        if op in ADVANCED_CATALOG:
            entry = ADVANCED_CATALOG[op]
            if entry.get("via"):
                return {"wired": True, "via": entry["via"],
                        "hint": "经 snowel_writeback 对应 action 调用"}
            return _not_wired(op, entry["planned_in"])
        raise ValueError(f"未知 advanced op：{op}")

    return mcp


def main(project=None, http: bool = False, host: str = "127.0.0.1",
         port: int = 8642, token: str | None = None) -> None:
    # 方括号 host 归一（RW-②）："[::1]" → "::1"，防 build_mcp 二次包裹
    # （"http://[[::1]]:8642" 构造即崩）；守卫集合匹配在 strip 后进行——
    # "[::]" 归一为 "::" 仍被通配守卫拦截，"[::1]"（loopback 非通配）放行
    host = host.strip("[]")
    # 防御性同款守卫（R4）：main 可不经 CLI 直调（如 python -m），
    # 通配地址必须持 token，与 cli 的 mcp 命令守卫保持同一集合
    if http and token is None and host in ("0.0.0.0", "::"):
        import sys
        print("snowel-mcp：绑定 0.0.0.0/:: 必须提供 token"
              "（拒绝无鉴权全网卡监听）", file=sys.stderr)
        raise SystemExit(1)
    try:
        ctx = open_project(resolve_project_path(project))  # 缺省 env SNOWEL_PROJECT 或 cwd
    except ProjectError as e:
        import sys
        print(f"snowel-mcp 启动失败：{e}", file=sys.stderr)
        raise SystemExit(1) from e
    try:
        mcp = build_mcp(ctx, host=host, port=port,
                        token_verifier=(StaticTokenVerifier(token)
                                        if token is not None else None))
        mcp.run("streamable-http" if http else "stdio")
    finally:
        ctx.close()  # 释放写租约并停止心跳，避免他端等 stale_after 过期
