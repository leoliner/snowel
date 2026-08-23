from pydantic import BaseModel, ValidationError

class CoreGroup(BaseModel):
    motivation: str
    lie: str
    fear: str
    arc: str

_registered: dict[str, tuple[type[BaseModel], int]] = {}

def register(schema: type[BaseModel], name: str, version: int) -> None:
    _registered[name] = (schema, version)

def validate(group_name: str, data: dict):
    if group_name not in _registered:
        return "unmanaged", None
    schema, cur = _registered[group_name]
    declared = None
    if isinstance(data.get("_schema"), str) and "@" in data["_schema"]:
        declared = int(data["_schema"].split("@")[1])
    try:
        schema.model_validate(data)
    except ValidationError as e:
        if declared is not None and declared != cur:
            return "version_mismatch", f"组 {group_name}@{declared} 与注册版本 @{cur} 不匹配"
        return "invalid", str(e.errors()[0])
    if declared is not None and declared != cur:
        return "version_mismatch", f"组 {group_name}@{declared} 与注册版本 @{cur} 不匹配"
    return "ok", None

register(CoreGroup, "core", version=1)
