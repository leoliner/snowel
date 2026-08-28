# shell/src/snowel/cli.py
"""Snowel CLI（typer 薄壳）：本地管理动作，不做交互式创作（需求 §7.3）。"""
from __future__ import annotations

import datetime as _dt
from pathlib import Path
from typing import Annotated, Optional

import typer

from .project import ProjectError, open_project, resolve_project_path

app = typer.Typer(help="Snowel 本地管理（薄壳：只调用 snowel-core 门面）")

# click 的组级选项（callback 参数）只能出现在子命令之前；
# 为支持 `snowel init --project X`（选项在子命令之后），各命令
# 以共享别名重复声明同名选项，命令级显式值优先于回调级。
ProjectOpt = Annotated[
    Optional[Path], typer.Option(
        "--project", "-p",
        help="项目目录（默认 cwd，或环境变量 SNOWEL_PROJECT）")]

_project: Optional[Path] = None


def _resolve(explicit: Optional[Path]) -> Path:
    """命令级 --project 优先，未给时回落回调级（--project X <cmd>）。"""
    return resolve_project_path(explicit if explicit is not None else _project)


def _open_or_exit(project: Optional[Path] = None, want_write: bool = False):
    try:
        return open_project(_resolve(project),
                            want_write=want_write, heartbeat=False)
    except ProjectError as e:
        typer.secho(str(e), err=True, fg=typer.colors.RED)
        raise typer.Exit(code=1) from e


# 扩展包管理出口（addendum §3.1 裁决 6：唯一管理入口走 CLI，无 Web/MCP 面）
ext_app = typer.Typer(help="扩展包管理：list / mount / unmount / status")
app.add_typer(ext_app, name="ext")

_ORIGIN = {"project": "项目", "global": "全局", None: "孤儿"}


def _echo_warnings(warnings) -> None:
    """非致命提示走 Yellow 沿旧例；致命错误才 RED + Exit(1)。"""
    for w in warnings:
        typer.secho(f"警告：{w}", fg=typer.colors.YELLOW)


@app.callback()
def _callback(project: ProjectOpt = None) -> None:
    global _project
    _project = project


@app.command()
def init(project: ProjectOpt = None) -> None:
    """初始化 Snowel 项目（建 snowel.db 并迁移 schema）。"""
    from snowel_core.api import SnowelAPI

    p = _resolve(project)
    if (p / "snowel.db").exists():
        typer.secho(f"项目已存在：{p / 'snowel.db'}（迁移幂等）",
                    fg=typer.colors.YELLOW)
    SnowelAPI.init_project(p)
    typer.echo(f"已初始化项目：{p}")


@app.command()
def status(project: ProjectOpt = None) -> None:
    """显示项目状态：租约模式、提案队列、图谱统计。"""
    ctx = _open_or_exit(project, want_write=False)
    try:
        counts: dict[str, int] = {}
        for row in ctx.api.proposals.list():
            counts[row["status"]] = counts.get(row["status"], 0) + 1
        stats = ctx.api.graph_stats()
        mode = "只读（CLI 不抢写租约）" if ctx.readonly else "可写"
        typer.echo(f"项目：{ctx.project_path}（{mode}）")
        typer.echo("提案：" + " / ".join(
            f"{k} {counts.get(k, 0)}"
            for k in ("pending", "stale", "confirmed", "rejected", "voided")))
        typer.echo(
            f"图谱：节点 {stats['nodes']}（" + " / ".join(
                f"{t} {n}" for t, n in stats["nodes_by_type"].items())
            + f"）· 边 {stats['edges']}")
        s = ctx.api.flow_state()
        done = sum(1 for v in s["layers"].values() if v == "done")
        typer.echo(f"流程：{s['current_layer'] or '全部完成'}（{done}/7 层完成）")
    finally:
        ctx.close()


@app.command()
def backup(
    project: ProjectOpt = None,
    out: Annotated[
        Optional[Path], typer.Option(
            "--out", "-o", help="备份文件路径（默认项目目录内带时间戳）")] = None,
) -> None:
    """SQLite 一致性备份（VACUUM INTO，可恢复出等价项目库）。"""
    ctx = _open_or_exit(project, want_write=False)
    try:
        out = out or ctx.project_path / (
            f"snowel-backup-{_dt.datetime.now():%Y%m%d-%H%M%S}.db")
        try:
            ctx.api.backup(out)
        except FileExistsError as e:
            typer.secho(f"备份文件已存在，拒绝覆盖：{out}",
                        err=True, fg=typer.colors.RED)
            raise typer.Exit(code=1) from e
        typer.echo(f"已备份：{out}")
    finally:
        ctx.close()


@app.command()
def export(project: ProjectOpt = None,
           out: Annotated[Optional[Path], typer.Option(
               "--out", "-o", help="导出目录（默认项目目录下 export/）")] = None,
           fmt: Annotated[str, typer.Option(
               "--format", "-f", help="md | txt")] = "md") -> None:
    """导出全部章节正文（从库内镜像，D8）。"""
    ctx = _open_or_exit(project, want_write=False)
    try:
        out = out or ctx.project_path / "export"
        out.mkdir(parents=True, exist_ok=True)
        rows = ctx.api.export_prose()
        for r in rows:
            f = out / f"{r['chapter_id']}.{fmt}"
            f.write_text(r["prose"], encoding="utf-8")
        typer.echo(f"已导出 {len(rows)} 章至 {out}")
    finally:
        ctx.close()


@app.command()
def seal(project: ProjectOpt = None,
         volume_id: Annotated[str, typer.Argument(
             help="卷 id（Volume 节点）")] = ...) -> None:
    """封卷（C7 冻结线）：已封卷内设定改动须走显式 retcon。"""
    ctx = _open_or_exit(project, want_write=True)
    try:
        node = ctx.api.get_node(volume_id)
        try:
            ctx.api.seal(volume_id)
        except ValueError as e:
            typer.secho(str(e), err=True, fg=typer.colors.RED)
            raise typer.Exit(code=1) from e
        name = node["name"] if node else volume_id
        typer.echo(f"已封卷：{volume_id}（{name}）")
    finally:
        ctx.close()


@app.command()
def web(project: ProjectOpt = None,
        host: Annotated[str, typer.Option(
            "--host", help="监听地址（默认 127.0.0.1）")] = "127.0.0.1",
        port: Annotated[int, typer.Option(
            "--port", help="监听端口（默认 8642）")] = 8642) -> None:
    """启动 Web 创作界面（FastAPI + 项目绑定，抢写租约失败降级只读）。"""
    import uvicorn

    from snowel.web_server import create_app

    p = _resolve(project)
    if not (p / "snowel.db").exists():
        typer.secho(
            f"目录不是 Snowel 项目（未找到 {p / 'snowel.db'}）；"
            f"请先运行 snowel init，或用 --project / SNOWEL_PROJECT 指定正确目录",
            err=True, fg=typer.colors.RED)
        raise typer.Exit(code=1)
    uvicorn.run(create_app(p), host=host, port=port)


@app.command()
def mcp(project: ProjectOpt = None,
        http: Annotated[bool, typer.Option(
            "--http", help="启用 streamable HTTP 传输（默认 stdio）")] = False,
        host: Annotated[str, typer.Option(
            "--host", help="监听地址（默认 127.0.0.1）")] = "127.0.0.1",
        port: Annotated[int, typer.Option(
            "--port", help="监听端口（默认 8642）")] = 8642,
        token: Annotated[Optional[str], typer.Option(
            "--token", help="Bearer token（--http 时可选，绑 0.0.0.0/:: 必填）")] = None,
        ) -> None:
    """启动 MCP server（stdio 薄壳；--http 切 streamable HTTP，R4/TC-SH-12）。"""
    # 启动守卫（R4）：绑通配地址必须显式 token，否则拒绝启动
    if http and token is None and host in ("0.0.0.0", "::"):
        typer.secho(
            "绑定 0.0.0.0/:: 必须通过 --token 提供 Bearer token"
            "（拒绝无鉴权全网卡监听）",
            err=True, fg=typer.colors.RED)
        raise typer.Exit(code=1)
    from snowel import mcp_server

    # 项目解析交 main 内部（resolve_project_path），与 stdio 直跑语义一致
    mcp_server.main(project=_resolve(project), http=http, host=host,
                    port=port, token=token)


@ext_app.command("list")
def ext_list(project: ProjectOpt = None) -> None:
    """列出扩展包：发现全集 × 挂载态 × 项目覆盖标记（TC-EX-01 出口）。"""
    ctx = _open_or_exit(project, want_write=False)
    try:
        for e in ctx.api.list_extensions():
            state = "已挂载" if e["mounted"] else "未挂载"
            # 严格 is False 才算 stale：孤儿行 digest_matches=None（未知）
            if e["mounted"] and e["digest_matches"] is False:
                stale = "（schema 与挂载时不一致，重新挂载后生效）"
            else:
                stale = ""
            typer.echo(
                f"{e['name']}  {e['version']}  "
                f"[{_ORIGIN[e['scope']]}] {state}{stale}")
    finally:
        ctx.close()


@ext_app.command("mount")
def ext_mount(project: ProjectOpt = None,
              name: Annotated[str, typer.Argument(
                  help="扩展包名（schema.json 的 name 字段）")] = ...) -> None:
    """挂载扩展包：属性组/hook 规则即刻可用（事件化，rebuild 可重放）。"""
    ctx = _open_or_exit(project, want_write=True)
    try:
        try:
            res = ctx.api.mount_extension(name)
        except ValueError as e:
            typer.secho(str(e), err=True, fg=typer.colors.RED)
            raise typer.Exit(code=1) from e
        _echo_warnings(res.get("warnings", []))
        typer.echo(f"已挂载扩展包：{name}")
    finally:
        ctx.close()


@ext_app.command("unmount")
def ext_unmount(project: ProjectOpt = None,
                name: Annotated[str, typer.Argument(
                    help="扩展包名")] = ...) -> None:
    """卸载扩展包：活跃节点仍引用属性组时拒绝并呈现原因。"""
    ctx = _open_or_exit(project, want_write=True)
    try:
        try:
            ctx.api.unmount_extension(name)
        except ValueError as e:
            typer.secho(str(e), err=True, fg=typer.colors.RED)
            raise typer.Exit(code=1) from e
        typer.echo(f"已卸载扩展包：{name}（已有数据保留，组字段降级 unmanaged）")
    finally:
        ctx.close()


@ext_app.command("status")
def ext_status(project: ProjectOpt = None) -> None:
    """扩展包健康明细：逐包正常/异常标注 + 启动重载警告回顾。"""
    ctx = _open_or_exit(project, want_write=False)
    try:
        rows = ctx.api.extensions_status()
        if not rows:
            typer.echo("未发现任何扩展包")
        for r in rows:
            health = "正常" if r["healthy"] else "异常"
            mounted = "" if r["mounted"] else "（未挂载）"
            typer.echo(f"{r['name']}  {r['version']}  "
                       f"[{_ORIGIN[r['scope']]}] {health}{mounted}")
            if r["note"]:
                typer.echo(f"    · {r['note']}")
        _echo_warnings(ctx.api.extension_warnings)
    finally:
        ctx.close()


def main() -> None:
    app()
