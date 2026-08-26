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
                {"fact": "node", "id": "ch1", "types": ["Chapter"],
                 "name": "第一章", "props": {}},
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


def test_extract_zero_facts_preserves_appeared(api, tmp_path):  # L15：零事实章 appeared 保真
    _prepare(api, tmp_path)
    resp = json.dumps({"facts": [], "appeared": ["hero"]}, ensure_ascii=False)
    r = api.extract_and_writeback("ch1", backend=FakeBackend([resp]))
    assert r["proposal_id"] is None and r["auto_event_seq"] is None
    assert r["appeared"] == ["hero"]            # 零事实路径不丢 appeared（回归锚）


def test_low_importance_routes_small_model(api, tmp_path):  # TC-RT-05 / §6.3
    from snowel_core.storage import config
    _prepare(api, tmp_path)
    seq = api.set_chapter_importance("ch1", "low")
    # R4：元数据改动必须事件化——chapter_importance_set 载荷落日志、投影更新 props
    p = json.loads(api._conn.execute(
        "SELECT payload FROM events WHERE seq=?", (seq,)).fetchone()["payload"])
    assert p == {"chapter_id": "ch1", "importance": "low"}
    assert json.loads(api._conn.execute(
        "SELECT props FROM nodes WHERE id='ch1'").fetchone()["props"])["importance"] == "low"
    config.set(api._conn, "extraction.small_model", "qwen-small")
    fake = FakeBackend([EXTRACT_OK])
    r = api.extract_and_writeback("ch1", backend=fake)
    assert fake.calls[-1]["model"] == "qwen-small"   # 成本控制生效
    # 分级语义不变：high→提案、low→auto_canonized（既有断言样式复跑）
    assert r["proposal_id"] is not None
    assert r["auto_event_seq"] is not None
    assert "修辞" in fake.calls[-1]["prompt"]       # 提示词原样，仅换模型


def test_small_model_unset_keeps_default(api, tmp_path):  # 向后兼容
    _prepare(api, tmp_path)
    # 未配置 extraction.small_model → model=None，与现状逐字节一致
    fake = FakeBackend([EXTRACT_OK])
    api.extract_and_writeback("ch1", backend=fake)
    assert fake.calls[-1]["model"] is None
    # 标记 normal 同样不路由（只有 == "low" 命中）
    api.set_chapter_importance("ch1", "normal")
    fake2 = FakeBackend([EXTRACT_OK])
    api.extract_and_writeback("ch1", backend=fake2)
    assert fake2.calls[-1]["model"] is None


def test_explicit_model_overrides_small_model(api, tmp_path):
    # 路由优先级：显式 model 参数 > extraction.small_model 配置 > None
    from snowel_core.storage import config
    _prepare(api, tmp_path)
    api.set_chapter_importance("ch1", "low")
    config.set(api._conn, "extraction.small_model", "qwen-small")
    fake = FakeBackend([EXTRACT_OK])
    api.extract_and_writeback("ch1", backend=fake, model="qwen-max")
    assert fake.calls[-1]["model"] == "qwen-max"


def test_set_chapter_importance_validates(api, tmp_path):
    _prepare(api, tmp_path)
    import pytest
    with pytest.raises(ValueError, match="chapter_importance_set|不存在|只允许"):
        api.set_chapter_importance("nope", "low")       # 章节节点不存在
    with pytest.raises(ValueError, match="只允许"):
        api.set_chapter_importance("ch1", "high")       # 非法取值
    with pytest.raises(ValueError, match="Chapter"):
        api.set_chapter_importance("hero", "low")       # 非 Chapter 节点


def test_extract_many_collects_per_chapter_failures(api, tmp_path):  # R3：省操作不省调用
    _prepare(api, tmp_path)
    fake = FakeBackend([EXTRACT_OK])
    results = api.extract_many(["ch1", "ch2"], fake)
    assert results[0]["chapter_id"] == "ch1" and results[0]["auto_event_seq"] is not None
    assert results[1]["chapter_id"] == "ch2" and "error" in results[1]  # 失败不静默消失
    assert "镜像" in results[1]["error"]
