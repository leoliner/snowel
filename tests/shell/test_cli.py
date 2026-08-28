# tests/shell/test_cli.py
import json
import shutil
from pathlib import Path

import pytest
from typer.testing import CliRunner

from snowel.cli import app
from snowel_core.api import SnowelAPI
# 预热 import rules：core 内置级联规则在 rules.py import 时注册；若首次 import
# 发生在本文件某个 ext 用例内，_restore_ext_registries 的差分回退会把内置规则
# 误判为用例污染清空，殃及同进程后续测试的 cascade 断言（如 test_mcp_server）
from snowel_core.consistency import engine, rules
from snowel_core.extensions import discovery
from snowel_core.ontology import groups

runner = CliRunner()


@pytest.fixture(autouse=True)
def _restore_ext_registries():
    """tests/extensions/test_hooks.py 同款差分回退：本文件的 ext 用例挂载/
    卸载包时会写进程态共享注册表（组 + 引擎规则），teardown 回退到进场前键
    集合；警告池一并清空。家目录隔离由 tests/conftest 会话级 fixture 统一罩。"""
    discovery.drain_warnings()
    known_groups = set(groups._registered)
    known_rules = set(engine._RULES)
    yield
    for n in set(groups._registered) - known_groups:
        groups.unregister(n)
    for n in set(engine._RULES) - known_rules:
        engine.unregister(n)
    discovery.drain_warnings()

FACTS = [{"fact": "node", "id": "n1", "types": ["Character"],
          "name": "林晚", "props": {}}]


def test_init_creates_db(tmp_path):
    res = runner.invoke(app, ["init", "--project", str(tmp_path)])
    assert res.exit_code == 0
    assert (tmp_path / "snowel.db").exists()


def test_init_existing_project_hints(tmp_path):
    runner.invoke(app, ["init", "--project", str(tmp_path)])
    res = runner.invoke(app, ["init", "--project", str(tmp_path)])
    assert res.exit_code == 0
    assert "已存在" in res.output


def test_status_missing_project_exits_1(tmp_path):
    res = runner.invoke(app, ["status", "--project", str(tmp_path)])
    assert res.exit_code == 1
    assert "snowel init" in res.output


def test_status_reports_counts(tmp_path):
    SnowelAPI.init_project(tmp_path)
    api = SnowelAPI.open(tmp_path)
    api.proposals.create("scene", {"facts": FACTS})
    pid = api.proposals.create("scene", {"facts": FACTS})
    api.proposals.confirm(pid)
    api.close()
    res = runner.invoke(app, ["status", "--project", str(tmp_path)])
    assert res.exit_code == 0
    assert "pending 1" in res.output
    assert "confirmed 1" in res.output
    assert "节点 1" in res.output
    assert "Character 1" in res.output
    assert "流程" in res.output


def test_backup_roundtrip_and_overwrite_guard(tmp_path):
    SnowelAPI.init_project(tmp_path)
    api = SnowelAPI.open(tmp_path)
    pid = api.proposals.create("scene", {"facts": FACTS})
    api.proposals.confirm(pid)
    api.close()
    out = tmp_path / "b.db"
    res = runner.invoke(app, ["backup", "--project", str(tmp_path),
                              "--out", str(out)])
    assert res.exit_code == 0 and out.exists()
    res2 = runner.invoke(app, ["backup", "--project", str(tmp_path),
                               "--out", str(out)])
    assert res2.exit_code == 1 and "拒绝覆盖" in res2.output
    restore = tmp_path / "r"
    restore.mkdir()
    shutil.copy(out, restore / "snowel.db")
    api2 = SnowelAPI.open(restore)
    assert api2.graph_stats()["nodes"] == 1
    api2.close()


def test_export_writes_all_chapters(tmp_path):
    SnowelAPI.init_project(tmp_path)
    api = SnowelAPI.open(tmp_path)
    pid = api.proposals.create("prose", {"chapter_id": "ch1",
                                         "content": "第一章：雨夜。"})
    api.confirm(pid)
    api.close()
    out = tmp_path / "export"
    res = runner.invoke(app, ["export", "--project", str(tmp_path),
                              "--out", str(out)])
    assert res.exit_code == 0
    assert (out / "ch1.md").read_text(encoding="utf-8") == "第一章：雨夜。"


def test_export_txt_format(tmp_path):
    SnowelAPI.init_project(tmp_path)
    api = SnowelAPI.open(tmp_path)
    pid = api.proposals.create("prose", {"chapter_id": "ch1",
                                         "content": "正文"})
    api.confirm(pid)
    api.close()
    out = tmp_path / "export"
    res = runner.invoke(app, ["export", "--project", str(tmp_path),
                              "--out", str(out), "--format", "txt"])
    assert res.exit_code == 0
    assert (out / "ch1.txt").read_text(encoding="utf-8") == "正文"


def test_seal_command(tmp_path):
    SnowelAPI.init_project(tmp_path)
    api = SnowelAPI.open(tmp_path)
    pid = api.proposals.create("t", {"facts": [
        {"fact": "node", "id": "v1", "types": ["Volume"], "name": "卷一",
         "props": {"address": {"volume": 1, "chapter": 0, "scene": 0,
                               "beat": 0}}}]})
    api.confirm(pid)
    api.close()
    res = runner.invoke(app, ["seal", "--project", str(tmp_path), "v1"])
    assert res.exit_code == 0 and "卷一" in res.output
    res2 = runner.invoke(app, ["seal", "--project", str(tmp_path), "v1"])
    assert res2.exit_code == 1 and "已封" in res2.output
    res3 = runner.invoke(app, ["seal", "--project", str(tmp_path)])
    assert res3.exit_code == 2                       # volume_id 参数必填


def test_project_option_overrides_cwd(tmp_path, monkeypatch):
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    monkeypatch.delenv("SNOWEL_PROJECT", raising=False)
    monkeypatch.chdir(elsewhere)
    SnowelAPI.init_project(tmp_path / "proj")
    res = runner.invoke(app, ["status", "--project", str(tmp_path / "proj")])
    assert res.exit_code == 0


def test_project_option_prepositioned(tmp_path, monkeypatch):
    # 回调级用法：--project 位于子命令之前（cwd 无项目，验证选项真正生效）
    monkeypatch.delenv("SNOWEL_PROJECT", raising=False)
    monkeypatch.chdir(tmp_path)
    SnowelAPI.init_project(tmp_path / "proj")
    res = runner.invoke(app, ["--project", str(tmp_path / "proj"), "status"])
    assert res.exit_code == 0


def test_project_short_alias(tmp_path, monkeypatch):
    # 命令级短别名 -p 等价于 --project
    monkeypatch.delenv("SNOWEL_PROJECT", raising=False)
    monkeypatch.chdir(tmp_path)
    SnowelAPI.init_project(tmp_path / "proj")
    res = runner.invoke(app, ["status", "-p", str(tmp_path / "proj")])
    assert res.exit_code == 0


def test_status_via_env_var(tmp_path, monkeypatch):
    # 无显式选项时回落 SNOWEL_PROJECT（cwd 在别处）
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    SnowelAPI.init_project(tmp_path / "proj")
    monkeypatch.setenv("SNOWEL_PROJECT", str(tmp_path / "proj"))
    monkeypatch.chdir(elsewhere)
    res = runner.invoke(app, ["status"])
    assert res.exit_code == 0


# ---- mcp 子命令（R4/TC-SH-12：stdio 默认零变化；--http 显式开启；
# 绑 0.0.0.0/:: 强制 --token 否则拒绝启动）----

def test_mcp_command_wildcard_requires_token(monkeypatch):
    captured = {}

    def fake_main(**kw):
        captured.update(kw)

    monkeypatch.setattr("snowel.mcp_server.main", fake_main)

    for bad_host in ("0.0.0.0", "::"):
        res = runner.invoke(app, ["mcp", "--http", "--host", bad_host])
        assert res.exit_code == 1
        assert "token" in res.output

    # 带 token → 守卫放行，token/host/http 原样透传 main
    ok = runner.invoke(app, ["mcp", "--http", "--host", "0.0.0.0",
                             "--token", "s3cret"])
    assert ok.exit_code == 0
    assert captured["http"] is True and captured["token"] == "s3cret"
    assert captured["host"] == "0.0.0.0"

    # 默认 host（loopback）无 token 不拦；host/port 默认值透传
    loop = runner.invoke(app, ["mcp", "--http"])
    assert loop.exit_code == 0
    assert captured["host"] == "127.0.0.1" and captured["port"] == 8642
    assert captured["token"] is None

    # 无 --http → stdio 默认路径（http=False）；--project 语义与 web 命令同构
    plain = runner.invoke(app, ["mcp", "-p", "some/proj"])
    assert plain.exit_code == 0
    assert captured["http"] is False
    assert Path(captured["project"]) == Path("some/proj").resolve()


def test_mcp_command_bracketed_ipv6_host_normalized(monkeypatch):  # RW-②
    # 方括号 host 归一（"[::1]"→"::1"）防 build_mcp 二次包裹崩；守卫集合
    # 匹配在 strip 后进行——"[::]" 归一为 "::" 仍被通配守卫拦截（语义不弱化）
    captured = {}

    def fake_main(**kw):
        captured.update(kw)

    monkeypatch.setattr("snowel.mcp_server.main", fake_main)

    res = runner.invoke(app, ["mcp", "--http", "--host", "[::1]",
                              "--token", "s3cret"])
    assert res.exit_code == 0  # ::1 是 loopback 非通配：持 token 直接放行
    assert captured["host"] == "::1"

    for bracketed_wildcard in ("[0.0.0.0]", "[::]"):
        blocked = runner.invoke(app, ["mcp", "--http", "--host",
                                      bracketed_wildcard])
        assert blocked.exit_code == 1
        assert "token" in blocked.output


# ---- ext 子命令组（TC-EX-01/03 出口面；hooks 引擎行为在 tests/extensions/）----

EXT_SCHEMA = {
    "name": "wuxia",
    "version": "0.1.0",
    "groups": {
        "combat": {
            "type": "object",
            "properties": {"realm": {"type": "string"}},
        }
    },
}


def write_ext(base, payload=EXT_SCHEMA):
    d = base / payload["name"]
    d.mkdir(parents=True, exist_ok=True)
    (d / "schema.json").write_text(
        json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return d


# 真包（R3 主锚）：tests/shell → tests → 仓库根
PACK_DIR = Path(__file__).parents[2] / "extensions" / "infinite-flow"


def _copy_pack(base, *, version=None):
    """真包只读 copytree 到 tmp 侧（R3：绝不原地挂载仓库目录）；version 给定
    时改写副本 manifest 的 version 字节 → 同名不同 digest（TC-EX-01 全局侧）。"""
    d = base / "infinite-flow"
    shutil.copytree(PACK_DIR, d,
                    ignore=shutil.ignore_patterns("__pycache__"))
    if version is not None:
        manifest = json.loads((d / "schema.json").read_text(encoding="utf-8"))
        manifest["version"] = version
        (d / "schema.json").write_text(
            json.dumps(manifest, ensure_ascii=False), encoding="utf-8")
    return d


def test_ext_list_shows_project_override_and_mount_state(
        tmp_path, monkeypatch):                                 # TC-EX-01 出口可见
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("USERPROFILE", str(home))
    monkeypatch.setattr(Path, "home", staticmethod(lambda: home))
    gdir = home / ".snowel" / "extensions"
    _copy_pack(gdir, version="2.0.0")                    # 全局同名改版
    write_ext(gdir, dict(EXT_SCHEMA, name="xianxia", version="2.0.0"))
    proj = tmp_path / "proj"
    SnowelAPI.init_project(proj)
    _copy_pack(proj / "extensions")                      # 项目内原版 1.0.0
    runner.invoke(app, ["ext", "mount", "infinite-flow", "-p", str(proj)])

    res = runner.invoke(app, ["ext", "list", "-p", str(proj)])
    assert res.exit_code == 0
    flow = next(l for l in res.output.splitlines()
                if l.startswith("infinite-flow"))
    assert "项目" in flow and "1.0.0" in flow             # 项目覆盖全局生效
    assert "已挂载" in flow and "2.0.0" not in flow       # 挂载态可见，改版不出现
    xianxia = next(l for l in res.output.splitlines()
                   if l.startswith("xianxia"))
    assert "全局" in xianxia and "未挂载" in xianxia       # 双位置发现全集


def test_ext_mount_unmount_lifecycle(tmp_path):
    proj = tmp_path / "proj"
    SnowelAPI.init_project(proj)
    _copy_pack(proj / "extensions")

    ghost = runner.invoke(app, ["ext", "mount", "ghost", "-p", str(proj)])
    assert ghost.exit_code == 1 and "未找到" in ghost.output

    res = runner.invoke(app, ["ext", "mount", "infinite-flow", "-p", str(proj)])
    assert res.exit_code == 0 and "已挂载" in res.output
    st = runner.invoke(app, ["ext", "status", "-p", str(proj)])
    assert st.exit_code == 0
    assert "infinite-flow" in st.output and "正常" in st.output

    res2 = runner.invoke(app,
                         ["ext", "unmount", "infinite-flow", "-p", str(proj)])
    assert res2.exit_code == 0 and "已卸载" in res2.output
    again = runner.invoke(app,
                          ["ext", "unmount", "infinite-flow", "-p", str(proj)])
    assert again.exit_code == 1 and "未挂载" in again.output


def test_ext_unmount_refusal_shows_reason(tmp_path):        # TC-EX-03 呈现面
    proj = tmp_path / "proj"
    SnowelAPI.init_project(proj)
    _copy_pack(proj / "extensions")
    api = SnowelAPI.open(proj)
    api.mount_extension("infinite-flow")
    pid = api.proposals.create("t", {"facts": [
        {"fact": "node", "id": "n-ref", "types": ["Character"], "name": "林晚",
         "props": {"flow_space_seniority": {"entered_at": "首夜"}}}]})
    api.confirm(pid)
    api.close()

    res = runner.invoke(app,
                        ["ext", "unmount", "infinite-flow", "-p", str(proj)])
    assert res.exit_code == 1
    assert "n-ref" in res.output and "引用" in res.output   # 拒绝原因完整呈现


def test_orphan_row_not_marked_stale(tmp_path):             # M-2 锚
    # 孤儿行（磁盘包已消失）：digest_matches 恒 None，不得再套
    # "schema 不一致，重新挂载后生效" 的 stale 文案误导用户去重挂
    proj = tmp_path / "proj"
    SnowelAPI.init_project(proj)
    write_ext(proj / "extensions")
    api = SnowelAPI.open(proj)
    api.mount_extension("wuxia")
    api.close()
    shutil.rmtree(proj / "extensions" / "wuxia")           # 孤儿化

    res = runner.invoke(app, ["ext", "list", "-p", str(proj)])
    assert res.exit_code == 0
    orphan = next(l for l in res.output.splitlines()
                  if l.startswith("wuxia"))
    assert "[孤儿]" in orphan
    assert "重新挂载后生效" not in res.output

    st = runner.invoke(app, ["ext", "status", "-p", str(proj)])
    assert st.exit_code == 0
    assert "异常" in st.output                              # 健康标注如常
    assert "重新挂载后生效" not in st.output
