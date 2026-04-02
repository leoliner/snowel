"""应用配置管理"""
import os
from pathlib import Path
from pydantic_settings import BaseSettings

BASE_DIR = Path(__file__).resolve().parent.parent.parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)

class Settings(BaseSettings):
    APP_NAME: str = "Snowvel"
    DEBUG: bool = True

    # 数据存储路径
    DATA_PATH: Path = DATA_DIR
    PROJECTS_PATH: Path = DATA_DIR / "projects"
    CONFIG_PATH: Path = DATA_DIR / "config.json"

    # 加密密钥存储
    ENCRYPTION_KEY_PATH: Path = DATA_DIR / ".key"

    # 默认 AI 配置
    DEFAULT_AI_MODEL: str = "kimi-k2-5"
    DEFAULT_AI_BASE_URL: str = "https://api.moonshot.cn/v1"

    class Config:
        env_file = ".env"

settings = Settings()

# 确保目录存在
settings.PROJECTS_PATH.mkdir(exist_ok=True)
