# Snowvel

**雪花写作法 meets AI-Powered Storycraft**

AI 辅助小说创作系统，基于 Randy Ingermanson 的雪花写作法（The Snowflake Method），帮助作者系统化地从灵感构建完整小说。

## ✨ 功能特点

- ❄️ **5层渐进式创作**: 从一句话前提到完整大纲的渐进扩展
- 🤖 **AI 辅助生成**: 集成 Kimi API（OpenAI 兼容），智能生成创意
- 🔒 **本地加密存储**: API 密钥本地加密，项目数据本地保存
- 🌐 **Web 界面**: 简洁直观的浏览器界面

## 🏗️ 系统架构

```
Layer 1: 灵感雪核 - 一句话前提 + 标签拼贴
Layer 2: 故事骨架 - 五句话摘要 + 一页大纲
Layer 3: 角色血肉 - 角色档案 + 关系图谱（开发中）
Layer 4: 场景脉络 - 场景卡片 + 技法标记（开发中）
Layer 5: 正文绽放 - 场景文本生成（开发中）
```

## 🚀 快速开始

### 1. 安装依赖

```bash
cd backend
pip install -r requirements.txt
```

### 2. 启动服务

```bash
python start.py
```

或直接使用 uvicorn：

```bash
uvicorn main:app --reload
```

### 3. 访问界面

打开浏览器访问: `http://localhost:8000/static/app.html`

## ⚙️ 配置 API 密钥

1. 点击右上角「配置」
2. 填入你的 Kimi API 密钥（从 https://platform.moonshot.cn/ 获取）
3. 密钥将加密存储在本地 `data/` 目录

## 📁 项目结构

```
snowel/
├── backend/
│   ├── app/
│   │   ├── core/          # 配置、加密
│   │   ├── models/        # 数据模型
│   │   ├── routers/       # API 路由
│   │   └── services/      # 业务逻辑
│   ├── frontend/
│   │   └── static/        # Web 前端
│   ├── main.py            # FastAPI 入口
│   └── requirements.txt
└── data/                  # 本地数据存储（自动创建）
```

## 📜 许可证

MIT License
