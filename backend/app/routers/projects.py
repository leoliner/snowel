"""项目管理路由"""
from typing import List
from fastapi import APIRouter, HTTPException

from app.models.schemas import (
    ProjectCreate, ProjectInfo, ProjectDetail,
    Layer1Data, PremiseRequest, PremiseResponse,
    SummaryRequest, SummaryResponse,
    OutlineRequest, OutlineResponse, Layer2Data
)
from app.services.layer1_service import project_service, layer1_service
from app.services.layer2_service import layer2_service

router = APIRouter(prefix="/api/projects", tags=["项目管理"])


@router.post("/", response_model=ProjectInfo)
async def create_project(project: ProjectCreate):
    """创建新项目"""
    return project_service.create_project(project.name, project.description)


@router.get("/", response_model=List[ProjectInfo])
async def list_projects():
    """列出所有项目"""
    return project_service.list_projects()


@router.get("/{project_id}", response_model=dict)
async def get_project(project_id: str):
    """获取项目详情"""
    project = project_service.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    return project


# ========== Layer 1 相关 ==========

@router.get("/tags/library")
async def get_tag_library():
    """获取标签库"""
    return layer1_service.get_tag_library()


@router.post("/premise/generate", response_model=PremiseResponse)
async def generate_premise(request: PremiseRequest):
    """生成前提候选"""
    candidates = await layer1_service.generate_premise_candidates(
        request.tags, request.count
    )
    return PremiseResponse(candidates=candidates)


@router.post("/premise/validate")
async def validate_premise(premise: str):
    """验证前提"""
    valid, message = layer1_service.validate_premise(premise)
    return {"valid": valid, "message": message}


@router.post("/{project_id}/layer1")
async def save_layer1(project_id: str, data: Layer1Data):
    """保存 Layer 1 数据"""
    success = project_service.save_layer1(project_id, data)
    if not success:
        raise HTTPException(status_code=500, detail="保存失败")
    return {"message": "Layer 1 已保存"}


# ========== Layer 2 相关 ==========

@router.post("/summary/generate", response_model=SummaryResponse)
async def generate_summary(request: SummaryRequest):
    """生成段落摘要"""
    return await layer2_service.generate_summary(
        request.premise, request.ending_type
    )


@router.post("/outline/generate", response_model=OutlineResponse)
async def generate_outline(request: OutlineRequest):
    """生成大纲"""
    chapters = await layer2_service.generate_outline(
        request.summary, request.num_chapters
    )
    return OutlineResponse(chapters=chapters)


@router.post("/{project_id}/layer2")
async def save_layer2(project_id: str, data: Layer2Data):
    """保存 Layer 2 数据"""
    success = project_service.save_layer2(project_id, data)
    if not success:
        raise HTTPException(status_code=500, detail="保存失败")
    return {"message": "Layer 2 已保存"}
