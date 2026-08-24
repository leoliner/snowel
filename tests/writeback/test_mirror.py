# tests/writeback/test_mirror.py
import hashlib
from snowel_core.storage import db, events, queries
from snowel_core.writeback import mirror


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def events_by_kind(api, kind):
    r = api._conn.execute(
        "SELECT * FROM events WHERE kind=? ORDER BY seq DESC", (kind,)).fetchone()
    r = dict(r); r["payload_hash"] = __import__("json").loads(r["payload"])["hash"]
    return r


def test_write_prose_registers_file_and_event(api, tmp_path):
    seq = mirror.write_prose(api._conn, tmp_path, "ch1", "第一章正文")
    f = tmp_path / "chapters" / "ch1.md"
    assert f.read_text(encoding="utf-8") == "第一章正文"
    row = events_by_kind(api, "prose_hash_registered")
    assert row["seq"] == seq
    assert _sha("第一章正文") in (row["payload_hash"])
    prose = api._conn.execute(
        "SELECT * FROM chapter_prose WHERE chapter_id='ch1'").fetchone()
    assert prose["hash"] == _sha("第一章正文") and prose["path"] == str(f)


def test_reconcile_rebuilds_mirror_from_file(api, tmp_path):  # TC-WB-05
    mirror.write_prose(api._conn, tmp_path, "ch1", "旧正文")
    (tmp_path / "chapters" / "ch1.md").write_text("新正文（外部编辑）", encoding="utf-8")
    changes = mirror.reconcile(api._conn, tmp_path)
    assert changes == [{"chapter_id": "ch1", "status": "external_change"}]
    ev = api._conn.execute(
        "SELECT payload FROM events WHERE kind='prose_external_change'").fetchone()
    import json
    p = json.loads(ev["payload"])
    assert p == {"chapter_id": "ch1",
                 "path": str(tmp_path / "chapters" / "ch1.md"),
                 "old_hash": _sha("旧正文"), "new_hash": _sha("新正文（外部编辑）")}
    prose = api._conn.execute(
        "SELECT prose, hash FROM chapter_prose WHERE chapter_id='ch1'").fetchone()
    assert prose["prose"] == "新正文（外部编辑）"      # 镜像以文件为准重灌


def test_reconcile_shortcircuits_registered_hash(api, tmp_path):  # TC-WB-02 基础
    mirror.write_prose(api._conn, tmp_path, "ch1", "正文")
    assert mirror.reconcile(api._conn, tmp_path) == []   # 哈希已登记 → 短路
    n = api._conn.execute(
        "SELECT count(*) c FROM events WHERE kind='prose_external_change'"
    ).fetchone()["c"]
    assert n == 0


def test_reconcile_reports_missing_file(api, tmp_path):
    mirror.write_prose(api._conn, tmp_path, "ch1", "正文")
    (tmp_path / "chapters" / "ch1.md").unlink()
    assert mirror.reconcile(api._conn, tmp_path) == [
        {"chapter_id": "ch1", "status": "missing_file"}]


def test_write_prose_hydrates_prose_column(api, tmp_path):
    mirror.write_prose(api._conn, tmp_path, "ch1", "第一章正文")
    prose = api._conn.execute(
        "SELECT prose FROM chapter_prose WHERE chapter_id='ch1'").fetchone()
    assert prose["prose"] == "第一章正文"   # 事务内水化，下游读镜像即得全文


def test_reconcile_repairs_empty_prose_without_events(api, tmp_path):
    mirror.write_prose(api._conn, tmp_path, "ch1", "正文")
    api._conn.execute(  # 模拟 rebuild：事件重放后 prose 置空、哈希仍登记
        "UPDATE chapter_prose SET prose='' WHERE chapter_id='ch1'")
    n_before = api._conn.execute("SELECT count(*) c FROM events").fetchone()["c"]
    assert mirror.reconcile(api._conn, tmp_path) == []   # 纯数据修复不报变更
    prose = api._conn.execute(
        "SELECT prose FROM chapter_prose WHERE chapter_id='ch1'").fetchone()
    assert prose["prose"] == "正文"      # P1：全文靠对账从文件重灌
    n_after = api._conn.execute("SELECT count(*) c FROM events").fetchone()["c"]
    assert n_after == n_before           # 哈希未变，不追加事件

