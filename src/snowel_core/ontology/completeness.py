# active 判定需"已确认正文登场"，属回写环计划；此处只做 draft/profiled。
_CORE_FIELDS = ("motivation", "lie", "fear", "arc")

def is_core_complete(core: dict) -> bool:
    return all(core.get(f) for f in _CORE_FIELDS)

def derive(props: dict) -> str:
    """draft/profiled 推导（props 无 IO）；active=正文登场，由抽取 appeared 接线（回写环计划）。"""
    return "profiled" if is_core_complete(props.get("core", {})) else "draft"
