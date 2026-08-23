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
