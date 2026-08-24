# tests/api/test_open.py
import sqlite3

import pytest

from snowel_core.api import ProjectNotFoundError, SnowelAPI

# 旧基线 schema 子集（分支前存量库）：仅首计划四表，缺本分支新增的
# node_fts/prose_fts/chapter_prose/config/retrieval_audit 等表
_LEGACY_SCHEMA = """
CREATE TABLE IF NOT EXISTS events(
  seq    INTEGER PRIMARY KEY AUTOINCREMENT,
  ts     TEXT NOT NULL,
  kind   TEXT NOT NULL,
  payload TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS nodes(
  id           TEXT PRIMARY KEY,
  types        TEXT NOT NULL,
  name         TEXT NOT NULL,
  completeness TEXT NOT NULL DEFAULT 'draft',
  props        TEXT NOT NULL DEFAULT '{}',
  story_order  INTEGER,
  active       INTEGER NOT NULL DEFAULT 1,
  created_event INTEGER NOT NULL REFERENCES events(seq)
);
CREATE TABLE IF NOT EXISTS edges(
  id            TEXT PRIMARY KEY,
  src           TEXT NOT NULL,
  dst           TEXT NOT NULL,
  kind          TEXT NOT NULL,
  props         TEXT NOT NULL DEFAULT '{}',
  valid_from    INTEGER,
  valid_until   INTEGER,
  created_event INTEGER NOT NULL REFERENCES events(seq)
);
CREATE TABLE IF NOT EXISTS proposals(
  id         TEXT PRIMARY KEY,
  kind       TEXT NOT NULL,
  payload    TEXT NOT NULL,
  status     TEXT NOT NULL,
  stale_hint TEXT,
  created_ts TEXT NOT NULL
);
"""


def _legacy_project(root):
    """手工建旧 schema 库（不 import schema.sql）：模拟缺新表的存量项目。"""
    root.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(root / "snowel.db", isolation_level=None)
    conn.executescript(_LEGACY_SCHEMA)
    conn.close()


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


def test_open_migrates_legacy_db(tmp_path):
    # 旧库缺 node_fts 等新表：open() 补迁移（schema 全 IF NOT EXISTS，幂等），不抛 OperationalError
    _legacy_project(tmp_path)
    api = SnowelAPI.open(tmp_path)
    try:
        assert api.find_nodes() == []
    finally:
        api.close()


def test_open_legacy_db_confirm_reaches_fts_refresh(tmp_path):
    # 回归：旧库首次 confirm 会走到 apply 尾部 fts.refresh（此前对新表 DELETE 即崩）
    _legacy_project(tmp_path)
    api = SnowelAPI.open(tmp_path)
    try:
        pid = api.proposals.create("t", {"facts": [
            {"fact": "node", "id": "n1", "types": ["Concept"],
             "name": "轮回规则", "props": {}}]})
        api.confirm(pid)
        assert api.find_nodes(name="轮回规则")
    finally:
        api.close()
