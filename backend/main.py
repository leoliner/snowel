"""Snowvel 后端主入口"""
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from pathlib import Path

from app.routers import config, projects

app = FastAPI(
    title="Snowvel",
    description="AI 辅助小说创作系统 - 雪花写作法",
    version="0.1.0"
)

# 注册路由
app.include_router(config.router)
app.include_router(projects.router)

# 静态文件和模板
BASE_DIR = Path(__file__).parent
STATIC_DIR = BASE_DIR / "frontend" / "static"
TEMPLATES_DIR = BASE_DIR / "frontend" / "templates"

# 如果前端目录存在，挂载静态文件
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/", response_class=HTMLResponse)
async def root():
    """首页 - 如果存在模板则返回，否则返回简单页面"""
    index_file = TEMPLATES_DIR / "index.html"
    if index_file.exists():
        with open(index_file, "r", encoding="utf-8") as f:
            return f.read()

    # 简单默认页面
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Snowvel - 雪花写作法</title>
        <meta charset="utf-8">
        <style>
            body {
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
                max-width: 800px;
                margin: 50px auto;
                padding: 20px;
                background: #f5f5f5;
            }
            .container {
                background: white;
                padding: 40px;
                border-radius: 12px;
                box-shadow: 0 2px 8px rgba(0,0,0,0.1);
            }
            h1 {
                color: #333;
                text-align: center;
            }
            .btn {
                display: inline-block;
                padding: 12px 24px;
                background: #4a90d9;
                color: white;
                text-decoration: none;
                border-radius: 6px;
                margin: 10px 5px;
            }
            .btn:hover {
                background: #357abd;
            }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>❄️ Snowvel</h1>
            <p style="text-align: center; color: #666;">
                AI 辅助小说创作系统 - 雪花写作法
            </p>
            <div style="text-align: center; margin-top: 40px;">
                <a href="/static/app.html" class="btn">开始使用</a>
                <a href="/docs" class="btn" style="background: #666;">API 文档</a>
            </div>
        </div>
    </body>
    </html>
    """


@app.get("/health")
async def health_check():
    """健康检查"""
    return {"status": "ok", "version": "0.1.0"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
