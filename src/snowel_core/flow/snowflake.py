# src/snowel_core/flow/snowflake.py
from .generate import ai_generate


def expand_chapter(api, chapter_id: str, backend,
                   extra: dict | None = None) -> list[str]:
    """小雪花 = 受限展开（§5.1）：档案现成直接拉取，只产提案不自动确认。"""
    locate = {"chapter": chapter_id}
    return [
        ai_generate(api, "chapter_intent", locate, extra, backend),
        ai_generate(api, "microbeat_group", locate, extra, backend),
        ai_generate(api, "prose", locate, extra, backend),
    ]
