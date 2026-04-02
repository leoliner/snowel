"""数据模型定义"""
from typing import List, Optional
from pydantic import BaseModel
from datetime import datetime


# ========== API 配置相关 ==========

class APIConfig(BaseModel):
    """API 配置模型"""
    api_key: str
    base_url: str = "https://api.moonshot.cn/v1"
    model: str = "kimi-k2-5"


class APIConfigResponse(BaseModel):
    """API 配置响应（隐藏密钥）"""
    configured: bool
    base_url: str = ""
    model: str = ""
    api_key_masked: str = ""


# ========== Layer 1: 灵感雪核 ==========

class TagLibrary(BaseModel):
    """标签库"""
    genres: List[str] = []  # 类型标签
    themes: List[str] = []  # 主题标签
    tones: List[str] = []   # 基调标签
    elements: List[str] = []  # 元素标签


class PremiseRequest(BaseModel):
    """生成前提请求"""
    tags: List[str]
    count: int = 3


class PremiseResponse(BaseModel):
    """前提响应"""
    candidates: List[str]


class Layer1Data(BaseModel):
    """Layer 1 完整数据"""
    tags: List[str] = []
    selected_premise: str = ""
    created_at: datetime = None

    def model_post_init(self, __context):
        if self.created_at is None:
            self.created_at = datetime.now()


# ========== Layer 2: 故事骨架 ==========

class SummaryRequest(BaseModel):
    """生成摘要请求"""
    premise: str
    ending_type: str = "open"  # happy, tragic, open, twist


class SummaryResponse(BaseModel):
    """摘要响应"""
    sentences: List[str]  # 五句话
    emotional_costs: List[str]  # 三个冲突的情感代价


class OutlineRequest(BaseModel):
    """生成大纲请求"""
    summary: SummaryResponse
    num_chapters: int = 20


class ChapterOutline(BaseModel):
    """单章大纲"""
    chapter: int
    title: str
    description: str
    conflict: str
    goal: str
    setback: str


class OutlineResponse(BaseModel):
    """大纲响应"""
    chapters: List[ChapterOutline]


class Layer2Data(BaseModel):
    """Layer 2 完整数据"""
    summary_sentences: List[str] = []
    emotional_costs: List[str] = []
    outline: List[ChapterOutline] = []
    created_at: datetime = None

    def model_post_init(self, __context):
        if self.created_at is None:
            self.created_at = datetime.now()


# ========== 项目相关 ==========

class ProjectCreate(BaseModel):
    """创建项目请求"""
    name: str
    description: str = ""


class ProjectInfo(BaseModel):
    """项目信息"""
    id: str
    name: str
    description: str
    created_at: datetime
    updated_at: datetime
    layer1_completed: bool = False
    layer2_completed: bool = False


class ProjectDetail(BaseModel):
    """项目详情"""
    info: ProjectInfo
    layer1: Optional[Layer1Data] = None
    layer2: Optional[Layer2Data] = None
