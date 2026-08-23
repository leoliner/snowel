import sqlite3
import pytest
from snowel_core.storage import db

def test_migrate_creates_all_tables(tmp_path):
    conn = db.connect(tmp_path / "snowel.db")
    db.migrate(conn)
    names = {r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'")}
    assert {"events", "nodes", "edges", "alias", "tracks",
            "proposals", "checkpoint", "lease"} <= names
    conn.close()

def test_migrate_is_idempotent(tmp_path):
    conn = db.connect(tmp_path / "snowel.db")
    db.migrate(conn); db.migrate(conn)
    conn.close()

def test_transaction_commits_and_rolls_back(tmp_path):
    conn = db.connect(tmp_path / "snowel.db"); db.migrate(conn)
    with db.transaction(conn) as tx:
        tx.execute("INSERT INTO events(ts, kind, payload) VALUES('t','x','{}')")
    with pytest.raises(RuntimeError):
        with db.transaction(conn) as tx:
            tx.execute("INSERT INTO events(ts, kind, payload) VALUES('t','y','{}')")
            raise RuntimeError("boom")
    assert conn.execute("SELECT COUNT(*) FROM events").fetchone()[0] == 1
    conn.close()
