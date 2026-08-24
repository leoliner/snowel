# tests/flow/test_state.py
from snowel_core.flow import state


def test_flow_state_layers_and_tree(api):
    api.proposals.create("premise", {"draft": "x"})
    pid = api.proposals.list("pending")[0]["id"]
    api.confirm(pid)                                     # premise done
    from snowel_core.storage import db, events, projector
    with db.transaction(api._conn):
        events.append_event(api._conn, "proposal_confirmed", {
            "artifact_type": "structure", "facts": [
                {"fact": "node", "id": "v1", "types": ["Volume"],
                 "name": "卷一", "props": {}},
                {"fact": "node", "id": "c1", "types": ["Chapter"],
                 "name": "第1章", "props": {"volume": "v1"}}]})
        projector.apply(api._conn)
    s = state.flow_state(api._conn)
    assert s["layers"]["premise"] == "done"
    assert s["layers"]["synopsis"] == "todo"
    assert s["current_layer"] == "synopsis"
    assert s["volumes"] == [{"id": "v1", "name": "卷一",
                             "chapters": [{"id": "c1", "name": "第1章"}]}]
    assert api.graph_stats()["active_nodes"] == 2


def test_flow_state_scene_kind_satisfies_scenes_layer(api):
    # 终审修复 F2：层名 "scenes"（复数）vs 提案 kind "scene"（单数）——
    # 确认 scene 提案后 scenes 层必须置 done，否则永远卡层
    pid = api.proposals.create("scene", {"facts": []})
    api.confirm(pid)
    s = state.flow_state(api._conn)
    assert s["layers"]["scenes"] == "done"
