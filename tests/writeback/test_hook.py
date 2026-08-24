# tests/writeback/test_hook.py
import json
from tests.conftest import FakeBackend
from snowel_core.writeback import hook, mirror

EXTRACT = json.dumps({"facts": [], "appeared": []}, ensure_ascii=False)


def _write_chapter(api, tmp_path, content="正文"):
    mirror.write_prose(api._conn, tmp_path, "ch1", content)


def test_auto_mode_extracts_on_external_change(api, tmp_path):  # TC-WB-03
    _write_chapter(api, tmp_path)
    (tmp_path / "chapters" / "ch1.md").write_text("改后的正文", encoding="utf-8")
    fake = FakeBackend([EXTRACT])
    sch = hook.HookScheduler(api, fake, mode="auto", interval=1.0)
    results = sch.tick()
    # extract 是 T8 完整返回（6 键），空 facts 下其余键确定：原样穿透不加料
    assert results == [{
        "chapter_id": "ch1", "status": "external_change",
        "extract": {"chapter_id": "ch1", "proposal_id": None,
                    "auto_event_seq": None, "warnings": [], "appeared": [],
                    "deviation": {"microbeat": None,
                                  "missing_elements": []}}}]
    assert "改后的正文" in fake.calls[0]["prompt"]    # 抽取吃的是新镜像


def test_manual_mode_registers_but_not_extracts(api, tmp_path):  # TC-WB-04 前半
    _write_chapter(api, tmp_path)
    (tmp_path / "chapters" / "ch1.md").write_text("手改", encoding="utf-8")
    fake = FakeBackend([EXTRACT])                    # trigger 要真调后端
    results = hook.HookScheduler(api, fake, "manual", 1.0).tick()
    assert results == [{"chapter_id": "ch1", "status": "external_change"}]
    assert fake.calls == []                          # 不立即抽取
    api.trigger_extract("ch1", backend=fake)         # 作者点击 → 显式抽取
    assert len(fake.calls) == 1


def test_timer_mode_no_thread_until_started(api):
    sch = hook.HookScheduler(api, FakeBackend([]), "timer", 60.0)
    assert sch._renewer is None                      # 未 start 不占线程
    sch.start(); sch.stop()


def test_scheduler_from_config(api):
    from snowel_core.storage import config
    config.set(api._conn, "hook.mode", "auto")
    sch = hook.HookScheduler.from_config(api, FakeBackend([]))
    assert sch.mode == "auto"


def test_tick_survives_poisoned_extract(api, tmp_path):  # 修环 1：单章抽取失败不杀 tick
    class BoomBackend(FakeBackend):
        def generate(self, prompt, *, model=None, system=None):
            self.calls.append({"prompt": prompt, "model": model, "system": system})
            raise RuntimeError("backend down")

    _write_chapter(api, tmp_path)
    (tmp_path / "chapters" / "ch1.md").write_text("毒章正文", encoding="utf-8")
    sch = hook.HookScheduler(api, BoomBackend([]), mode="auto", interval=1.0)
    results = sch.tick()                             # 异常不得逃出 tick
    assert results == [{"chapter_id": "ch1", "status": "external_change",
                        "extract_error": "backend down"}]
    (tmp_path / "chapters" / "ch1.md").write_text("再改一次", encoding="utf-8")
    results2 = sch.tick()                            # 第二轮仍活：线程未死语义
    assert results2 == [{"chapter_id": "ch1", "status": "external_change",
                         "extract_error": "backend down"}]
