# tests/writeback/test_extract.py
import json
from tests.conftest import FakeBackend
from snowel_core.writeback import mirror

EXTRACT_OK = json.dumps({
    "facts": [
        {"sensitivity": "low", "fact": {
            "fact": "node", "id": "n-rule", "types": ["Mechanism"],
            "name": "积分兑换", "props": {"mechanism": {"规则": "一积分换一命"}}}},
        {"sensitivity": "high", "fact": {
            "fact": "node", "id": "n-level", "types": ["Mechanism"],
            "name": "等级提升", "props": {"core": {"level": 3}}}},
        {"sensitivity": "low", "fact": {   # 修辞陷阱：必须被确定性后校转 high（数字）
            "fact": "node", "id": "n-metaphor", "types": ["Concept"],
            "name": "怒吼如高炮弹", "props": {"core": {"分贝": 120}}}},
    ],
    "appeared": ["hero"],
}, ensure_ascii=False)


def _prepare(api, tmp_path):
    from snowel_core.storage import db, events, projector
    with db.transaction(api._conn):
        events.append_event(api._conn, "proposal_confirmed", {
            "artifact_type": "t", "facts": [
                {"fact": "node", "id": "hero", "types": ["Character"],
                 "name": "林晚", "props": {}}]})
        projector.apply(api._conn)
    mirror.write_prose(api._conn, tmp_path, "ch1", "林晚攒积分。")


def test_extract_splits_sensitivity(api, tmp_path):  # TC-WB-06 / TC-PR-10 / D1
    _prepare(api, tmp_path)
    fake = FakeBackend([EXTRACT_OK])
    r = api.extract_and_writeback("ch1", backend=fake)
    # low（规则，无数字）→ 单条 auto_canonized 批量事件
    assert r["auto_event_seq"] is not None
    ev = api._conn.execute(
        "SELECT payload FROM events WHERE kind='auto_canonized'").fetchone()
    p = json.loads(ev["payload"])
    assert [f["id"] for f in p["facts"]] == ["n-rule"]
    assert p["source"] == {"chapter_id": "ch1", "hash": p["source"]["hash"]}
    assert p["appeared"] == ["hero"]
    # high（显式 high + 数字后校转 high）→ 提案队列，不自动入典
    assert r["proposal_id"] is not None
    prop = [dict(x) for x in api.proposals.list("pending")][0]
    ids = [f["id"] for f in json.loads(prop["payload"])["facts"]]
    assert ids == ["n-level", "n-metaphor"]
    # 提示词忽略修辞判据在场
    assert "修辞" in fake.calls[0]["prompt"]


def test_extract_requires_mirror(api, tmp_path):
    import pytest
    with pytest.raises(ValueError, match="镜像"):
        api.extract_and_writeback("ch1", backend=FakeBackend([]))


def test_extract_unmanaged_group_warns(api, tmp_path):  # TC-ON-03 消费面 + L1 接线
    _prepare(api, tmp_path)
    resp = json.dumps({"facts": [
        {"sensitivity": "low", "fact": {
            "fact": "node", "id": "n-x", "types": ["Concept"], "name": "x",
            "props": {"foo": {"any": "thing"}, "_schema_bad": "demo@x"}}}],
        "appeared": []}, ensure_ascii=False)
    r = api.extract_and_writeback("ch1", backend=FakeBackend([resp]))
    assert any("unmanaged" in w for w in r["warnings"])


def test_extract_tolerates_fenced_json(api, tmp_path):  # 真实模型常裹 ```json 围栏
    _prepare(api, tmp_path)
    fenced = "```json\n" + EXTRACT_OK + "\n```"
    r = api.extract_and_writeback("ch1", backend=FakeBackend([fenced]))
    assert r["auto_event_seq"] is not None   # 围栏剥壳后照常分级入典


def test_extract_bad_response_raises_structured(api, tmp_path):
    import pytest
    _prepare(api, tmp_path)
    with pytest.raises(ValueError, match="LLM 响应不是合法 JSON"):
        api.extract_and_writeback("ch1", backend=FakeBackend(["不是 JSON"]))
    with pytest.raises(ValueError, match="LLM 响应缺少 facts 键"):
        api.extract_and_writeback("ch1", backend=FakeBackend(['{"appeared": []}']))


def test_extract_version_mismatch_forces_high(api, tmp_path):  # L1 降级消费面：校验失败不自动入典
    _prepare(api, tmp_path)
    resp = json.dumps({"facts": [
        {"sensitivity": "low", "fact": {
            "fact": "node", "id": "n-bad", "types": ["Concept"], "name": "坏版本",
            "props": {"core": {"motivation": "守护", "lie": "独自承担",
                               "fear": "失去同伴", "arc": "从封闭到开放",
                               "_schema": "core@abc"}}}}],
        "appeared": []}, ensure_ascii=False)
    r = api.extract_and_writeback("ch1", backend=FakeBackend([resp]))
    assert r["auto_event_seq"] is None          # 强制 high：不进 auto_canonized
    n = api._conn.execute(
        "SELECT count(*) c FROM events WHERE kind='auto_canonized'").fetchone()["c"]
    assert n == 0
    assert r["proposal_id"] is not None         # 转进提案队列
    prop = [dict(x) for x in api.proposals.list("pending")][0]
    ids = [f["id"] for f in json.loads(prop["payload"])["facts"]]
    assert ids == ["n-bad"]
    assert any("畸形" in w for w in r["warnings"])  # L1 降级警告记录在案
