# src/snowel_core/writeback/mirror.py
import hashlib
import json
import sqlite3
from pathlib import Path

from ..storage import events, fts, projector
from ..storage.db import transaction


def _sha(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def prose_path(project_root: Path, chapter_id: str) -> Path:  # P5 约定
    return project_root / "chapters" / f"{chapter_id}.md"


def write_prose(conn: sqlite3.Connection, project_root: Path,
                chapter_id: str, content: str) -> int:
    """确认即写文件（C1）：文件落盘 + 登记哈希（事件+镜像），同一事务物化。"""
    f = prose_path(project_root, chapter_id)
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(content, encoding="utf-8")
    with transaction(conn):
        seq = events.append_event(conn, "prose_hash_registered", {
            "chapter_id": chapter_id, "path": str(f), "hash": _sha(content)})
        projector.apply(conn)
        conn.execute("UPDATE chapter_prose SET prose=? WHERE chapter_id=?",
                     (content, chapter_id))  # P1：全文由 writeback 层水化
        fts.refresh(conn)  # apply 时 prose 列尚未水化，水化后同事务重灌，首写即可检
    return seq


def reconcile(conn: sqlite3.Connection, project_root: Path,
              dry_run: bool = False) -> list[dict]:
    """D8 对账：文件是真相源，哈希不一致以文件为准重灌镜像。

    dry_run=True（Web /api/reconcile 只读预演）：只收集 changed/missing
    清单，两条写分支（镜像重灌 + 事件 + FTS 刷新）全部跳过——只读会话查
    对账状态不得绕过租约写共享库（F2）；清单与 dry_run=False 逐项一致。
    """
    changes = []
    for r in conn.execute("SELECT chapter_id, path, hash, prose FROM chapter_prose"):
        f = Path(r["path"])
        if not f.exists():
            changes.append({"chapter_id": r["chapter_id"], "status": "missing_file"})
            continue
        content = f.read_text(encoding="utf-8")
        new_hash = _sha(content)
        if new_hash == r["hash"]:
            if r["prose"] == "" and not dry_run:  # rebuild 后镜像全文丢失：
                # 纯数据修复，哈希未变不写事件
                with transaction(conn):
                    conn.execute(
                        "UPDATE chapter_prose SET prose=? WHERE chapter_id=?",
                        (content, r["chapter_id"]))
                    fts.refresh(conn)  # 水化后同事务重灌，修复后立即可检
            continue  # 已登记写入短路（TC-WB-02）：核心代写的文件不再触发
        if not dry_run:
            with transaction(conn):
                events.append_event(conn, "prose_external_change", {
                    "chapter_id": r["chapter_id"], "path": str(f),
                    "old_hash": r["hash"], "new_hash": new_hash})
                projector.apply(conn)
                conn.execute("UPDATE chapter_prose SET prose=? WHERE chapter_id=?",
                             (content, r["chapter_id"]))
                fts.refresh(conn)  # apply 时 prose 列尚未水化，水化后同事务重灌
        changes.append({"chapter_id": r["chapter_id"], "status": "external_change"})
    return changes
