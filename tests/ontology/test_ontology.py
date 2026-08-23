from snowel_core.ontology import groups, completeness

def test_core_group_registered_and_validated():
    status, warn = groups.validate("core", {"motivation": "活下去", "lie": "没人会救我",
                                            "fear": "被抛下", "arc": "学会信任"})
    assert status == "ok" and warn is None
    status, warn = groups.validate("core", {"motivation": "x"})
    assert status == "invalid"

def test_unmanaged_group_stored_with_flag():
    status, warn = groups.validate("foo", {"anything": 1})
    assert status == "unmanaged"

def test_version_mismatch_downgrades_to_warning():
    groups._registered.pop("demo", None)
    from pydantic import BaseModel
    class DemoV2(BaseModel):
        power: int
    groups.register(DemoV2, "demo", version=2)
    data = {"_schema": "demo@1", "power": 5}
    status, warn = groups.validate("demo", data)
    assert status == "version_mismatch" and warn

def test_derive_completeness():
    assert not completeness.is_core_complete({"motivation": "x"})
    assert completeness.is_core_complete(
        {"motivation": "x", "lie": "y", "fear": "z", "arc": "w"})
