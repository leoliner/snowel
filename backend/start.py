#!/usr/bin/env python3
"""Snowvel 启动脚本"""
import uvicorn
import sys
from pathlib import Path

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent))

# 切换到 backend 目录作为工作目录
import os
os.chdir(Path(__file__).parent)

if __name__ == "__main__":
    print("❄️  Snowvel 雪花写作法 - AI 辅助小说创作系统")
    print("=" * 50)
    print("启动服务中...")
    print("访问: http://localhost:8000")
    print("API文档: http://localhost:8000/docs")
    print("=" * 50)

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )
