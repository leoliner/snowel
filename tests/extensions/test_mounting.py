"""扩展包挂载/卸载事件闭环 + 启动重载（TC-EX-02/03、重载语义 R3-R5）。"""
import json
import shutil
from pathlib import Path

import pytest

from snowel_core.api import SnowelAPI
from snowel_core.extensions import discovery
from snowel_core.ontology import groups
from snowel_core.storage import db, events, projector

# 与 test_discovery 同款合成包：字段铺满 R1 映射表并带 required/enum/pattern
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
    d.mkdir(parents=True, exist_ok=True)
    if payload is not None:
        text = payload if isinstance(payload, str) else json.dumps(
            payload, ensure_ascii=False)
        (d / "schema.json").write_text(text, encoding="utf-8")
    return d


@pytest.fixture(autouse=True)
def _isolated_ext_env(tmp_path, monkeypatch):
    """钉死家目录（discover 总会扫全局 ~/.snowel，不能依赖本机真家目录）、
    清空警告池；teardown 清掉测试注册的扩展组（进程态注册表全局共享，
    只保内置 core 组），规则引擎 T2 阶段无 hooks 注册无需清理。"""
    home = tmp_path / "home"
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("USERPROFILE", str(home))
    monkeypatch.setattr(Path, "home", staticmethod(lambda: home))
    discovery.drain_warnings()
    yield
    for name in [n for n in groups._registered if n != "core"]:
        groups.unregister(name)
    discovery.drain_warnings()


def _confirm(api, facts):
    """最小事实写入路径（tests/storage/test_queries.py 先例）：不走提案队列，
    直接 proposal_confirmed 事件 + 投影。"""
    with db.transaction(api._conn):
        events.append_event(api._conn, "proposal_confirmed", {
            "proposal_id": "p", "artifact_type": "t", "facts": facts})
    projector.apply(api._conn)


def _retract_node(api, node_id):
    with db.transaction(api._conn):
        events.append_event(api._conn, "retraction", {
            "target": "node", "target_id": node_id, "cascade_hints": []})
    projector.apply(api._conn)


def _mount_pack(api) -> Path:
    return write_pack(api._root / "extensions", "wuxia", PACK_SCHEMA)


def test_mount_midway_does_not_touch_existing_nodes(api):  # TC-EX-02
    _mount_pack(api)
    _confirm(api, [{"fact": "node", "id": "n1", "types": ["Character"],
                    "name": "老侠客", "props": {"combat": {"realm": "元婴",
                                                           "_schema": "combat@999"}}}])
    before = json.loads(api.get_node("n1")["props"])

    result = api.mount_extension("wuxia")
    assert isinstance(result["warnings"], list)
    # 中途挂载零回溯：既有节点 props 原样、active 不受影响
    assert json.loads(api.get_node("n1")["props"]) == before

    # managed 生效：合法数据四态校验 ok（版本串声明与摘要派生版一致）
    status, warn = groups.validate("combat", {"realm": "炼气"})
    assert (status, warn) == ("ok", None)
    # 约束真的编译进了模型：required 缺失与越 enum 取值都 invalid
    assert groups.validate("combat", {"title": "abc"})[0] == "invalid"
    assert groups.validate("combat", {"realm": "化神"})[0] == "invalid"
    # extract 校验链视角：组字段不再是 unmanaged 警告
    from snowel_core.writeback.extract import _validate_groups
    assert _validate_groups({"props": {"combat": {"realm": "炼气"}}}) == []

    entry = next(e for e in api.list_extensions() if e["name"] == "wuxia")
    assert entry["scope"] == "project" and entry["mounted"] is True


def test_unmount_blocked_by_active_reference(api):  # TC-EX-03
    _mount_pack(api)
    api.mount_extension("wuxia")
    _confirm(api, [{"fact": "node", "id": "n-ref", "types": ["Character"],
                    "name": "剑修", "props": {"combat": {"realm": "金丹"}}}])
    n_before = api._conn.execute("SELECT COUNT(*) c FROM events").fetchone()["c"]

    with pytest.raises(ValueError, match="n-ref"):
        api.unmount_extension("wuxia")
    # 事务前拒绝：不留半事件，状态仍 mounted
    assert api._conn.execute(
        "SELECT COUNT(*) c FROM events").fetchone()["c"] == n_before
    assert api._conn.execute(
        "SELECT status FROM extensions WHERE name='wuxia'"
    ).fetchone()["status"] == "mounted"


def test_unmount_after_data_cleared_downgrades_to_unmanaged(api):
    _mount_pack(api)
    api.mount_extension("wuxia")
    _confirm(api, [{"fact": "node", "id": "n-ref", "types": ["Character"],
                    "name": "剑修", "props": {"combat": {"realm": "金丹"}}}])
    _retract_node(api, "n-ref")

    api.unmount_extension("wuxia")
    rows = api._conn.execute(
        "SELECT seq FROM events WHERE kind='extension_unmounted'").fetchall()
    assert len(rows) == 1                      # 恰一条卸载事件
    p = json.loads(api.get_node("n-ref", active_only=False)["props"])
    assert p["combat"] == {"realm": "金丹"}     # 数据保留原样
    # 回落 unmanaged：非法取值不再报 invalid（根本不校验了）
    assert groups.validate("combat", {"realm": "化神"})[0] == "unmanaged"
    from snowel_core.writeback.extract import _validate_groups
    warns = _validate_groups({"props": {"combat": {"realm": "化神"}}})
    assert any("unmanaged" in w for w in warns)


def test_remount_updates_digest_last_write_wins(api):
    d = _mount_pack(api)
    api.mount_extension("wuxia")
    old = api._conn.execute(
        "SELECT schema_digest, version FROM extensions "
        "WHERE name='wuxia'").fetchone()

    (d / "schema.json").write_text(
        json.dumps(dict(PACK_SCHEMA, version="0.2.0"), ensure_ascii=False),
        encoding="utf-8")
    api.mount_extension("wuxia")
    row = api._conn.execute(
        "SELECT schema_digest, version FROM extensions "
        "WHERE name='wuxia'").fetchone()
    fresh = discovery.parse_manifest(d)[0]
    assert row["schema_digest"] == fresh.schema_digest
    assert old["schema_digest"] != fresh.schema_digest   # last-write-wins 覆盖
    assert row["version"] == "0.2.0"
    kinds = api._conn.execute(
        "SELECT payload FROM events WHERE kind='extension_mounted' "
        "ORDER BY seq").fetchall()
    assert len(kinds) == 2                                # 恰两条挂载事件
    assert json.loads(kinds[0]["payload"])["version"] == "0.1.0"  # 历史 append-only


def test_reload_orphan_warns_and_degrades(api, tmp_path):
    d = _mount_pack(api)
    api.mount_extension("wuxia")
    api.close()
    shutil.rmtree(d)              # 手删包目录 → 孤儿
    groups.unregister("combat")   # 模拟进程重启后的空白进程态注册表
    api2 = SnowelAPI.open(tmp_path / "api")

    assert any("wuxia" in w for w in api2.extension_warnings)  # 孤儿警告
    assert "combat" not in groups._registered                  # 不激活
    row = api2._conn.execute(
        "SELECT status FROM extensions WHERE name='wuxia'").fetchone()
    assert row["status"] == "mounted"                          # 状态表不翻转（R3 只降级）
    assert api2.save_inspiration("巷口的雨声")                   # 核心功能如常
    api2.close()


def test_reload_skips_upgraded_global_pack_until_remount(tmp_path):
    gdir = Path.home() / ".snowel" / "extensions"
    d = write_pack(gdir, "wuxia", PACK_SCHEMA)
    proj = tmp_path / "proj"
    api = SnowelAPI.init_project(proj)
    api.mount_extension("wuxia")
    mounted = api._conn.execute(
        "SELECT schema_digest FROM extensions WHERE name='wuxia'").fetchone()
    api.close()
    groups.unregister("combat")

    # 全局包原地升级（digest 变）：C-1 不自动跟随，启动警告 + 保持不激活
    (d / "schema.json").write_text(
        json.dumps(dict(PACK_SCHEMA, version="9.9.9"), ensure_ascii=False),
        encoding="utf-8")
    api2 = SnowelAPI.open(proj)
    assert any("重新挂载" in w or "re-mount" in w for w in api2.extension_warnings)
    assert "combat" not in groups._registered
    row = api2._conn.execute(
        "SELECT schema_digest FROM extensions WHERE name='wuxia'").fetchone()
    assert row["schema_digest"] == mounted["schema_digest"]
    api2.close()

    # 显式 re-mount 才生效
    api3 = SnowelAPI.open(proj)
    api3.mount_extension("wuxia")
    assert "combat" in groups._registered
    api3.close()


def test_open_succeeds_with_broken_extensions_dir(tmp_path):  # TC-EX-05 核心
    proj = tmp_path / "proj"
    a = SnowelAPI.init_project(proj)
    a.close()
    ext = proj / "extensions"
    write_pack(ext, "no_schema", None)                 # 缺 schema.json
    write_pack(ext, "bad_json", "{oops")               # JSON 坏
    write_pack(ext, "bad_frag",
               {"name": "f", "version": "1", "groups": {"g": {"type": 123}}})
    good = write_pack(ext, "good", PACK_SCHEMA)        # 好包不受牵连

    api2 = SnowelAPI.open(proj)                        # 不抛即过半
    warns = api2.extension_warnings
    for marker in ("no_schema", "bad_json", "bad_frag"):
        assert any(marker in w for w in warns), warns
    assert api2.save_inspiration("雨停在字里行间")       # 内置功能如常
    packs = {m.name for m in discovery.discover(api2._root)}
    assert packs == {"wuxia"}  # 包名取自 schema.json（非目录名 good）
    api2.close()
