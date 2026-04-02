"""Layer 1: 灵感雪核 - 标签拼贴与前提生成"""
import uuid
from typing import List, Optional
from pathlib import Path
import json

from app.models.schemas import Layer1Data, ProjectInfo, TagLibrary
from app.core.config import settings
from app.services.ai_service import ai_service


# 预设标签库
DEFAULT_TAG_LIBRARY = TagLibrary(
    genres=[
        "奇幻", "科幻", "悬疑", "爱情", "历史", "武侠",
        "恐怖", "冒险", "推理", "都市", "末世", "克苏鲁"
    ],
    themes=[
        "复仇", "救赎", "成长", "背叛", "牺牲", "觉醒",
        "真相", "命运", "自由", "权力", "爱情", "亲情"
    ],
    tones=[
        "黑暗压抑", "轻松幽默", "紧张刺激", "温馨治愈",
        "史诗宏大", "冷峻写实", "浪漫唯美", "诡异神秘"
    ],
    elements=[
        "时间穿越", "失忆", "双重身份", "古代遗迹", "神秘组织",
        "禁忌之恋", "末日求生", "AI觉醒", "魔法学院", "星际战争"
    ]
)


class Layer1Service:
    """灵感雪核服务"""

    def __init__(self):
        self.tag_library = DEFAULT_TAG_LIBRARY

    def get_tag_library(self) -> TagLibrary:
        """获取标签库"""
        return self.tag_library

    async def generate_premise_candidates(
        self,
        tags: List[str],
        count: int = 3
    ) -> List[str]:
        """生成前提候选"""
        return await ai_service.generate_premise_candidates(tags, count)

    def validate_premise(self, premise: str) -> tuple[bool, str]:
        """验证前提是否符合规则"""
        # 规则1: 不超过25个字
        if len(premise) > 25:
            return False, f"前提超过25个字（当前{len(premise)}字）"

        # 规则2: 包含主角（通常是人名或代词）
        # 简化检查：是否有主语感
        if not premise:
            return False, "前提不能为空"

        # 规则3: 包含主动动词和冲突感
        active_verbs = ["复仇", "寻找", "拯救", "逃离", "对抗", "守护",
                       "揭露", "阻止", "夺取", "追求", "反抗", "调查"]
        has_active_verb = any(v in premise for v in active_verbs)

        if not has_active_verb:
            return True, "⚠️ 建议包含更明确的主动动词以增强冲突感"

        return True, "✅ 前提符合规则"


class ProjectService:
    """项目管理服务"""

    def __init__(self):
        self.projects_path = settings.PROJECTS_PATH

    def _get_project_dir(self, project_id: str) -> Path:
        """获取项目目录"""
        return self.projects_path / project_id

    def _get_project_file(self, project_id: str) -> Path:
        """获取项目数据文件路径"""
        return self._get_project_dir(project_id) / "project.json"

    def _get_layer1_file(self, project_id: str) -> Path:
        """获取 Layer1 数据文件路径"""
        return self._get_project_dir(project_id) / "layer1.json"

    def _get_layer2_file(self, project_id: str) -> Path:
        """获取 Layer2 数据文件路径"""
        return self._get_project_dir(project_id) / "layer2.json"

    def create_project(self, name: str, description: str = "") -> ProjectInfo:
        """创建新项目"""
        from datetime import datetime

        project_id = str(uuid.uuid4())[:8]
        now = datetime.now()

        project = ProjectInfo(
            id=project_id,
            name=name,
            description=description,
            created_at=now,
            updated_at=now
        )

        # 创建项目目录并保存
        project_dir = self._get_project_dir(project_id)
        project_dir.mkdir(parents=True, exist_ok=True)

        with open(self._get_project_file(project_id), "w", encoding="utf-8") as f:
            json.dump(project.model_dump(mode="json"), f, ensure_ascii=False, indent=2)

        return project

    def list_projects(self) -> List[ProjectInfo]:
        """列出所有项目"""
        projects = []
        for project_dir in self.projects_path.iterdir():
            if project_dir.is_dir():
                project_file = project_dir / "project.json"
                if project_file.exists():
                    with open(project_file, "r", encoding="utf-8") as f:
                        data = json.load(f)
                        projects.append(ProjectInfo(**data))
        return sorted(projects, key=lambda p: p.updated_at, reverse=True)

    def get_project(self, project_id: str) -> Optional[dict]:
        """获取项目详情"""
        project_file = self._get_project_file(project_id)
        if not project_file.exists():
            return None

        with open(project_file, "r", encoding="utf-8") as f:
            info = ProjectInfo(**json.load(f))

        # 加载 Layer1
        layer1 = None
        layer1_file = self._get_layer1_file(project_id)
        if layer1_file.exists():
            with open(layer1_file, "r", encoding="utf-8") as f:
                layer1 = Layer1Data(**json.load(f))

        # 加载 Layer2
        layer2 = None
        layer2_file = self._get_layer2_file(project_id)
        if layer2_file.exists():
            from app.models.schemas import Layer2Data, ChapterOutline
            with open(layer2_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                if "outline" in data:
                    data["outline"] = [ChapterOutline(**ch) for ch in data["outline"]]
                layer2 = Layer2Data(**data)

        return {
            "info": info,
            "layer1": layer1,
            "layer2": layer2
        }

    def save_layer1(self, project_id: str, layer1: Layer1Data) -> bool:
        """保存 Layer1 数据"""
        layer1_file = self._get_layer1_file(project_id)
        layer1_file.parent.mkdir(parents=True, exist_ok=True)

        with open(layer1_file, "w", encoding="utf-8") as f:
            json.dump(layer1.model_dump(mode="json"), f, ensure_ascii=False, indent=2)

        # 更新项目状态
        self._update_project_status(project_id, layer1_completed=True)
        return True

    def save_layer2(self, project_id: str, layer2: "Layer2Data") -> bool:
        """保存 Layer2 数据"""
        from app.models.schemas import Layer2Data

        layer2_file = self._get_layer2_file(project_id)
        layer2_file.parent.mkdir(parents=True, exist_ok=True)

        with open(layer2_file, "w", encoding="utf-8") as f:
            json.dump(layer2.model_dump(mode="json"), f, ensure_ascii=False, indent=2)

        # 更新项目状态
        self._update_project_status(project_id, layer2_completed=True)
        return True

    def _update_project_status(self, project_id: str, **kwargs) -> bool:
        """更新项目状态"""
        from datetime import datetime

        project_file = self._get_project_file(project_id)
        if not project_file.exists():
            return False

        with open(project_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        data.update(kwargs)
        data["updated_at"] = datetime.now().isoformat()

        with open(project_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        return True


layer1_service = Layer1Service()
project_service = ProjectService()
