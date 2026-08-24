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
CREATE TABLE IF NOT EXISTS alias(
  node_id TEXT NOT NULL REFERENCES nodes(id),
  alias   TEXT NOT NULL,
  source  TEXT NOT NULL,
  PRIMARY KEY (node_id, alias)
);
CREATE TABLE IF NOT EXISTS tracks(
  id         TEXT PRIMARY KEY,
  name       TEXT NOT NULL,
  definition TEXT NOT NULL,
  frozen     INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS proposals(
  id         TEXT PRIMARY KEY,
  kind       TEXT NOT NULL,
  payload    TEXT NOT NULL,
  status     TEXT NOT NULL,
  stale_hint TEXT,
  created_ts TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS checkpoint(
  id  INTEGER PRIMARY KEY CHECK (id = 1),
  seq INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS lease(
  id           INTEGER PRIMARY KEY CHECK (id = 1),
  holder       TEXT NOT NULL,
  heartbeat_ts REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS config(
  key   TEXT PRIMARY KEY,
  value TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS chapter_prose(
  chapter_id    TEXT PRIMARY KEY,
  path          TEXT NOT NULL,
  hash          TEXT NOT NULL,
  prose         TEXT NOT NULL DEFAULT '',
  updated_event INTEGER NOT NULL REFERENCES events(seq)
);
CREATE VIRTUAL TABLE IF NOT EXISTS node_fts USING fts5(
  node_id UNINDEXED, text);
CREATE VIRTUAL TABLE IF NOT EXISTS prose_fts USING fts5(
  chapter_id UNINDEXED, para_idx UNINDEXED, text);
CREATE TABLE IF NOT EXISTS prose_paragraph(
  -- L10：段落原文侧表——prose_fts 存分词串（MATCH 需要），原文从此表取
  chapter_id TEXT NOT NULL,
  para_idx   INTEGER NOT NULL,
  text       TEXT NOT NULL,
  PRIMARY KEY(chapter_id, para_idx)
);
CREATE TABLE IF NOT EXISTS retrieval_audit(
  id       INTEGER PRIMARY KEY AUTOINCREMENT,
  ts       TEXT NOT NULL,
  strategy TEXT NOT NULL,
  dry_run  INTEGER NOT NULL DEFAULT 0,
  locate   TEXT,
  bundle   TEXT NOT NULL
);
