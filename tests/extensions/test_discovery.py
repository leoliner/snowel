import hashlib
import json
from pathlib import Path

import pytest

from snowel_core.extensions import discovery
from snowel_core.extensions.discovery import discover, parse_manifest

# 合成标准包：字段铺满 R1 映射表（string+enum / integer / number /
# array<string>）并带 required/pattern 约束——roundtrip 断言这些约束原样进 raw。
PACK_SCHEMA = {
    "name": "wuxia",
    "version": "0.1.0",
    "groups": {
        "combat": {
            "type": "object",
            "required": ["realm"],
            "properties": {
                "realm": {"type": "string", "enum": ["炼气", "金丹"]},
                "title": {"type": "string", "pattern": "^《.+》$"},
                "speed": {"type": "number"},
                "moves": {"type": "array", "items": {"type": "string"}},
            },
        }
    },
}


def write_pack(base: Path, name: str, payload) -> Path:
    """现造合成包目录：payload 为 None 时不写 schema.json（模拟缺文件）。"""
    d = base / name
    d.mkdir(parents=True)
    if payload is not None:
        text = payload if isinstance(payload, str) else json.dumps(
            payload, ensure_ascii=False)
        (d / "schema.json").write_text(text, encoding="utf-8")
    return d


@pytest.fixture
def monkey_patch_home(tmp_path, monkeypatch):
    """伪造家目录：Windows 读 USERPROFILE、POSIX 读 HOME，两处都改并钉死
    Path.home，避免对本机真实 ~/.snowel 的依赖。"""
    home = tmp_path / "home"
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("USERPROFILE", str(home))
    monkeypatch.setattr(Path, "home", staticmethod(lambda: home))
    return home


@pytest.fixture(autouse=True)
def _fresh_warning_pool():
    discovery.drain_warnings()
    yield


def test_discover_prefers_project_over_global(tmp_path, monkey_patch_home):  # TC-EX-01
    global_dir = monkey_patch_home / ".snowel" / "extensions"
    old = dict(PACK_SCHEMA, version="0.1.0")
    new = dict(PACK_SCHEMA, version="0.2.0")
    write_pack(global_dir, "wuxia", old)
    write_pack(tmp_path / "extensions", "wuxia", new)

    packs = discover(tmp_path)
    assert len(packs) == 1
    assert packs[0].name == "wuxia"
    assert packs[0].version == "0.2.0"  # 项目内版本生效（覆盖全局）
    assert packs[0].scope == "project"


def test_parse_valid_manifest_roundtrip(tmp_path, monkey_patch_home):
    d = write_pack(tmp_path / "extensions", "wuxia", PACK_SCHEMA)
    manifest, warns = parse_manifest(d)

    assert warns == []
    assert manifest.name == "wuxia"
    assert manifest.version == "0.1.0"
    assert manifest.dir_path == d
    assert manifest.scope == "project"  # 不在全局目录下 → project
    assert manifest.schema_digest == hashlib.sha256(
        (d / "schema.json").read_bytes()).hexdigest()  # sha256(原文字节) 十六进制
    assert manifest.raw["groups"]["combat"]["required"] == ["realm"]
    assert manifest.raw["groups"]["combat"]["properties"]["realm"]["enum"] == ["炼气", "金丹"]
    # warns == [] 即锁定 required/enum/pattern 这类约束不触发跳过警告


def test_missing_schema_skips_with_warning(tmp_path, monkey_patch_home):  # TC-EX-05 schema 半
    broken = write_pack(tmp_path / "extensions", "broken", None)  # 目录在、schema 缺
    good = write_pack(tmp_path / "extensions", "good", PACK_SCHEMA)

    m, warns = parse_manifest(broken)
    assert m is None
    assert len(warns) == 1 and "缺 schema.json" in warns[0]

    # discover 剔除坏包、警告入池，好包不受牵连
    packs = discover(tmp_path)
    assert len(packs) == 1
    assert packs[0].dir_path == good  # 名字取自 schema：仍是 wuxia，不是目录名 good
    pooled = discovery.drain_warnings()
    assert len(pooled) == 1 and "broken" in pooled[0]


def test_invalid_manifest_variants_skip(tmp_path, monkey_patch_home):
    # JSON 坏
    m, warns = parse_manifest(write_pack(tmp_path, "bad_json", "{oops"))
    assert m is None and "不是合法 JSON" in warns[0]
    # 缺 version
    m, warns = parse_manifest(write_pack(
        tmp_path, "no_ver", {"name": "ghost", "groups": {}}))
    assert m is None and "缺少有效 version" in warns[0]
    # 片段本身违反 JSON Schema 元模式（type 数字非法）
    m, warns = parse_manifest(write_pack(
        tmp_path, "bad_fragment",
        {"name": "x", "version": "0.1", "groups": {"g": {"type": 123}}}))
    assert m is None and "片段校验失败" in warns[0]
    # 类型越映射表：包仍合法挂载，仅收集跳过字段警告（R1）
    m, warns = parse_manifest(write_pack(
        tmp_path, "odd_type",
        {"name": "ok", "version": "9.9",
         "groups": {"g": {"properties": {"weird": {"type": "object"}}}}}))
    assert m is not None and m.name == "ok"
    assert len(warns) == 1 and "不在映射表" in warns[0]


def test_discover_no_global_dir_is_silent(tmp_path, monkey_patch_home):
    # ~/.snowel/extensions 从未创建：root=None 与给定项目根都静默为空、零警告
    assert discover(None) == []
    assert discover(tmp_path) == []
    assert discovery.drain_warnings() == []
