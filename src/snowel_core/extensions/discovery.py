# src/snowel_core/extensions/discovery.py
"""扩展包双位置发现与 manifest 解析（addendum §3.1）。

纯函数层：不碰 ontology 注册表、不写任何事件；PackManifest.raw 供后续
挂载任务构组 pydantic 模型消费。
"""
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

from jsonschema import Draft202012Validator
from jsonschema.exceptions import SchemaError

# R1 映射表（本任务只用于识别可构组字段、收集跳过警告，不做映射产物）
_SCALAR_TYPES = ("string", "integer", "number", "boolean")


@dataclass
class PackManifest:
    name: str
    version: str
    dir_path: Path
    scope: str  # 仅 "project" / "global"
    schema_digest: str  # sha256(schema.json 原文字节) 十六进制
    raw: dict  # schema.json 解析后的全文 dict


# 发现期全局警告池：坏包剔除原因在此累积，由启动/挂载层 drain 呈现
_warning_pool: list[str] = []


def drain_warnings() -> list[str]:
    out = _warning_pool[:]
    _warning_pool.clear()
    return out


def _global_extensions_dir() -> Path:
    # Path.home 在 Windows 读 USERPROFILE、POSIX 读 HOME，走标准展开即可
    return Path.home() / ".snowel" / "extensions"


def _scope_of(dir_path: Path) -> str:
    try:
        dir_path.resolve().relative_to(_global_extensions_dir().resolve())
        return "global"
    except ValueError:
        return "project"


def _skipped_fields(dir_path: Path, group_name: str, fragment: dict) -> list[str]:
    # R1：类型越映射表的字段包仍合法，但后续构组会跳过 → 先收集警告备用
    out = []
    properties = fragment.get("properties")
    if not isinstance(properties, dict):
        return out
    for field, spec in properties.items():
        if not isinstance(spec, dict):  # JSON Schema 允许布尔 schema，这里视为不支持
            out.append(f"扩展包 {dir_path} 组 {group_name} 字段 {field}"
                       f" 是布尔 schema，后续构组将跳过")
            continue
        t = spec.get("type")
        supported = t in _SCALAR_TYPES or (
            t == "array" and isinstance(spec.get("items"), dict)
            and spec["items"].get("type") == "string")
        if not supported:
            out.append(f"扩展包 {dir_path} 组 {group_name} 字段 {field}"
                       f" 类型 {t!r} 不在映射表，后续构组将跳过")
    return out


def parse_manifest(dir_path: Path) -> tuple[PackManifest | None, list[str]]:
    """读 <dir>/schema.json 并按 R1 校验；任何致命问题返 (None, [警告])
    视同缺失包。"""
    schema_file = dir_path / "schema.json"
    try:
        schema_bytes = schema_file.read_bytes()
    except OSError:
        return None, [f"扩展包 {dir_path} 缺 schema.json，已跳过"]
    try:
        raw = json.loads(schema_bytes)
    except ValueError as e:  # JSONDecodeError/UnicodeDecodeError 同源
        return None, [f"扩展包 {dir_path} schema.json 不是合法 JSON: {e}"]

    name = raw.get("name") if isinstance(raw, dict) else None
    if not name or not isinstance(name, str):
        return None, [f"扩展包 {dir_path} 缺少有效 name（非空字符串），视同缺失包"]
    version = raw.get("version")
    if not version or not isinstance(version, str):
        return None, [f"扩展包 {dir_path} 缺少有效 version（非空字符串），视同缺失包"]
    group_fragments = raw.get("groups", {})
    if not isinstance(group_fragments, dict):
        return None, [f"扩展包 {dir_path} groups 必须是对象，视同缺失包"]
    warns: list[str] = []
    for group_name, fragment in group_fragments.items():
        if not isinstance(fragment, dict):
            return None, [
                f"扩展包 {dir_path} 组 {group_name} 片段必须是对象，视同缺失包"]
        try:
            Draft202012Validator.check_schema(fragment)
        except SchemaError as e:
            return None, [
                f"扩展包 {dir_path} 组 {group_name} 片段校验失败: {e.message}"]
        warns.extend(_skipped_fields(dir_path, group_name, fragment))
    return PackManifest(
        name=name, version=version, dir_path=dir_path,
        scope=_scope_of(dir_path),
        schema_digest=hashlib.sha256(schema_bytes).hexdigest(), raw=raw), warns


def discover(root: Path | None) -> list[PackManifest]:
    """扫描全局 ~/.snowel/extensions/* 与项目 <root>/extensions/*；
    root 为 None 只扫全局。先全局后项目、同名后者覆盖前者（TC-EX-01）。
    全局目录不存在静默为空（首次使用零摩擦）；坏包剔除并入警告池。"""
    bases = [_global_extensions_dir()]
    if root is not None:
        bases.append(Path(root) / "extensions")
    found: dict[str, PackManifest] = {}
    for base in bases:
        if not base.is_dir():
            continue
        for pack_dir in sorted(p for p in base.iterdir() if p.is_dir()):
            manifest, warns = parse_manifest(pack_dir)
            if manifest is None:
                _warning_pool.extend(warns)
                continue
            found[manifest.name] = manifest
    return list(found.values())
