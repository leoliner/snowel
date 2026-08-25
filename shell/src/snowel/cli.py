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


def main() -> None:
    app()
