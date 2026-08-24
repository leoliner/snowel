# src/snowel_core/flow/registry.py
ARTIFACTS = {
    "premise":        {"layer": 1, "strategy": "generic",   "template": "写一句话灵感前提。"},
    "synopsis":       {"layer": 1, "strategy": "generic",   "template": "扩展为一段梗概。"},
    "summary":        {"layer": 2, "strategy": "generic",   "template": "写摘要页。"},
    "beat_sheet":     {"layer": 3, "strategy": "generic",   "template": "写节拍表。"},
    "characters":     {"layer": 4, "strategy": "character", "template": "生成角色档案。"},
    "scene":          {"layer": 4, "strategy": "generic",   "template": "生成场景卡（含 required_elements、characters）。"},
    "prose":          {"layer": 5, "strategy": "prose",     "template": "写本章正文。"},
    "microbeat_group": {"layer": 5, "strategy": "prose",    "template": "产本章 3-6 个微节拍（props 含 keywords）。"},
    "chapter_intent": {"layer": 5, "strategy": "prose",     "template": "一句话本章意图。"},
    "volume_theme":   {"layer": 0, "strategy": "generic",   "template": "卷级主题。"},
    "volume_acts":    {"layer": 0, "strategy": "generic",   "template": "卷级三幕。"},
}
