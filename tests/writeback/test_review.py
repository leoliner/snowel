# tests/writeback/test_review.py
import json
from snowel_core.storage import db, events, projector
from snowel_core.writeback import mirror, review


def _auto_rule(api, tmp_path):
    with db.transaction(api._conn):
        events.append_event(api._conn, "auto_canonized", {
            "facts": [{"fact": "node", "id": "n-rule", "types": ["Mechanism"],
                       "name": "一命换积分", "props": {}}],
            "source": {"chapter_id": "ch1", "hash": "h"}, "appeared": []})
        projector.apply(api._conn)
    mirror.write_prose(api._conn, tmp_path, "ch1",
                       "规则很简单。\n\n林晚想起点数：一命换积分。")


def test_list_auto_marks_retracted(api, tmp_path):  # TC-WB-07 前置
    _auto_rule(api, tmp_path)
    items = review.list_auto(api._conn)
    assert items == [{"event_seq": 1, "fact_id": "n-rule", "kind": "node",
                      "name_or_id": "一命换积分", "source_chapter": "ch1",
                      "retracted": False}]
    review.reject_auto(api._conn, [("node", "n-rule")], reason="抽取错了")
    items = review.list_auto(api._conn)
    assert items[0]["retracted"] is True


def test_reject_auto_retracts_and_reports_references(api, tmp_path):  # TC-WB-07
    _auto_rule(api, tmp_path)
    r = review.reject_auto(api._conn, [("node", "n-rule")], reason="抽取错了")
    assert r["retracted"] == 1
    assert api.get_node("n-rule")["active"] == 0          # 物化图立即失效（C2）
    ev = api._conn.execute(
        "SELECT payload FROM events WHERE kind='retraction'").fetchone()
    p = json.loads(ev["payload"])
    assert p["target"] == "node" and p["target_id"] == "n-rule"
    assert p["reason"] == "抽取错了"
    assert r["referencing_paragraphs"] and \
        r["referencing_paragraphs"][0]["chapter_id"] == "ch1"  # 引用提示，不改文
