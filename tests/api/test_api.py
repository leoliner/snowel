from snowel_core import api as sapi

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
