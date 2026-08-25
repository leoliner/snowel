import sqlite3
from contextlib import contextmanager
from pathlib import Path

SCHEMA = Path(__file__).with_name("schema.sql").read_text(encoding="utf-8")

def connect(path) -> sqlite3.Connection:
    # check_same_thread=False：W6 Web SSE 流经 iterate_in_threadpool 在线程池
    # 迭代 core 生成器（FastAPI 模式），连接须可跨线程使用（sqlite 序列化模式
    # threadsafety=3 保证同连接并发安全）；MCP/CLI 单线程路径行为不变。
    # fail-fast：threadsafety<3 的构建上跨线程共享连接会静默损坏数据，显式拒绝
    if sqlite3.threadsafety < 3:
        raise RuntimeError(
            f"本构建 sqlite3.threadsafety={sqlite3.threadsafety}，"
            "check_same_thread=False 需要序列化模式（3）构建")
    conn = sqlite3.connect(path, isolation_level=None,
                           check_same_thread=False)  # 手动事务
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn

def migrate(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA)

@contextmanager
def transaction(conn: sqlite3.Connection):
    conn.execute("BEGIN IMMEDIATE")
    try:
        yield conn
    except BaseException:
        conn.execute("ROLLBACK")
        raise
    else:
        conn.execute("COMMIT")

def backup(conn: sqlite3.Connection, out_path) -> None:
    out = Path(out_path)
    if out.exists():
        raise FileExistsError(f"备份文件已存在：{out}")
    conn.execute("VACUUM INTO ?", (str(out),))
