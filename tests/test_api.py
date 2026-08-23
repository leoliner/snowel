# tests/test_api.py
from snowel_core import api as sapi
from snowel_core.storage import db, lease

def test_lease_single_writer(tmp_path):
    a = db.connect(tmp_path / "s.db"); db.migrate(a)
    assert lease.acquire(a, "web-1") is True
    b = db.connect(tmp_path / "s.db")
    assert lease.acquire(b, "cli-1") is False        # 活租约拒绝第二写者
    lease.release(a, "web-1")
    assert lease.acquire(b, "cli-1") is True
    a.close(); b.close()

def test_lease_recovers_after_holder_death(tmp_path):  # C10 存活检测
    a = db.connect(tmp_path / "s.db"); db.migrate(a)
    assert lease.acquire(a, "web-1", stale_after=0.05) is True
    a.close()                                        # 模拟崩溃：不再心跳
    import time; time.sleep(0.1)
    b = db.connect(tmp_path / "s.db")
    assert lease.acquire(b, "cli-1", stale_after=0.05) is True  # 过期租约可夺
    b.close()

def test_api_facade_end_to_end(tmp_path):
    core = sapi.SnowelAPI.init_project(tmp_path / "book")
    pid = core.proposals.create("scene", {"facts": [
        {"fact": "node", "id": "n1", "types": ["Character"], "name": "林晚",
         "props": {"core": {"motivation": "活下去", "lie": "x", "fear": "y", "arc": "z"}}}]})
    core.proposals.confirm(pid)
    n = core.get_node("n1")
    assert n["name"] == "林晚"
    assert core.find_nodes(name="林晚")[0]["id"] == "n1"
    core.rebuild()
    assert core.get_node("n1")["name"] == "林晚"     # rebuild 后状态一致
    core.close()
