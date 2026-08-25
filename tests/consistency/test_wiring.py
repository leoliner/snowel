# tests/consistency/test_wiring.py
import json
from snowel_core.consistency import engine, wiring
from snowel_core.storage import db, events, projector
from snowel_core.writeback import mirror


def _seed_level(conn, level=3):
    with db.transaction(conn):
        events.append_event(conn, "proposal_confirmed", {
            "artifact_type": "t", "facts": [
                {"fact": "node", "id": "m1", "types": ["Mechanism"],
                 "name": "积分兑换", "props": {"mechanism": {"level": level}}}]})
    projector.apply(conn)


def test_confirm_runs_full_cascade(api):  # TC-CC-01/04 接线面
    _seed_level(api._conn)
    pid = api.proposals.create("t", {"facts": [
        {"fact": "node", "id": "m1", "types": ["Mechanism"],
         "name": "积分兑换", "props": {"mechanism": {"level": 5}}}]})
    seq = api.confirm(pid)
    assert seq > 0
    last = api.last_cascade()
    assert last["tier"] == "full"
    assert any(v["rule"] == "contradiction" for v in last["violations"])
    assert last["cascade_proposal_id"] is not None      # diff 修订提案已入队


def test_extract_runs_light_cascade(api, tmp_path):  # auto 入典轻量
    mirror.write_prose(api._conn, tmp_path, "ch1", "林晚攒积分。")
    resp = json.dumps({"facts": [
        {"sensitivity": "low", "fact": {
            "fact": "node", "id": "m2", "types": ["Mechanism"],
            "name": "新机制", "props": {}}}], "appeared": []},
        ensure_ascii=False)
    from tests.conftest import FakeBackend
    r = api.extract_and_writeback("ch1", backend=FakeBackend([resp]))
    assert r["cascade"]["tier"] == "light"
    assert isinstance(r["cascade"]["violations"], list)


def test_cascade_check_readonly_preview(api):  # 独立预演门面
    _seed_level(api._conn)
    out = api.cascade_check([
        {"fact": "node", "id": "m1", "types": ["Mechanism"], "name": "积分兑换",
         "props": {"mechanism": {"level": 7}}}])
    assert any(v["rule"] == "contradiction" for v in out["violations"])
    assert len(api.proposals.list("pending")) == 0     # 预演不入队


def test_register_overwrite_retires_old_tiers(core_conn):  # E1 覆盖（T2 挂账补钉）
    calls = []

    def fn_full(change, conn):
        calls.append("full"); return []

    def fn_light(change, conn):
        calls.append("light"); return []

    engine.register("probe", fn_full, tiers=("full",))
    engine.register("probe", fn_light, tiers=("light",))  # 同名重注册：换 fn 换档
    engine.run(core_conn, [{"kind": "node", "fact": {"id": "x"}, "seq": 1}], "full")
    assert calls == []                                     # 旧档位撤尽，旧 fn 不再执行
    engine.run(core_conn, [{"kind": "node", "fact": {"id": "x"}, "seq": 1}], "light")
    assert calls == ["light"]                              # 新 fn 只在新档执行
