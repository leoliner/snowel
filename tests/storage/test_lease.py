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
