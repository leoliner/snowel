# tests/api/test_open.py
import pytest

from snowel_core.api import ProjectNotFoundError, SnowelAPI


def test_open_missing_project_raises(tmp_path):
    with pytest.raises(ProjectNotFoundError, match="snowel.db"):
        SnowelAPI.open(tmp_path)


def test_open_missing_does_not_create_db(tmp_path):
    with pytest.raises(ProjectNotFoundError):
        SnowelAPI.open(tmp_path)
    assert not (tmp_path / "snowel.db").exists()  # 不得静默建空库


def test_open_existing_project(tmp_path):
    SnowelAPI.init_project(tmp_path)
    api = SnowelAPI.open(tmp_path)
    try:
        assert api.find_nodes() == []
    finally:
        api.close()
