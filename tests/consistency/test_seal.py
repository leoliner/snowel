# tests/consistency/test_seal.py
import json
import pytest
from snowel_core.consistency.seal import SealedVolumeError
from snowel_core.storage import db, events, projector


def _seed_two_volumes(api):
    with db.transaction(api._conn):
        events.append_event(api._conn, "proposal_confirmed", {
            "artifact_type": "t", "facts": [
                {"fact": "node", "id": "v1", "types": ["Volume"], "name": "卷一",
                 "props": {"address": {"volume": 1, "chapter": 0, "scene": 0,
                                       "beat": 0}}},
                {"fact": "node", "id": "v2", "types": ["Volume"], "name": "卷二",
                 "props": {"address": {"volume": 2, "chapter": 0, "scene": 0,
                                       "beat": 0}}},
                {"fact": "node", "id": "m1", "types": ["Mechanism"],
                 "name": "积分兑换", "props": {}},
                {"fact": "node", "id": "c3", "types": ["Chapter"], "name": "第3章",
                 "props": {"address": {"volume": 1, "chapter": 3, "scene": 0,
                                       "beat": 0}}}]})
    projector.apply(api._conn)


def test_seal_and_freeze_line(api):  # TC-CC-06/08
    _seed_two_volumes(api)
    assert api.seal("v1") > 0
    ev = api._conn.execute(
        "SELECT payload FROM events WHERE kind='volume_sealed'").fetchone()
    assert json.loads(ev["payload"]) == {"volume_id": "v1"}
    # 卷一内设定（m1 挂 address.volume=1 后被拦；此处用 c3 章节——补 address）
    pid = api.proposals.create("t", {"facts": [
        {"fact": "node", "id": "m1", "types": ["Mechanism"], "name": "积分兑换",
         "props": {"address": {"volume": 1, "chapter": 0, "scene": 0,
                               "beat": 0}, "mechanism": {"level": 9}}}]})
    with pytest.raises(Exception, match="封卷"):
        api.confirm(pid)                                  # 冻结线拦截
    with pytest.raises(ValueError, match="已封"):
        api.seal("v1")                                    # 重复封卷拒绝


def test_unsealed_volume_not_blocked(api):  # TC-CC-05
    _seed_two_volumes(api)
    pid = api.proposals.create("t", {"facts": [
        {"fact": "node", "id": "m1", "types": ["Mechanism"], "name": "积分兑换",
         "props": {"address": {"volume": 2, "chapter": 0, "scene": 0,
                               "beat": 0}, "mechanism": {"level": 9}}}]})
    assert api.confirm(pid) > 0                           # 卷二未封，不拦


def test_extract_auto_blocked_in_sealed_volume(api, tmp_path):  # 冻结线：auto 入典拦截
    from snowel_core.writeback import mirror
    _seed_two_volumes(api)
    pid = api.proposals.create("t", {"facts": [
        {"fact": "node", "id": "m1", "types": ["Mechanism"], "name": "积分兑换",
         "props": {"address": {"volume": 1, "chapter": 0, "scene": 0,
                               "beat": 0}}}]})
    api.confirm(pid)  # m1 落盘归属卷一（数字后校会把带数字 props 的 low 事实抬成
    # high，low 事实不能携带地址——冻结线经存盘归属卷命中）
    api.seal("v1")
    mirror.write_prose(api._conn, tmp_path, "c3", "林晚攒积分，第3章正文。")
    resp = json.dumps({"facts": [
        {"sensitivity": "low", "fact": {
            "fact": "node", "id": "m1", "types": ["Mechanism"],
            "name": "积分兑换",
            "props": {"mechanism": {"规则": "一命换两命"}}}}],
        "appeared": []}, ensure_ascii=False)
    from tests.conftest import FakeBackend
    with pytest.raises(SealedVolumeError, match="封卷"):
        api.extract_and_writeback("c3", backend=FakeBackend([resp]))
    assert api._conn.execute(
        "SELECT 1 FROM events WHERE kind='auto_canonized'").fetchone() is None


def test_confirm_blocked_after_retract_revival(api):  # 冻结线：撤回复活逃逸（confirm 路径）
    _seed_two_volumes(api)
    pid = api.proposals.create("t", {"facts": [
        {"fact": "node", "id": "m1", "types": ["Mechanism"], "name": "积分兑换",
         "props": {"address": {"volume": 1, "chapter": 0, "scene": 0,
                               "beat": 0}}}]})
    api.confirm(pid)                                  # m1 落盘归属卷一
    api.seal("v1")
    with db.transaction(api._conn):
        events.append_event(api._conn, "retraction",
                            {"target": "node", "target_id": "m1"})
    projector.apply(api._conn)  # C11 撤回：active=0，props（含 address）保留
    pid2 = api.proposals.create("t", {"facts": [
        {"fact": "node", "id": "m1", "types": ["Mechanism"], "name": "积分兑换",
         "props": {"mechanism": {"level": 9}}}]})     # 无 address：逃逸点
    with pytest.raises(SealedVolumeError, match="封卷"):
        api.confirm(pid2)  # 撤回前存盘地址仍命中已封卷——不得静默复活改写


def test_extract_blocked_after_retract_revival(api, tmp_path):  # 冻结线：撤回复活逃逸（extract 路径）
    from snowel_core.writeback import mirror
    _seed_two_volumes(api)
    pid = api.proposals.create("t", {"facts": [
        {"fact": "node", "id": "m1", "types": ["Mechanism"], "name": "积分兑换",
         "props": {"address": {"volume": 1, "chapter": 0, "scene": 0,
                               "beat": 0}}}]})
    api.confirm(pid)                                  # m1 落盘归属卷一
    api.seal("v1")
    with db.transaction(api._conn):
        events.append_event(api._conn, "retraction",
                            {"target": "node", "target_id": "m1"})
    projector.apply(api._conn)  # C11 撤回：active=0，props（含 address）保留
    mirror.write_prose(api._conn, tmp_path, "c3", "林晚攒积分，第3章正文。")
    resp = json.dumps({"facts": [
        {"sensitivity": "low", "fact": {
            "fact": "node", "id": "m1", "types": ["Mechanism"],
            "name": "积分兑换",
            "props": {"mechanism": {"规则": "一命换两命"}}}}],  # 无数字、无 address
        "appeared": []}, ensure_ascii=False)
    from tests.conftest import FakeBackend
    with pytest.raises(SealedVolumeError, match="封卷"):
        api.extract_and_writeback("c3", backend=FakeBackend([resp]))
    assert api._conn.execute(
        "SELECT 1 FROM events WHERE kind='auto_canonized'").fetchone() is None


def test_auto_retraction_ignores_freeze(api, tmp_path):  # TC-WB-08 后半
    _seed_two_volumes(api)
    pid = api.proposals.create("t", {"facts": [
        {"fact": "node", "id": "m1", "types": ["Mechanism"],
         "name": "一命换积分",
         "props": {"address": {"volume": 1, "chapter": 0, "scene": 0,
                               "beat": 0}}}]})
    api.confirm(pid)
    api.seal("v1")
    from snowel_core.writeback import review
    r = review.reject_auto(api._conn, [("node", "m1")])  # C11：否决不受冻结线
    assert r["retracted"] == 1
