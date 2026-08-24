# tests/shell/test_cli.py
import shutil

from typer.testing import CliRunner

from snowel.cli import app
from snowel_core.api import SnowelAPI

runner = CliRunner()

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


def test_export_seal_not_wired_exit_2(tmp_path):
    SnowelAPI.init_project(tmp_path)
    for cmd in (["export", "--project", str(tmp_path)],
                ["seal", "--project", str(tmp_path)]):
        res = runner.invoke(app, cmd)
        assert res.exit_code == 2
        assert "未接线" in res.output


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
