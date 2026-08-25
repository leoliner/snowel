# src/snowel_core/writeback/extract.py
import json
import re
import sqlite3

from ..consistency import wiring
from ..llm.backend import GenerationBackend
from ..ontology import groups
from ..storage import config, events, projector
from ..storage.db import transaction
from . import deviation

_PROMPT = """你是小说设定抽取器。从下方章节正文中抽取事实。
判据：比喻、夸张、通感等修辞不构成事实，一律忽略（忽略修辞判据）。
只抽取文本明确陈述的内容。返回 JSON：
{{"facts": [{{"sensitivity": "high"|"low", "fact": {{"fact": "node"|"edge", ...}}}}],
 "appeared": ["登场实体已有节点 id，仅正文名词出场，图谱引用不算"]}}
高敏感 = 数字、人名变更、规则、角色生死；低敏感 = 描述性细节。

章节正文：
{prose}"""


def _has_number(fact: dict) -> bool:
    return bool(re.search(r"\d", json.dumps(
        fact.get("props", {}), ensure_ascii=False)))


def _validate_groups(fact: dict) -> list[str]:
    warns = []
    for gname, gval in fact.get("props", {}).items():
        if not isinstance(gval, dict):
            continue
        status, warn = groups.validate(gname, gval)
        if status == "unmanaged":
            warns.append(f"unmanaged 组 {gname} 照存（不参与护栏/级联）")
        elif status != "ok":
            warns.append(warn)
            return warns + ["__FORCE_HIGH__"]
    return warns


def extract_and_writeback(api, chapter_id: str, backend: GenerationBackend,
                          model: str | None = None) -> dict:
    """三口之一（E3）：抽取 → 确认分级（§5.3）→ 提案 / auto 单事件批量入典。"""
    conn: sqlite3.Connection = api._conn
    row = conn.execute(
        "SELECT prose, hash FROM chapter_prose WHERE chapter_id=?",
        (chapter_id,)).fetchone()
    if row is None or not row["prose"]:
        raise ValueError(f"章节 {chapter_id} 无镜像全文，先对账（reconcile）")
    resp = backend.generate(_PROMPT.format(prose=row["prose"]), model=model)
    from ..llm.ports import parse_llm_json  # 函数级导入：ports 顶层反向引用本模块
    parsed = parse_llm_json(resp)
    numeric_high = config.get(conn, "extraction.numeric_high", True)

    high, low, warnings, appeared = [], [], list(), parsed.get("appeared", [])
    for item in parsed["facts"]:
        fact = item["fact"]
        sens = item.get("sensitivity", "low")
        gw = _validate_groups(fact)
        if numeric_high and _has_number(fact):
            sens = "high"  # 确定性后校：数字事实强制高敏感（阈值可配置）
        if any(w == "__FORCE_HIGH__" for w in gw):
            sens = "high"  # 校验失败项不自动入典
        warnings.extend(w for w in gw if w != "__FORCE_HIGH__")
        (high if sens == "high" else low).append(fact)

    proposal_id = None
    if high:
        proposal_id = api.proposals.create("extract_facts", {
            "chapter_id": chapter_id, "facts": high, "appeared": appeared})
    auto_seq = None
    cascade = None
    if low:
        with transaction(conn):
            auto_seq = events.append_event(conn, "auto_canonized", {
                "facts": low, "source": {"chapter_id": chapter_id,
                                         "hash": row["hash"]},
                "appeared": appeared})
            projector.apply(conn)
        # 级联接线（E5 四写入点之二）：auto 入典事务后轻量跑档（C11）
        cascade = wiring.after_commit(conn, low, auto_seq, "light")
    return {"chapter_id": chapter_id, "proposal_id": proposal_id,
            "auto_event_seq": auto_seq, "warnings": warnings,
            "appeared": appeared, "cascade": cascade,
            "deviation": deviation.report(conn, chapter_id)}  # C12：随抽取产出
