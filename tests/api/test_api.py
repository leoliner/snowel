import shutil

import pytest

from snowel_core import api as sapi
from snowel_core.api import SnowelAPI

def test_api_facade_end_to_end(tmp_path):
    core = sapi.SnowelAPI.init_project(tmp_path / "book")
    pid = core.proposals.create("scene", {"facts": [
        {"fact": "node", "id": "n1", "types": ["Character"], "name": "林晚",
         "props": {"core": {"motivation": "活下去", "lie": "x", "fear": "y", "arc": "z"}}}]})
    core.proposals.confirm(pid)
    n = core.get_node("n1")
    assert n["name"] == "林晚"
    assert core.find_nodes(name="林晚")[0]["id"] == "n1"
    core.rebuild()
    assert core.get_node("n1")["name"] == "林晚"     # rebuild 后状态一致
    core.close()


def test_backup_roundtrip_equivalent(tmp_path):
    api = SnowelAPI.init_project(tmp_path)
    pid = api.proposals.create("scene", {"facts": [
        {"fact": "node", "id": "n1", "types": ["Character"],
         "name": "林晚", "props": {}}]})
    api.proposals.confirm(pid)
    out = tmp_path / "b.db"
    api.backup(out)
    restore = tmp_path / "restore"
    restore.mkdir()
    shutil.copy(out, restore / "snowel.db")
    api2 = SnowelAPI.open(restore)
    try:
        assert api2.graph_stats() == api.graph_stats()
        assert [r["status"] for r in api2.proposals.list()] == ["confirmed"]
    finally:
        api2.close()
    api.close()


def test_backup_refuses_overwrite(tmp_path):
    api = SnowelAPI.init_project(tmp_path)
    out = tmp_path / "b.db"
    out.write_bytes(b"x")
    with pytest.raises(FileExistsError):
        api.backup(out)
    api.close()
