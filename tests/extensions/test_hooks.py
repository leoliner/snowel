"""扩展包 hooks 隔离加载（TC-EX-04 / TC-EX-05 hooks 半、R2 包级原子）。"""
import json
import shutil
from pathlib import Path

import pytest

from snowel_core.api import SnowelAPI
from snowel_core.consistency import engine, wiring
from snowel_core.extensions import discovery
from snowel_core.ontology import groups
from snowel_core.storage import db, events, projector

PACK_SCHEMA = {
    "name": "wuxia",
    "version": "0.1.0",
    "groups": {
        "combat": {
            "type": "object",
            "properties": {
                "power": {"type": "integer"},
                "realm": {"type": "string"},
            },
        }
    },
}

HOOKS_OK = '''\
def register(registry):
    def _power_needs_realm(change, conn):
        combat = ((change.get("fact") or {}).get("props") or {}).get("combat")
        if isinstance(combat, dict) and combat.get("power", 0) > 0 \
                and not combat.get("realm"):
            return [{"level": "minor", "rule": "power_needs_realm",
                     "message": "战力>0 必须给出境界", "refs": []}]
        return []

    registry.rule("power_needs_realm", _power_needs_realm)
'''

# 注册第 1 条成功后中途崩：R2 要求第 1 条也不许进引擎（包级原子）
HOOKS_PARTIAL = '''\
def register(registry):
    registry.rule("roll_a", lambda change, conn: [])
    raise RuntimeError("第二条注册前炸了")
'''


@pytest.fixture(autouse=True)
def _isolated_ext_env(tmp_path, monkeypatch):
    """钉死家目录（discover 总会扫全局 ~/.snowel）、清空警告池；teardown
    把进程态共享注册表（组 + 引擎规则）回退到进场前键集合。"""
    home = tmp_path / "home"
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("USERPROFILE", str(home))
    monkeypatch.setattr(Path, "home", staticmethod(lambda: home))
    discovery.drain_warnings()
    known_groups = set(groups._registered)
    known_rules = set(engine._RULES)
    yield
    for n in set(groups._registered) - known_groups:
        groups.unregister(n)
    for n in set(engine._RULES) - known_rules:
        engine.unregister(n)
    discovery.drain_warnings()


def _write_pack(base: Path, schema=PACK_SCHEMA, hooks=None) -> Path:
    d = base / schema["name"]
    d.mkdir(parents=True, exist_ok=True)
    (d / "schema.json").write_text(
        json.dumps(schema, ensure_ascii=False), encoding="utf-8")
    if hooks is not None:
        (d / "hooks.py").write_text(hooks, encoding="utf-8")
    return d


# 真包（R3 主锚）：tests/extensions → tests → 仓库根
PACK_DIR = Path(__file__).parents[2] / "extensions" / "infinite-flow"


def _copy_pack(base: Path) -> Path:
    """真包只读 copytree 到 tmp 项目 extensions/（R3：绝不原地挂载仓库目录）。"""
    d = base / "infinite-flow"
    shutil.copytree(PACK_DIR, d)
    return d


def _seed_mechanism(conn, level):
    """内置规则触发器（tests/consistency/test_wiring.py 同款种子）：
    既有 Mechanism.mechanism.level，后续变更才构成矛盾比对面。"""
    with db.transaction(conn):
        events.append_event(conn, "proposal_confirmed", {
            "artifact_type": "t", "facts": [
                {"fact": "node", "id": "m1", "types": ["Mechanism"],
                 "name": "积分兑换", "props": {"mechanism": {"level": level}}}]})
    projector.apply(conn)


# 一份变更集同时踩两条线：flow_rank_track 缺 direction（真包规则，R2 语义
# 义务未履行）与 mechanism.level 3→7（内置 contradiction 规则）
_MIXED_CHANGES = [
    {"fact": "node", "id": "n1", "types": ["Character"], "name": "林晚",
     "props": {"flow_rank_track": {"current_rank": 480000}}},
    {"fact": "node", "id": "m1", "types": ["Mechanism"], "name": "积分兑换",
     "props": {"mechanism": {"level": 7}}}]

# 同一节点补 direction：语义义务已履行，真包规则不再报（schema 上 direction
# 刻意 optional——形状归 schema、语义归 hooks 的分工实证）
_DIRECTED_CHANGES = [
    {"fact": "node", "id": "n1", "types": ["Character"], "name": "林晚",
     "props": {"flow_rank_track": {"current_rank": 480000,
                                   "direction": "descending"}}}]


def test_pack_rule_runs_in_same_engine(api):                       # TC-EX-04
    _copy_pack(api._root / "extensions")
    _seed_mechanism(api._conn, level=3)

    pre = wiring.analyze(api._conn, _MIXED_CHANGES, "full")
    pre_rules = {v["rule"] for v in pre}
    # 挂载前真包规则缺席（引擎规则是进程级全局，其他测试的残留规则不保证清空，
    # 故只做成员断言不做全集相等）
    assert "contradiction" in pre_rules
    assert "flow_rank_track_direction_required" not in pre_rules

    res = api.mount_extension("infinite-flow")
    assert res["warnings"] == []
    assert "flow_rank_track_direction_required" in engine._RULES

    post = wiring.analyze(api._conn, _MIXED_CHANGES, "full")
    assert {"contradiction", "flow_rank_track_direction_required"} <= {
        v["rule"] for v in post}       # 同引擎混跑：两类 Violation 并存互不影响
    hit = next(v for v in post
               if v["rule"] == "flow_rank_track_direction_required")
    assert hit["level"] == "major"
    assert hit["message"] == "排名轨迹写入须附轨迹方向 direction"
    assert hit["refs"] == ["n1"]       # R2：refs 含节点 id

    after = wiring.analyze(api._conn, _DIRECTED_CHANGES, "full")
    assert "flow_rank_track_direction_required" not in {
        v["rule"] for v in after}      # 补 direction 后无


@pytest.mark.parametrize(
    "bad_hooks,marker",
    [('raise RuntimeError("boom")\n', "RuntimeError"),
     ('def register(registry)\n    pass\n', "SyntaxError")])
def test_hooks_syntax_error_isolated(api, bad_hooks,
                                     marker):                     # TC-EX-05 hooks 半
    base = api._root / "extensions"
    _write_pack(base, hooks=bad_hooks)

    res = api.mount_extension("wuxia")        # R5：包坏不阻断挂载本身
    assert marker in "\n".join(res["warnings"])   # 隔离且警告含原因
    assert "power_needs_realm" not in engine._RULES
    assert api.save_inspiration("巷口的雨声")      # 核心功能如常


def test_rule_batch_rollback_on_partial_failure(api):
    base = api._root / "extensions"
    _write_pack(base, hooks=HOOKS_PARTIAL)

    res = api.mount_extension("wuxia")
    assert any("RuntimeError" in w for w in res["warnings"])
    assert "roll_a" not in engine._RULES         # 第 1 条也被撤：包级原子
    row = api._conn.execute(
        "SELECT status FROM extensions WHERE name='wuxia'").fetchone()
    assert row["status"] == "mounted"            # 规则没了 ≠ 包挂载失败


# ---- 执行-2 Ruling 锁定：unmount 撤销本包 hooks 规则（实例记账）----

_HOOK_TRIGGER = [{"fact": "node", "id": "n1", "types": ["Character"],
                  "name": "剑修", "props": {"combat": {"power": 5}}}]


def test_unmount_retires_hook_rules_same_instance(api):
    _write_pack(api._root / "extensions", hooks=HOOKS_OK)
    api.mount_extension("wuxia")

    hit = wiring.analyze(api._conn, _HOOK_TRIGGER, "full")
    assert any(v["rule"] == "power_needs_realm" for v in hit)

    api.unmount_extension("wuxia")               # 无活跃引用，正常卸载
    assert "power_needs_realm" not in engine._RULES
    # 同一变更不再触发该包规则（成员负断言：全量套件下他测试的残留规则
    # 不保证清空，全集相等断言会误伤）
    after = wiring.analyze(api._conn, _HOOK_TRIGGER, "full")
    assert "power_needs_realm" not in {v["rule"] for v in after}
    assert api._active_rules.get("wuxia") is None  # 账目同步清空


def test_reloaded_instance_accounting_covers_unmount(tmp_path):
    proj = tmp_path / "proj"
    a = SnowelAPI.init_project(proj)
    _write_pack(proj / "extensions", hooks=HOOKS_OK)
    a.mount_extension("wuxia")
    a.close()

    api2 = SnowelAPI.open(proj)                  # reload 重激活 + 记账
    hit = wiring.analyze(api2._conn, _HOOK_TRIGGER, "full")
    assert any(v["rule"] == "power_needs_realm" for v in hit)

    api2.unmount_extension("wuxia")
    assert "power_needs_realm" not in engine._RULES
    after = wiring.analyze(api2._conn, _HOOK_TRIGGER, "full")
    assert "power_needs_realm" not in {v["rule"] for v in after}
    api2.close()
