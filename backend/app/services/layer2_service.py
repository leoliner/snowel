"""Layer 2: 故事骨架 - 段落摘要与一页大纲"""
from typing import List

from app.models.schemas import SummaryResponse, ChapterOutline, Layer2Data
from app.services.ai_service import ai_service


class Layer2Service:
    """故事骨架服务"""

    async def generate_summary(
        self,
        premise: str,
        ending_type: str = "open"
    ) -> SummaryResponse:
        """生成五句话段落摘要"""
        result = await ai_service.generate_summary(premise, ending_type)
        return SummaryResponse(**result)

    async def generate_outline(
        self,
        summary: SummaryResponse,
        num_chapters: int = 20
    ) -> List[ChapterOutline]:
        """生成一页大纲"""
        chapters_data = await ai_service.generate_outline(summary, num_chapters)
        return [ChapterOutline(**ch) for ch in chapters_data]

    def validate_summary(self, sentences: List[str]) -> tuple[bool, str]:
        """验证摘要是否符合规则"""
        # 规则1: 必须五句话
        if len(sentences) != 5:
            return False, f"摘要必须为五句话（当前{len(sentences)}句）"

        # 规则2: 第三句必须是三个冲突
        # 简化检查：每句不为空
        for i, s in enumerate(sentences):
            if not s or len(s) < 10:
                return False, f"第{i+1}句过短或为空"

        return True, "✅ 摘要结构符合规则"

    def validate_outline(
        self,
        chapters: List[ChapterOutline]
    ) -> tuple[bool, str]:
        """验证大纲是否符合规则"""
        # 规则1: 检查章节数
        if len(chapters) < 10:
            return False, f"章节数过少（建议10-40章，当前{len(chapters)}章）"
        if len(chapters) > 40:
            return False, f"章节数过多（建议10-40章，当前{len(chapters)}章）"

        # 规则2: 每章必须有目标-冲突-挫折
        for i, ch in enumerate(chapters):
            if not ch.goal:
                return False, f"第{ch.chapter}章缺少目标"
            if not ch.conflict:
                return False, f"第{ch.chapter}章缺少冲突"
            if not ch.setback:
                return False, f"第{ch.chapter}章缺少挫折"

        return True, f"✅ 大纲结构符合规则（共{len(chapters)}章）"


layer2_service = Layer2Service()
