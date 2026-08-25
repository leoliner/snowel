# shell/src/snowel/web_server.py
"""Snowel Web 壳（W2/W5）：FastAPI app 工厂 + 项目绑定 + 租约会话 + 静态 serve。

每 server 进程绑定一个项目（C4/TC-SH-06）；启动抢写租约 `web:<pid>`（C10，
W5），失败降级只读会话（/api/session 暴露 readonly/holder，写端点统一 409）。
只转发 api 门面，零领域逻辑（design §10）。

open + acquire 在工厂内同步完成：httpx ASGITransport 不发送 lifespan 消息
（测试锚定的是工厂后的状态），uvicorn 生产路径经 lifespan shutdown 释放
租约并关闭连接；测试中资源随 app 对象 GC 自动释放。
"""
from __future__ import annotations

import json
import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import Depends, FastAPI, Request
from fastapi.staticfiles import StaticFiles
# 用 starlette 基类而非 fastapi 子类：StaticFiles 抛的是基类，
# 以子类捕获（except fastapi.HTTPException）会漏接
from starlette.exceptions import HTTPException
from starlette.responses import JSONResponse, Response
from starlette.types import Scope

from snowel_core.api import SnowelAPI
from snowel_core.consistency.seal import SealedVolumeError
from snowel_core.proposal.queue import ProposalStateError

_REPO_ROOT = Path(__file__).resolve().parents[3]  # 源码布局：shell/src/snowel/ -> 仓库根
_DEFAULT_DIST = _REPO_ROOT / "web" / "dist"


class _SpaStaticFiles(StaticFiles):
    """SPA 静态服务：未命中文件时回落 index.html（/api 路径除外）。"""

    async def get_response(self, path: str, scope: Scope) -> Response:
        try:
            return await super().get_response(path, scope)
        except HTTPException as exc:
            if exc.status_code == 404 and not scope["path"].startswith("/api"):
                return await super().get_response("index.html", scope)
            raise


def _require_write(request: Request) -> None:
    """写端点统一守卫：只查 app.state 布尔（零领域逻辑），只读会话 → 409。"""
    if request.app.state.readonly:
        raise HTTPException(
            status_code=409,
            detail=f"只读会话：写租约由 {request.app.state.holder} 持有")


def _rows(rows) -> list[dict]:
    # sqlite3.Row 无法被 JSON 序列化，边界处统一转 dict（与 mcp_server 同款模式）
    return [dict(r) for r in rows]


def _proposal(api: SnowelAPI, pid: str) -> dict:
    """提案行 + 解析后的 payload（404 统一：pid 不存在抛 HTTPException）。"""
    row = api.proposals.get(pid)
    if row is None:
        raise HTTPException(status_code=404, detail=f"提案 {pid} 不存在")
    return {**dict(row), "payload": json.loads(row["payload"])}


def _require(body: dict | None, key: str):
    """请求体必填字段守卫：缺失/空值 → 400（统一 ValueError 映射）。"""
    val = (body or {}).get(key)
    if not val:
        raise ValueError(f"{key} 必填")
    return val


def create_app(project_root: str | Path,
               static_dir: str | Path | None = None,
               llm_backend=None) -> FastAPI:
    """app 工厂：绑定项目、抢写租约，挂 app.state；web/dist 存在则挂 /。

    static_dir 缺省取 <仓库根>/web/dist（源码布局解析），缺失则跳过挂载
    （无 node 环境测试不破）。llm_backend 为测试注入点（FakeBackend），
    缺省 None → 写端点透传给 core，由其按配置解析默认 backend。
    """
    root = Path(project_root)
    api = SnowelAPI.open(root)
    holder = f"web:{os.getpid()}"
    got = api.acquire_lease(holder)
    app = FastAPI(title="Snowel", lifespan=_lifespan)
    app.state.project_root = root
    app.state.api = api
    app.state.readonly = not got
    app.state.holder = None if got else api.current_lease_holder()
    app.state._lease_holder = holder if got else None  # shutdown 定向释放
    app.state.llm_backend = llm_backend

    # ---- 统一错误映射（Task 6，全写端点共用）：core 校验错误 → 400，
    # 队列状态机错误 → 409；missing pid 由 _proposal 统一 404
    @app.exception_handler(ValueError)
    async def _value_error(request: Request, exc: ValueError) -> JSONResponse:
        return JSONResponse(status_code=400, content={"detail": str(exc)})

    @app.exception_handler(SealedVolumeError)
    async def _sealed_error(request: Request,
                            exc: SealedVolumeError) -> JSONResponse:
        return JSONResponse(status_code=400, content={"detail": str(exc)})

    @app.exception_handler(ProposalStateError)
    async def _state_error(request: Request,
                           exc: ProposalStateError) -> JSONResponse:
        return JSONResponse(status_code=409, content={"detail": str(exc)})

    @app.get("/api/session")
    async def session(request: Request) -> dict:
        # 必须 async：api 连接创建于事件循环线程（create_app 所在线程），
        # sync def 会进线程池执行，跨线程用 sqlite 直接报错
        return {
            "project": request.app.state.project_root.name,
            "readonly": request.app.state.readonly,
            "holder": request.app.state.holder,
            "flow": request.app.state.api.flow_state(),
        }

    @app.get("/api/health")
    async def health() -> dict:
        return {"ok": True}

    # ---- 写 API 面（Task 6）：全部 POST，统一过写守卫（readonly → 409）。
    # db 触碰端点一律 async def（sync def 进线程池 → 跨线程用 sqlite 崩溃，T4 实证）；
    # 错误映射见工厂头部三个 exception_handler，pid 缺失统一 404（_proposal 预检）。
    @app.post("/api/proposals/{pid}/confirm",
              dependencies=[Depends(_require_write)])
    async def confirm(request: Request, pid: str) -> dict[str, Any]:
        """确认提案：返回事件 seq + 最近级联结果（E5 接线面）。

        壳零分派：retcon 提案经 kind 由前端预路由到 confirm_retcon 端点；
        错配时 core 抛 ValueError → 400（含提示消息）。
        """
        api = request.app.state.api
        _proposal(api, pid)  # 404 预检（core 对缺失 pid 是 TypeError，不可映射）
        seq = api.confirm(pid)
        return {"seq": seq, "cascade": api.last_cascade()}

    @app.post("/api/proposals/{pid}/confirm_retcon",
              dependencies=[Depends(_require_write)])
    async def confirm_retcon(request: Request, pid: str) -> dict[str, Any]:
        """retcon 专属确认（冻结线豁免）：响应形态与 confirm 同（seq + cascade）。"""
        api = request.app.state.api
        _proposal(api, pid)
        seq = api.confirm_retcon(pid)
        return {"seq": seq, "cascade": api.last_cascade()}

    @app.post("/api/proposals/{pid}/reject",
              dependencies=[Depends(_require_write)])
    async def reject(request: Request, pid: str,
                     body: dict | None = None) -> dict[str, Any]:
        """否决提案；reason 可选（历史留痕）。"""
        api = request.app.state.api
        _proposal(api, pid)
        api.proposals.reject(pid, (body or {}).get("reason"))
        return {"ok": True}

    @app.post("/api/proposals/{pid}/rewrite",
              dependencies=[Depends(_require_write)])
    async def rewrite(request: Request, pid: str,
                      body: dict | None = None) -> dict[str, Any]:
        """提案改写：按指令产新提案（标 rewritten_from），原提案留队不动。"""
        api = request.app.state.api
        _proposal(api, pid)
        instruction = _require(body, "instruction")
        new_pid = api.rewrite_proposal(
            pid, instruction, backend=request.app.state.llm_backend or None)
        return {"proposal_id": new_pid}

    @app.post("/api/generate", dependencies=[Depends(_require_write)])
    async def generate(request: Request,
                       body: dict | None = None) -> dict[str, Any]:
        """生成环：按产物类型产出提案（产出必进队列，不直接回生成文本）。"""
        api = request.app.state.api
        artifact_type = _require(body, "artifact_type")
        pid = api.ai_generate(artifact_type,
                              locate=(body or {}).get("locate"),
                              extra=(body or {}).get("extra"),
                              backend=request.app.state.llm_backend or None)
        return {"proposal_id": pid}

    @app.post("/api/expand/chapter", dependencies=[Depends(_require_write)])
    async def expand_chapter(request: Request,
                             body: dict | None = None) -> dict[str, Any]:
        """小雪花章级展开：按序产三提案（意图→微节拍组→正文），不自动确认。"""
        api = request.app.state.api
        chapter_id = _require(body, "chapter_id")
        pids = api.expand_chapter(chapter_id,
                                  request.app.state.llm_backend or None,
                                  extra=(body or {}).get("extra"))
        return {"proposal_ids": pids}

    @app.post("/api/expand/volume", dependencies=[Depends(_require_write)])
    async def expand_volume(request: Request,
                            body: dict | None = None) -> dict[str, Any]:
        """卷级展开：主题→三幕两提案（locate 携带卷首世界状态，不自动确认）。"""
        api = request.app.state.api
        volume_id = _require(body, "volume_id")
        pids = api.expand_volume(volume_id,
                                 request.app.state.llm_backend or None,
                                 extra=(body or {}).get("extra"))
        return {"proposal_ids": pids}

    @app.post("/api/seal", dependencies=[Depends(_require_write)])
    async def seal(request: Request, body: dict | None = None) -> dict[str, Any]:
        """封卷（C7 冻结线）：重复封卷 → 400 带"已封"（ValueError 映射）。"""
        api = request.app.state.api
        volume_id = _require(body, "volume_id")
        api.seal(volume_id)
        return {"sealed": volume_id}

    @app.post("/api/retcon", dependencies=[Depends(_require_write)])
    async def retcon(request: Request,
                     body: dict | None = None) -> dict[str, Any]:
        """显式 retcon（冻结线合法通道）：建提案 + 影响清单（propose 即跑全量级联）。"""
        api = request.app.state.api
        return api.propose_retcon(
            facts=(body or {}).get("facts"),
            renames=(body or {}).get("renames"),
            track_updates=(body or {}).get("track_updates"),
            reason=_require(body, "reason"))

    @app.post("/api/foreshadow", dependencies=[Depends(_require_write)])
    async def foreshadow(request: Request,
                         body: dict | None = None) -> dict[str, Any]:
        """伏笔注册（author 通道）：建 kind=foreshadow 提案，确认走 confirm。"""
        api = request.app.state.api
        pid = api.register_foreshadow(
            _require(body, "name"), _require(body, "planted_at"),
            origin=(body or {}).get("origin", "author"),
            payoff_beat=(body or {}).get("payoff_beat"),
            note=(body or {}).get("note", ""))
        return {"proposal_id": pid}

    @app.post("/api/writeback/extract", dependencies=[Depends(_require_write)])
    async def writeback_extract(request: Request,
                                body: dict | None = None) -> dict[str, Any]:
        """抽取回写（铁律 1 唯一入口）：完整 extract 返回（含 cascade 键）。"""
        api = request.app.state.api
        return api.trigger_extract(
            _require(body, "chapter_id"),
            backend=request.app.state.llm_backend or None)

    @app.post("/api/writeback/reject_auto",
              dependencies=[Depends(_require_write)])
    async def writeback_reject_auto(request: Request,
                                    body: dict | None = None) -> dict[str, Any]:
        """auto 条目事后否决（C11，不受冻结线）：entries=[[target, id], ...]。"""
        api = request.app.state.api
        entries = [(e[0], e[1]) for e in _require(body, "entries")]
        return api.reject_auto(entries, reason=(body or {}).get("reason"))

    @app.post("/api/writeback/reregister",
              dependencies=[Depends(_require_write)])
    async def writeback_reregister(request: Request,
                                   body: dict | None = None) -> dict[str, Any]:
        """崩溃窗口恢复：重放已确认 prose 提案的"确认即代写"（L6）。"""
        api = request.app.state.api
        chapter_id = api.reregister_prose(_require(body, "proposal_id"))
        return {"chapter_id": chapter_id}

    @app.post("/api/revision", dependencies=[Depends(_require_write)])
    async def revision(request: Request,
                       body: dict | None = None) -> dict[str, Any]:
        """统一 revision（§5.2）：结构变更提案，确认后二段物化。"""
        api = request.app.state.api
        pid = api.propose_revision(_require(body, "node_id"),
                                   _require(body, "new_address"),
                                   reason=(body or {}).get("reason", ""))
        return {"proposal_id": pid}

    # ---- 只读 API 面（Task 5）：全部 GET，一比一转发 api 门面，pid 缺失统一 404。
    # 只读降级读不限（TC-SH-04）——不挂写守卫；db 触碰端点一律 async def
    # （sync def 进线程池 → 跨线程用 sqlite 崩溃，T4 实证）。
    @app.get("/api/flow")
    async def flow(request: Request) -> dict:
        """流程树（雪花流程状态，含卷/章树）。"""
        return request.app.state.api.flow_state()

    @app.get("/api/proposals")
    async def proposals(request: Request,
                        status: str | None = None) -> list[dict]:
        """提案队列列表；status 可选，缺省全量（status 过滤在 core 侧）。"""
        return _rows(request.app.state.api.proposals.list(status))

    @app.get("/api/proposals/{pid}")
    async def proposal_detail(request: Request, pid: str) -> dict:
        """提案详情：payload 解析为对象；kind 字段供前端分派确认入口
        （retcon 提案确认按钮路由到 confirm_retcon 端点，壳零分派）。"""
        return _proposal(request.app.state.api, pid)

    @app.get("/api/proposals/{pid}/cascade_preview")
    async def cascade_preview(request: Request, pid: str) -> dict:
        """级联只读预演：按提案 payload.facts 跑档返回 violations + diff
        预览，不入队任何提案。"""
        api = request.app.state.api
        payload = _proposal(api, pid)["payload"]
        return api.cascade_check(payload.get("facts", []))

    @app.get("/api/search")
    async def search(request: Request,
                     q: str,
                     kind: str | None = None) -> dict:
        """混合检索（FTS5+jieba + sqlite-vec）；kind 为前端保留位
        （门面暂不支持，优雅忽略）。"""
        return request.app.state.api.search(q)

    @app.get("/api/nodes/{node_id}")
    async def node_detail(request: Request, node_id: str) -> dict:
        """节点详情 + 关联边（row → dict，JSON 序列化边界）。"""
        api = request.app.state.api
        row = api.get_node(node_id)
        return {"node": dict(row) if row is not None else None,
                "edges": _rows(api.edges_of(node_id))}

    @app.get("/api/state")
    async def state(request: Request, at: int) -> dict:
        """按叙事时间点投影当前生效集（D1 修正后视角）。"""
        return request.app.state.api.state_at(at)

    @app.get("/api/audit")
    async def audit(request: Request) -> list[dict]:
        """最近检索上下文审计。"""
        return request.app.state.api.audit_recent()

    @app.get("/api/writeback/auto")
    async def auto_list(request: Request) -> list[dict]:
        """自动抽取队列（待人工裁决项）。"""
        return request.app.state.api.list_auto()

    @app.get("/api/writeback/deviation/{chapter_id}")
    async def deviation(request: Request, chapter_id: str) -> dict:
        """指定章的抽取偏离报告。"""
        return request.app.state.api.deviation(chapter_id)

    @app.get("/api/reconcile")
    async def reconcile(request: Request) -> list[dict]:
        """正文镜像对账状态（changed/missing 清单，dry-run：纯状态读不写库，
        只读会话照常可查——F2）。"""
        return request.app.state.api.reconcile_prose(dry_run=True)

    @app.get("/api/sealed")
    async def sealed(request: Request) -> list[dict]:
        """已封卷列表（冻结线警告面）。"""
        return request.app.state.api.sealed_volumes()

    dist = Path(static_dir) if static_dir is not None else _DEFAULT_DIST
    if dist.is_dir():
        app.mount("/", _SpaStaticFiles(directory=dist, html=True), name="static")
    return app


@asynccontextmanager
async def _lifespan(app: FastAPI):
    try:
        yield
    finally:
        # uvicorn 退出路径：释放租约（仅写会话）并关闭连接；测试中 app 被 GC 时
        # sqlite 连接随之关闭，无需在此兜底
        api = getattr(app.state, "api", None)
        if api is not None:
            if app.state._lease_holder:
                api.release_lease(app.state._lease_holder)
            api.close()
