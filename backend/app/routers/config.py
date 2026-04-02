"""配置管理路由"""
from fastapi import APIRouter, HTTPException
from app.models.schemas import APIConfig, APIConfigResponse
from app.core.security import secure_storage

router = APIRouter(prefix="/api/config", tags=["配置管理"])


@router.get("/", response_model=APIConfigResponse)
async def get_config():
    """获取当前 API 配置（隐藏密钥）"""
    config = secure_storage.load_config()
    if not config:
        return APIConfigResponse(configured=False)

    # 隐藏部分密钥
    api_key = config.get("api_key", "")
    masked = "*" * (len(api_key) - 8) + api_key[-8:] if len(api_key) > 8 else "****"

    return APIConfigResponse(
        configured=True,
        base_url=config.get("base_url", ""),
        model=config.get("model", ""),
        api_key_masked=masked
    )


@router.post("/")
async def save_config(config: APIConfig):
    """保存 API 配置（加密存储）"""
    success = secure_storage.save_config(
        api_key=config.api_key,
        base_url=config.base_url,
        model=config.model
    )
    if not success:
        raise HTTPException(status_code=500, detail="配置保存失败")
    return {"message": "配置已保存"}


@router.delete("/")
async def clear_config():
    """清除配置"""
    secure_storage.clear_config()
    return {"message": "配置已清除"}
