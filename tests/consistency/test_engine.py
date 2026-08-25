# tests/consistency/test_engine.py
from snowel_core.api import SnowelAPI
from snowel_core.consistency import engine


def test_run_aggregates_and_dedupes(core_conn):
    seen = []

    def rule_a(change, conn):
        seen.append(change["kind"])
        return [{"level": "minor", "rule": "a", "message": "m",
                 "refs": [change["fact"].get("id", "?")] * 1}]

    def rule_b(change, conn):
        return [{"level": "major", "rule": "b", "message": "m", "refs": ["x"]}]

    engine.register("test_a", rule_a, tiers=("full", "light"))
    engine.register("test_b", rule_b, tiers=("full",))
    vs = engine.run(core_conn, [
        {"kind": "node", "fact": {"id": "n1"}, "seq": 1},
        {"kind": "node", "fact": {"id": "n1"}, "seq": 2}], "light")
    assert {v["rule"] for v in vs} == {"a"}          # light 不含 b
    vs2 = engine.run(core_conn, [
        {"kind": "node", "fact": {"id": "n1"}, "seq": 3}], "full")
    assert {v["rule"] for v in vs2} == {"a", "b"}


def test_diff_proposal_creates_cascade_revision(core_conn):
    # brief 原文签名 (api, core_conn)：两 fixture 分属两库（conftest 明示"两库互不影响"），
    # 跨库读提案恒 None——计划缺陷，最小修正为在 core_conn 库上构造 API，断言逐字保留。
    api = SnowelAPI(core_conn)
    pid = engine.diff_proposal(core_conn, [
        {"level": "major", "rule": "contradiction", "message": "等级冲突",
         "refs": ["m1"], "detail": {"node_id": "m1", "key": "mechanism_level",
                                     "old": 3, "new": 5}}], source_seq=9)
    row = api.proposals.get(pid)
    assert row["kind"] == "cascade_revision"
    import json
    p = json.loads(row["payload"])
    assert p["conflicts"][0]["old"] == 3 and p["source_change_seq"] == 9
    assert engine.diff_proposal(core_conn, [], source_seq=1) is None
