# tests/test_queries.py
from snowel_core.storage import db, events, projector, queries


def _mk(tmp_path):
    conn = db.connect(tmp_path / "s.db"); db.migrate(conn); return conn


def _confirm(conn, facts, **kw):
    with db.transaction(conn) as tx:
        events.append_event(tx, "proposal_confirmed",
                            {"proposal_id": "p", "artifact_type": "t",
                             "facts": facts, **kw})
    projector.apply(conn)


def test_state_at_filters_by_validity(tmp_path):
    conn = _mk(tmp_path)
    _confirm(conn, [
        {"fact": "node", "id": "mb1", "types": ["MicroBeat"], "name": "b1",
         "props": {"address": {"volume": 1, "chapter": 1, "scene": 1, "beat": 1}}},
        {"fact": "node", "id": "mb2", "types": ["MicroBeat"], "name": "b2",
         "props": {"address": {"volume": 1, "chapter": 1, "scene": 1, "beat": 2}}},
        {"fact": "edge", "id": "e1", "src": "mb1", "dst": "mb2", "kind": "PARTICIPATES",
         "props": {"valid_from_beat": "mb1", "valid_until_beat": "mb2"}},
    ])
    p1 = queries.state_at(conn, 0)
    assert {n["id"] for n in p1["nodes"]} == {"mb1"}     # mb2 尚未生效
    assert {e["id"] for e in p1["edges"]} == {"e1"}
    p2 = queries.state_at(conn, 1)
    assert {n["id"] for n in p2["nodes"]} == {"mb1", "mb2"}
    assert {e["id"] for e in p2["edges"]} == {"e1"}
    p3 = queries.state_at(conn, 2)
    assert {e["id"] for e in p3["edges"]} == set()      # valid_until=1 已过期


def _seed(tmp_path):
    conn = _mk(tmp_path)
    _confirm(conn, [
        {"fact": "node", "id": "n1", "types": ["Character", "Concept"],
         "name": "江晚", "props": {}},
        {"fact": "node", "id": "n2", "types": ["Concept"], "name": "轮回游戏", "props": {}},
        {"fact": "node", "id": "n3", "types": ["Mechanism"], "name": "积分兑换", "props": {}},
        {"fact": "edge", "id": "e1", "src": "n2", "dst": "n3", "kind": "REQUIRES", "props": {}},
        {"fact": "edge", "id": "e2", "src": "n3", "dst": "n2", "kind": "IS_A", "props": {}},
    ])
    with db.transaction(conn) as tx:
        events.append_event(tx, "retcon_applied", {"renames": [
            {"node_id": "n1", "old_name": "林晚", "new_name": "江晚"}], "notes": ""})
    projector.apply(conn)
    return conn


def test_find_nodes_by_alias_and_type(tmp_path):
    conn = _seed(tmp_path)
    assert queries.find_nodes(conn, name="林晚")[0]["id"] == "n1"   # alias 命中
    assert queries.find_nodes(conn, name="江晚")[0]["id"] == "n1"
    assert {r["id"] for r in queries.find_nodes(conn, type="Concept")} == {"n1", "n2"}


def test_get_node(tmp_path):
    conn = _seed(tmp_path)
    assert queries.get_node(conn, "n1")["name"] == "江晚"
    assert queries.get_node(conn, "nope") is None


def test_edges_of_both_directions(tmp_path):
    conn = _seed(tmp_path)
    out = queries.edges_of(conn, "n2", "out")
    assert [e["id"] for e in out] == ["e1"]
    both = queries.edges_of(conn, "n3")
    assert {e["id"] for e in both} == {"e1", "e2"}


def test_descendants_recursive_cte(tmp_path):
    conn = _seed(tmp_path)
    # e1: n2->n3, e2: n3->n2 构成环：递归 CTE 必须不死循环
    ds = queries.descendants(conn, "n2", max_depth=5)
    assert {r["id"] for r in ds} == {"n3"}


def test_state_at_uses_current_effective_version(tmp_path):  # C9 修正后视角
    conn = _mk(tmp_path)
    _confirm(conn, [{"fact": "node", "id": "n1", "types": ["Character"],
                     "name": "林晚", "props": {"core": {"level": 1}}}])
    # retcon 修正等级（追加事件，物化为当前版）
    with db.transaction(conn) as tx:
        events.append_event(tx, "proposal_confirmed",
            {"proposal_id": "p2", "artifact_type": "retcon", "facts": [
                {"fact": "node", "id": "n1", "types": ["Character"], "name": "林晚",
                 "props": {"core": {"level": 9}}}]})
    projector.apply(conn)
    s = queries.state_at(conn, 0)
    assert s["nodes"][0]["core_level"] == 9             # 取当前生效版，不是历史原版


FACTS = [{"fact": "node", "id": "n1", "types": ["Character"],
          "name": "林晚", "props": {}}]


def test_descendants_kinds_and_validity(core_conn):  # L4
    _confirm(core_conn, [
        {"fact": "node", "id": "n1", "types": ["Concept"], "name": "a", "props": {}},
        {"fact": "node", "id": "n2", "types": ["Mechanism"], "name": "b", "props": {}},
        {"fact": "node", "id": "n3", "types": ["Concept"], "name": "c", "props": {}},
        {"fact": "edge", "id": "e1", "src": "n1", "dst": "n2", "kind": "REQUIRES",
         "props": {"valid_from_beat": "mb1", "valid_until_beat": "mb2"}},
        {"fact": "edge", "id": "e2", "src": "n1", "dst": "n3", "kind": "IS_A",
         "props": {}},
        {"fact": "node", "id": "mb1", "types": ["MicroBeat"], "name": "x",
         "props": {"address": {"volume": 1, "chapter": 1, "scene": 1, "beat": 1}}},
        {"fact": "node", "id": "mb2", "types": ["MicroBeat"], "name": "y",
         "props": {"address": {"volume": 1, "chapter": 2, "scene": 1, "beat": 1}}},
    ])
    # kinds 过滤
    got = {r["id"] for r in queries.descendants(core_conn, "n1", kinds=["REQUIRES"])}
    assert got == {"n2"}
    # 时效过滤：e1 有效期 [0,1]，at=5 过期；e2 恒有效
    got2 = {r["id"] for r in queries.descendants(
        core_conn, "n1", at_story_order=5)}
    assert got2 == {"n3"}
    got3 = {r["id"] for r in queries.descendants(
        core_conn, "n1", at_story_order=1)}
    assert got3 == {"n2", "n3"}
    # 默认行为不变
    assert len(queries.descendants(core_conn, "n1")) == 2


def test_edges_of_active_only(core_conn):  # L17
    _confirm(core_conn, [
        {"fact": "node", "id": "a", "types": ["Character"], "name": "a", "props": {}},
        {"fact": "node", "id": "b", "types": ["Concept"], "name": "b",
         "props": {"address": {"volume": 1}}},
        {"fact": "node", "id": "v1", "types": ["Volume"], "name": "卷一",
         "props": {"address": {"volume": 1}}},
        {"fact": "edge", "id": "e1", "src": "a", "dst": "b", "kind": "REQUIRES",
         "props": {}},
    ])
    with db.transaction(core_conn):
        events.append_event(core_conn, "retraction",
                            {"target": "node", "target_id": "b"})
    projector.apply(core_conn)
    assert queries.edges_of(core_conn, "a") == []            # 默认仅活跃
    assert len(queries.edges_of(core_conn, "a", active_only=False)) == 1
    # get_node 同口径
    assert queries.get_node(core_conn, "b") is None
    assert queries.get_node(core_conn, "b", active_only=False) is not None
    # seal 的前 canon 读取不受统一影响（L 前修复不回退）：b 已撤回但带 address，
    # 仍命中归属卷 v1——"行被读到"与"行被 active 过滤"从此可区分（评审修复）
    from snowel_core.consistency import seal
    assert seal.volume_id_of(core_conn, "b") == "v1"


def test_graph_stats_counts_and_types(tmp_path):
    # 本文件无 conn fixture，沿用 _mk(tmp_path) 建库（断言与 brief 一致）
    conn = _mk(tmp_path)
    from snowel_core.storage import db, events, projector
    from snowel_core.storage.queries import graph_stats
    with db.transaction(conn):
        events.append_event(conn, "proposal_confirmed",
                            {"facts": FACTS})
        projector.apply(conn)
    stats = graph_stats(conn)
    assert stats["nodes"] == 1
    assert stats["edges"] == 0
    assert stats["nodes_by_type"] == {"Character": 1}


# ---- Task 7（W4 可视化四件）：统计查询语义 ----

def _seed_stats(tmp_path):
    """统计种子：双卷 + 双 POV 章/场/拍（ch1 章级江晚、场级沈眠）+ 无 pov 拍。"""
    conn = _mk(tmp_path)
    _confirm(conn, [
        {"fact": "node", "id": "v1", "types": ["Volume"], "name": "卷一",
         "props": {"address": {"volume": 1}}},
        {"fact": "node", "id": "v2", "types": ["Volume"], "name": "卷二",
         "props": {"address": {"volume": 2}}},
        {"fact": "node", "id": "ch1", "types": ["Chapter"], "name": "第一章",
         "props": {"address": {"volume": 1, "chapter": 1},
                   "pov": {"name": "江晚"}}},
        {"fact": "node", "id": "ch2", "types": ["Chapter"], "name": "第二章",
         "props": {"address": {"volume": 1, "chapter": 2},
                   "pov": {"name": "沈眠"}}},
        {"fact": "node", "id": "ch3", "types": ["Chapter"], "name": "第三章",
         "props": {"address": {"volume": 2, "chapter": 1},
                   "pov": {"name": "江晚"}}},
        {"fact": "node", "id": "s1", "types": ["Scene"], "name": "场景一",
         "props": {"address": {"volume": 1, "chapter": 1, "scene": 1},
                   "pov": {"name": "沈眠"}}},
        {"fact": "node", "id": "mb1", "types": ["MicroBeat"], "name": "拍一",
         "props": {"address": {"volume": 1, "chapter": 1, "scene": 1, "beat": 1},
                   "pov": {"name": "江晚"}}},
        {"fact": "node", "id": "mb2", "types": ["MicroBeat"], "name": "拍二",
         "props": {"address": {"volume": 1, "chapter": 1, "scene": 1, "beat": 2}}},
        {"fact": "node", "id": "mb3", "types": ["MicroBeat"], "name": "拍三",
         "props": {"address": {"volume": 2, "chapter": 1, "scene": 1, "beat": 1},
                   "pov": {"name": "沈眠"}}},
    ])
    return conn


def test_stats_pov_counts_by_volume(tmp_path):
    conn = _seed_stats(tmp_path)
    by_volume = {v["volume_id"]: v for v in queries.stats_pov(conn)["by_volume"]}
    # ch1(江晚)/s1(沈眠)/mb1(江晚)/ch2(沈眠) → 卷一；mb2 无 pov 不计入
    assert by_volume["v1"]["volume_name"] == "卷一"
    assert by_volume["v1"]["counts"] == {"江晚": 2, "沈眠": 2}
    assert by_volume["v2"]["counts"] == {"江晚": 1, "沈眠": 1}
    assert sum(sum(v["counts"].values()) for v in by_volume.values()) == 6


def test_stats_pov_volume_less_node_grouped_null(tmp_path):
    # 有 pov 但无 address 的节点：仍计入，按未分卷聚合（volume_id/name 为 None）
    conn = _mk(tmp_path)
    _confirm(conn, [{"fact": "node", "id": "n1", "types": ["Scene"],
                     "name": "x", "props": {"pov": {"name": "江晚"}}}])
    got = queries.stats_pov(conn)
    assert got["by_volume"] == [{"volume_id": None, "volume_name": None,
                                 "counts": {"江晚": 1}}]


def test_stats_foreshadow_statuses(tmp_path):
    conn = _mk(tmp_path)
    _confirm(conn, [
        {"fact": "node", "id": "mb1", "types": ["MicroBeat"], "name": "b1",
         "props": {"address": {"volume": 1, "chapter": 1, "scene": 1, "beat": 1}}},
        {"fact": "node", "id": "mb5", "types": ["MicroBeat"], "name": "b5",
         "props": {"address": {"volume": 1, "chapter": 1, "scene": 1, "beat": 5}}},
        {"fact": "node", "id": "mb6", "types": ["MicroBeat"], "name": "b6",
         "props": {"address": {"volume": 1, "chapter": 1, "scene": 1, "beat": 6}}},
        {"fact": "node", "id": "f1", "types": ["Foreshadow"], "name": "怀表",
         "props": {"foreshadow": {"planted_at": "mb1", "origin": "author",
                                  "payoff_beat": None, "note": ""}}},
        {"fact": "node", "id": "f2", "types": ["Foreshadow"], "name": "铜币",
         "props": {"foreshadow": {"planted_at": "mb1", "origin": "author",
                                  "payoff_beat": "mb5", "note": ""}}},
        {"fact": "node", "id": "f3", "types": ["Foreshadow"], "name": "钥匙",
         "props": {"foreshadow": {"planted_at": "mb1", "origin": "author",
                                  "payoff_beat": "mb9", "note": ""}}},
        {"fact": "node", "id": "f4", "types": ["Foreshadow"], "name": "信",
         "props": {"foreshadow": {"planted_at": "mb1", "origin": "author",
                                  "payoff_beat": "mb6", "note": ""}}},
    ])
    with db.transaction(conn):
        events.append_event(conn, "retraction",
                            {"target": "node", "target_id": "mb6"})
    projector.apply(conn)
    items = {it["id"]: it for it in queries.stats_foreshadow(conn)["items"]}
    assert items["f1"]["status"] == "planted"      # payoff_beat 空
    assert items["f2"]["status"] == "paid"         # 目标拍存在且活跃
    assert items["f3"]["status"] == "stale"        # 目标拍缺失
    assert items["f4"]["status"] == "stale"        # 目标拍已撤回（active=0）
    assert items["f1"]["planted_at"] == "mb1" and items["f1"]["payoff_beat"] is None
    assert items["f2"]["payoff_beat"] == "mb5"
    assert {it["name"] for it in items.values()} == {"怀表", "铜币", "钥匙", "信"}


def test_stats_relations_active_characters_only(tmp_path):
    conn = _mk(tmp_path)
    _confirm(conn, [
        {"fact": "node", "id": "a", "types": ["Character"], "name": "江晚",
         "props": {}},
        {"fact": "node", "id": "b", "types": ["Character"], "name": "沈眠",
         "props": {}},
        {"fact": "node", "id": "c", "types": ["Character"], "name": "林晚",
         "props": {}},
        {"fact": "node", "id": "d", "types": ["Character"], "name": "路人",
         "props": {}},
        {"fact": "node", "id": "x", "types": ["Concept"], "name": "轮回游戏",
         "props": {}},
        {"fact": "edge", "id": "e1", "src": "a", "dst": "b", "kind": "KNOWS",
         "props": {}},
        {"fact": "edge", "id": "e2", "src": "b", "dst": "c", "kind": "KNOWS",
         "props": {}},
        {"fact": "edge", "id": "e3", "src": "b", "dst": "d", "kind": "KNOWS",
         "props": {}},
        {"fact": "edge", "id": "e4", "src": "a", "dst": "x", "kind": "PARTICIPATES",
         "props": {}},
    ])
    with db.transaction(conn):
        events.append_event(conn, "retraction",
                            {"target": "node", "target_id": "d"})
    projector.apply(conn)
    got = queries.stats_relations(conn)
    assert {n["id"] for n in got["nodes"]} == {"a", "b", "c"}
    assert {e["id"] for e in got["edges"]} == {"e1", "e2"}  # e3 端 d 撤回、e4 非角色
    assert got["edges"][0]["kind"] == "KNOWS"               # 行序列化为 dict


def test_stats_pacing_beats_and_paragraphs(tmp_path):
    conn = _mk(tmp_path)
    _confirm(conn, [
        {"fact": "node", "id": "ch1", "types": ["Chapter"], "name": "第一章",
         "props": {"address": {"volume": 1, "chapter": 1}}},
        {"fact": "node", "id": "ch2", "types": ["Chapter"], "name": "第二章",
         "props": {"address": {"volume": 1, "chapter": 2}}},
        {"fact": "node", "id": "mb1", "types": ["MicroBeat"], "name": "b1",
         "props": {"address": {"volume": 1, "chapter": 1, "scene": 1, "beat": 1}}},
        {"fact": "node", "id": "mb2", "types": ["MicroBeat"], "name": "b2",
         "props": {"address": {"volume": 1, "chapter": 1, "scene": 1, "beat": 2}}},
        {"fact": "node", "id": "mb3", "types": ["MicroBeat"], "name": "b3",
         "props": {"address": {"volume": 1, "chapter": 2, "scene": 1, "beat": 1}}},
        {"fact": "node", "id": "mb4", "types": ["MicroBeat"], "name": "b4",
         "props": {"address": {"volume": 2, "chapter": 1, "scene": 1, "beat": 1}}},
    ])
    from snowel_core.writeback import mirror
    mirror.write_prose(conn, tmp_path, "ch1", "段一\n\n段二\n\n段三")
    mirror.write_prose(conn, tmp_path, "ch2", "段四")
    got = queries.stats_pacing(conn)
    assert [c["chapter_id"] for c in got["chapters"]] == ["ch1", "ch2"]
    by_id = {c["chapter_id"]: c for c in got["chapters"]}
    assert by_id["ch1"]["name"] == "第一章"
    assert by_id["ch1"]["beats"] == 2 and by_id["ch1"]["paragraphs"] == 3
    assert by_id["ch2"]["beats"] == 1 and by_id["ch2"]["paragraphs"] == 1
