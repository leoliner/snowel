# src/snowel_core/storage/lease.py
import time

def _now() -> float:
    return time.time()

def acquire(conn, holder: str, stale_after: float = 30.0) -> bool:
    from .db import transaction
    with transaction(conn):
        row = conn.execute("SELECT * FROM lease WHERE id=1").fetchone()
        if row and row["holder"] != holder and row["heartbeat_ts"] > _now() - stale_after:
            return False                             # 他人活租约
        conn.execute(
            "INSERT INTO lease(id, holder, heartbeat_ts) VALUES(1,?,?) "
            "ON CONFLICT(id) DO UPDATE SET holder=excluded.holder, "
            "heartbeat_ts=excluded.heartbeat_ts", (holder, _now()))
        return True

def renew(conn, holder: str) -> bool:
    cur = conn.execute("UPDATE lease SET heartbeat_ts=? WHERE id=1 AND holder=?",
                       (_now(), holder))
    return cur.rowcount == 1

def release(conn, holder: str) -> None:
    conn.execute("DELETE FROM lease WHERE id=1 AND holder=?", (holder,))
