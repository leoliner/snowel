"""AI 服务 - 封装 OpenAI 兼容 API 调用"""
from typing import List, Optional
from openai import AsyncOpenAI

from app.core.security import secure_storage


class AIService:
    """AI 生成服务"""

    def __init__(self):
        self._client: Optional[AsyncOpenAI] = None
        self._config = None

    async def _get_client(self) -> AsyncOpenAI:
        """获取或创建 OpenAI 客户端"""
        if self._client is None:
            config = secure_storage.load_config()
            if not config or not config.get("api_key"):
                raise ValueError("API 密钥未配置")

            self._config = config
            self._client = AsyncOpenAI(
                api_key=config["api_key"],
                base_url=config.get("base_url")
            )
        return self._client

    async def generate_premise_candidates(
        self,
        tags: List[str],
        count: int = 3
    ) -> List[str]:
        """生成一句话前提候选"""
        client = await self._get_client()

        prompt = f"""基于以下标签，生成{count}个不同的一句话小说前提。
每个前提必须包含：主角 + 主动动词 + 独特冲突，不超过25个字。

标签：{', '.join(tags)}

要求：
- 每个前提用数字编号
- 只输出前提内容，不要额外解释
- 确保冲突具有戏剧性"""

        response = await client.chat.completions.create(
            model=self._config.get("model", "kimi-k2-5"),
            messages=[
                {"role": "system", "content": "你是一个专业的故事创意生成助手，擅长基于标签创作引人入胜的故事前提。"},
                {"role": "user", "content": prompt}
            ],
            temperature=0.8,
            max_tokens=300
        )

        content = response.choices[0].message.content
        # 解析候选列表
        candidates = []
        for line in content.strip().split('\n'):
            line = line.strip()
            if line and (line[0].isdigit() or line.startswith('-')):
                # 去掉编号
                candidate = line.lstrip('0123456789.-) ').strip()
                if candidate:
                    candidates.append(candidate)

        return candidates[:count]

    async def generate_summary(
        self,
        premise: str,
        ending_type: str = "open"
    ) -> dict:
        """生成五句话段落摘要"""
        client = await self._get_client()

        endings = {
            "happy": "美好结局",
            "tragic": "悲剧结局",
            "open": "开放式结局",
            "twist": "反转结局"
        }

        prompt = f"""基于以下前提，生成一个五句话的故事摘要。

前提：{premise}
结局类型：{endings.get(ending_type, "开放式结局")}

五句话结构：
1. 背景与主角现状
2. 第一个冲突（引入变化）
3. 第二个冲突（升级紧张）
4. 第三个冲突（危机顶点）
5. 结局

输出格式：
{{
    "sentences": ["句1", "句2", "句3", "句4", "句5"],
    "emotional_costs": ["冲突1的情感代价", "冲突2的情感代价", "冲突3的情感代价"]
}}"""

        response = await client.chat.completions.create(
            model=self._config.get("model", "kimi-k2-5"),
            messages=[
                {"role": "system", "content": "你是一个专业的故事结构师，擅长使用雪花写作法构建故事框架。输出必须是有效的JSON格式。"},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
            response_format={"type": "json_object"},
            max_tokens=800
        )

        import json
        content = response.choices[0].message.content
        return json.loads(content)

    async def generate_outline(
        self,
        summary: dict,
        num_chapters: int = 20
    ) -> List[dict]:
        """生成一页大纲（章节列表）"""
        client = await self._get_client()

        sentences = summary.get("sentences", [])
        summary_text = " ".join(sentences)

        prompt = f"""基于以下故事摘要，生成{num_chapters}章的大纲。

摘要：{summary_text}

要求：
- 每章包含：章号、标题、一句话描述、核心冲突
- 章节应该分布在三幕结构中
- 每章必须包含目标-冲突-挫折

输出格式：JSON数组
[
    {{
        "chapter": 1,
        "title": "章节标题",
        "description": "一句话描述本章内容",
        "conflict": "本章核心冲突",
        "goal": "主角目标",
        "setback": "遭遇的挫折"
    }}
]"""

        response = await client.chat.completions.create(
            model=self._config.get("model", "kimi-k2-5"),
            messages=[
                {"role": "system", "content": "你是一个专业的小说大纲设计师。输出必须是有效的JSON数组格式。"},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
            response_format={"type": "json_object"},
            max_tokens=2000
        )

        import json
        content = response.choices[0].message.content
        result = json.loads(content)
        # 处理可能的嵌套结构
        if isinstance(result, dict):
            return result.get("chapters", result.get("outline", []))
        return result


ai_service = AIService()
