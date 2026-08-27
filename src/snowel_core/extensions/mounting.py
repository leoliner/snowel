# src/snowel_core/extensions/mounting.py
"""扩展包挂载/卸载事件闭环与启动重载（addendum §3.1，R3/R4/R5）。

发现层（discovery）只读不注册；本模块把挂载做成事件溯源闭环：
单事务 append + 投影 → 进程态 groups/engine 注册。领域编排全部在此，
api.py 只留薄门面。
"""
import hashlib
import importlib.util
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Annotated, Literal, Optional

from pydantic import BaseModel, StringConstraints, create_model

from ..consistency import engine
from ..ontology import groups
from ..storage import db, events, projector
from . import discovery
from .discovery import PackManifest, discover, parse_manifest

# R1 映射表（与 discovery._SCALAR_TYPES 同口径）：JSON Schema 类型 → Python 注解
_SPEC_TO_PY = {"string": str, "integer": int, "number": float, "boolean": bool}


def _annotation(spec: dict):
    """单个属性片段 → 类型注解；越映射表返 None（discover 已发跳过警告）。"""
    t = spec.get("type")
    if t == "string":
        # enum 约束优先于 pattern（两者同现时 Literal 已含取值收敛语义）
        if isinstance(spec.get("enum"), list) and spec["enum"]:
            return Literal[tuple(spec["enum"])]
        if "pattern" in spec:
            return Annotated[str, StringConstraints(pattern=spec["pattern"])]
        return str
    if t == "array" and isinstance(spec.get("items"), dict) \
            and spec["items"].get("type") == "string":
        return list[str]
    return _SPEC_TO_PY.get(t)


def build_group_models(manifest: PackManifest) -> dict[str, type[BaseModel]]:
    """manifest.raw["groups"] 的 JSON Schema 片段 → pydantic 模型：
    required 内字段必填、required 外全 Optional default None。"""
    out: dict[str, type[BaseModel]] = {}
    for gname, fragment in manifest.raw["groups"].items():
        fields = {}
        required = set(fragment.get("required", []))
        for fname, spec in fragment.get("properties", {}).items():
            ann = _annotation(spec if isinstance(spec, dict) else {})
            if ann is None:
                continue  # 越映射表字段：parse 阶段已发"后续构组将跳过"警告
            fields[fname] = ((ann, ...) if fname in required
                             else (Optional[ann], None))
        out[gname] = create_model(gname, **fields)
    return out


class Registry:
    """hooks 注册面（R2 / design §8）：v1.0.0 只暴露 rule()——载荷上限
    裁决（属性组+级联规则两类）。rule() 只暂存不直接进引擎：register()
    全程无副作用跑完后由 _activate_hooks 统一提交，任一条中途炸不产生
    半注册。entries 暴露已存清单，供包级回滚逐名撤销。"""

    def __init__(self) -> None:
        self.entries: list[tuple[str, Callable, tuple]] = []

    def rule(self, name, fn, tiers=("full",)) -> None:
        self.entries.append((name, fn, tuple(tiers)))


def load_hooks(dir_path: Path) -> tuple[list, list]:
    """按路径加载 <dir>/hooks.py 并执行 register(registry)；无 hooks.py
    视为纯 schema 包静默成功；import/exec/注册任一异常 → (空清单, [警告])，
    异常绝不外溢（TC-EX-05 错误隔离）。"""
    hooks_file = Path(dir_path) / "hooks.py"
    if not hooks_file.is_file():
        return [], []
    # 模块名由路径哈希派生（稳定、不撞内置命名空间）；同一包多次加载
    # （挂载/重载各一次）同名重 exec 即可
    mod_name = ("_snowel_ext_hooks_"
                + hashlib.sha256(str(hooks_file).encode()).hexdigest()[:12])
    registry = Registry()
    try:
        spec = importlib.util.spec_from_file_location(mod_name, hooks_file)
        module = importlib.util.module_from_spec(spec)
        # sys.modules 防污染（裁决）：条目仅 exec 期间在场、finally 必除——
        # dataclasses 等运行时按模块名反查的机制需要条目在场才稳；exec 抛错
        # 同样清理，进程长期状态零残留。
        sys.modules[mod_name] = module
        try:
            spec.loader.exec_module(module)
            module.register(registry)
        finally:
            sys.modules.pop(mod_name, None)
    except Exception as e:  # noqa: BLE001  R5/TC-EX-05：包错不上抛，只转警告
        return [], [f"扩展包 {dir_path} 的 hooks.py 加载失败，"
                    f"本包规则全部未注册: {type(e).__name__}: {e}"]
    return registry.entries, []


def _activate_hooks(pack_name: str, entries: list) -> list[str]:
    """暂存条目统一提交入引擎（mount/reload 共用）。R2 包级原子：任一条
    engine.register 失败 → 已进引擎的同包条目全部 unregister 后整体作废。"""
    done: list[str] = []
    try:
        for name, fn, tiers in entries:
            engine.register(name, fn, tiers=tiers)
            done.append(name)
    except Exception as e:  # noqa: BLE001  与 load 同策略：失败转警告不外溢
        for n in done:
            engine.unregister(n)
        return [f"扩展包 {pack_name} 的 hooks 规则提交失败，已回滚本包全部规则:"
                f" {type(e).__name__}: {e}"]
    return []


def mount(api, name: str) -> dict:
    """挂载扩展包（R5 顺序）：定位 → 组模型构建全成功 → 单事务 append
    extension_mounted + apply 投影 → 进程态注册组 → hooks 规则提交
    （R2 包级原子；R5：hooks 失败不阻断挂载，只随响应降警告）。"""
    conn = api._conn
    manifest = next((m for m in discover(api._root) if m.name == name), None)
    if manifest is None:
        raise ValueError(
            f"未找到扩展包: {name}（项目/全局 extensions 目录下均无此包）")
    models = build_group_models(manifest)  # 失败即中止，事件未落、无半状态
    with db.transaction(conn):             # 事件与投影单事务原子（固定模式）
        seq = events.append_event(conn, "extension_mounted", {
            "name": manifest.name, "version": manifest.version,
            "source_path": str(manifest.dir_path),
            "schema_digest": manifest.schema_digest})
        projector.apply(conn)
    # 组注册版本从 schema 摘要内容派生：同一 schema 内容版本号稳定，
    # 内容一变自然换版——与 digest 升级判据（C-1）同源
    group_version = int(manifest.schema_digest[:8], 16)
    for gname, model in models.items():
        groups.register(model, gname, version=group_version)
    entries, hook_warns = load_hooks(manifest.dir_path)
    hook_warns += _activate_hooks(manifest.name, entries)
    # 本轮 discover 重扫了双位置全部包：建议性跳过字段警告一并随响应呈现
    return {"warnings": discovery.drain_warnings() + hook_warns}


def _mounted_groups_of(source_path: Path) -> list[str]:
    """执行-1 Ruling：引用校验/组注销的名单 = 现场 parse 该包 dir 得到的
    groups 键；孤儿（目录缺失/损坏，parse 返 None）返回空名单。"""
    manifest, _ = parse_manifest(source_path)
    return sorted(manifest.raw["groups"]) if manifest is not None else []


def unmount(api, name: str) -> int:
    """卸载扩展包：未 mounted 拒绝；活跃节点仍引用任一组键时拒绝（R4）；
    通过则事务内 append extension_unmounted + apply → 撤进程态组注册。
    数据保留（组字段降级 unmanaged 照存），孤儿包无组名单、跳过引用校验
    直接放行（降级语义下无可守护数据）。"""
    conn = api._conn
    row = conn.execute("SELECT source_path FROM extensions "
                       "WHERE name=? AND status='mounted'", (name,)).fetchone()
    if row is None:
        raise ValueError(f"扩展包未挂载: {name}")
    group_names = _mounted_groups_of(Path(row["source_path"]))
    with db.transaction(conn):
        # R4 引用预查：active=1 节点 props 含该包任一组键即拦（json_extract
        # 参数化路径，TOCTOU 同锁窗口）；首个命中组列节点 id（封顶 10 个）
        for g in group_names:
            ids = [r["id"] for r in conn.execute(
                "SELECT id FROM nodes WHERE active=1 "
                "AND json_extract(props, ?) IS NOT NULL", (f"$.{g}",))]
            if ids:
                shown = "、".join(ids[:10])
                more = f" 等 {len(ids)} 个" if len(ids) > 10 else ""
                raise ValueError(
                    f"属性组 {g} 被 {len(ids)} 个活跃节点引用："
                    f"{shown}{more}，先 retcon/迁移后卸载")
        seq = events.append_event(conn, "extension_unmounted", {"name": name})
        projector.apply(conn)
    for g in group_names:
        groups.unregister(g)
    return seq


def list_extensions(api) -> list[dict]:
    """发现全集 × 状态表 join：磁盘存在为准（version/scope 取现场 manifest），
    mounted/digest_matches 取投影状态；仅存于状态表的行（磁盘已消失）以
    scope=None 补入尾部——孤儿对用户必须可见。"""
    state = {r["name"]: r for r in api._conn.execute(
        "SELECT * FROM extensions")}
    out = []
    for m in discover(api._root):
        s = state.pop(m.name, None)
        out.append({"name": m.name, "scope": m.scope,
                    "mounted": bool(s and s["status"] == "mounted"),
                    "version": m.version,
                    "digest_matches": None if s is None
                    else s["schema_digest"] == m.schema_digest})
    for name, s in sorted(state.items()):
        out.append({"name": name, "scope": None,
                    "mounted": s["status"] == "mounted",
                    "version": s["version"], "digest_matches": False})
    return out


def extensions_status(api) -> list[dict]:
    """挂载明细 + 健康标注（CLI ext status 数据面）：孤儿与 schema 升级
    未跟随两类异常 healthy=False 且 note 携带原因；未挂载属正常态非异常。"""
    out = []
    for e in list_extensions(api):
        if e["scope"] is None:   # 仅存于状态表：磁盘包已消失（孤儿）
            healthy, note = False, ("扩展包目录缺失或已损坏，本次启动未激活"
                                    "（已有数据降级 unmanaged 语义照存）")
        elif e["mounted"] and e["digest_matches"] is False:
            healthy, note = False, ("schema 与挂载时不一致（升级不自动跟随），"
                                    "如需生效请显式重新挂载")
        else:
            healthy, note = True, ("" if e["mounted"] else "已发现，未挂载")
        out.append({"name": e["name"], "version": e["version"],
                    "scope": e["scope"], "mounted": e["mounted"],
                    "healthy": healthy, "note": note})
    return out


def reload(api) -> list[str]:
    """启动重载（R3）：逐个 mounted 行按 source_path 磁盘定位——孤儿或
    schema_digest 与挂载时不一致（全局升级不自动跟随，C-1）→ 警告不激活；
    正常 → 构建组模型并注册进程态，hooks 规则包级原子提交（R2）。
    整体吞错转警告，绝不让 open 崩。
    纯进程内存操作，不触库，readonly 会话同样安全。"""
    warns: list[str] = []
    try:
        discover(api._root)  # 全量扫描一轮：未挂载坏包的剔除原因经警告池收集（TC-EX-05）
        rows = api._conn.execute(
            "SELECT name, source_path, schema_digest FROM extensions "
            "WHERE status='mounted' ORDER BY name").fetchall()
        for row in rows:
            manifest, parse_warns = parse_manifest(Path(row["source_path"]))
            warns.extend(parse_warns)
            if manifest is None:
                warns.append(f"扩展包 {row['name']} 的目录 {row['source_path']} "
                             "缺失或已损坏，本次启动不激活"
                             "（已有数据降级 unmanaged 语义照存）")
                continue
            if manifest.schema_digest != row["schema_digest"]:
                warns.append(f"扩展包 {row['name']} 的 schema 与挂载时不一致"
                             "（升级不自动跟随），如需生效请显式重新挂载"
                             "（re-mount）")
                continue
            for gname, model in build_group_models(manifest).items():
                groups.register(model, gname,
                                version=int(manifest.schema_digest[:8], 16))
            entries, hook_warns = load_hooks(manifest.dir_path)
            warns.extend(_activate_hooks(row["name"], entries))
            warns.extend(hook_warns)
        warns.extend(discovery.drain_warnings())
    except Exception as e:  # noqa: BLE001  R3：重载失败只降级为警告
        warns.append(f"扩展包启动重载失败: {type(e).__name__}: {e}")
    return warns
