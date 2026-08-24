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

PLANNED_IN = {
    "export": "阶段三 回写环（章节正文镜像，D8）",
    "seal": "级联检查计划（volume_sealed 事件）",
}


def _not_wired(capability: str) -> None:
    typer.secho(
        f"未接线：{capability} 依赖尚未实现的底层能力"
        f"（{PLANNED_IN[capability]}）。",
        err=True, fg=typer.colors.YELLOW)
    raise typer.Exit(code=2)


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
        mode = "只读（另一进程持有写租约）" if ctx.readonly else "可写"
        typer.echo(f"项目：{ctx.project_path}（{mode}）")
        typer.echo("提案：" + " / ".join(
            f"{k} {counts.get(k, 0)}"
            for k in ("pending", "stale", "confirmed", "rejected", "voided")))
        typer.echo(
            f"图谱：节点 {stats['nodes']}（" + " / ".join(
                f"{t} {n}" for t, n in stats["nodes_by_type"].items())
            + f"）· 边 {stats['edges']}")
        typer.echo("流程：未接线（阶段三 flow 模块）")
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
def export(project: ProjectOpt = None) -> None:
    """导出项目（Markdown/txt）——未接线。"""
    _not_wired("export")


@app.command()
def seal(project: ProjectOpt = None) -> None:
    """封卷（冻结线）——未接线。"""
    _not_wired("seal")


def main() -> None:
    app()
