# Snowel Web UI（web/）

前端独立工程（Vite + React 18 + TypeScript + Tailwind CSS），构建产物 `web/dist`
由后端 FastAPI 静态 serve（`snowel web`，SPA fallback）。

## 前置

- Node.js ≥ 18（开发环境实测 v24）
- 后端服务：`snowel web`（默认 127.0.0.1:8642）

## 命令

| 命令 | 说明 |
|---|---|
| `npm install` | 安装依赖 |
| `npm run dev` | 开发服务器（vite proxy `/api` → `http://127.0.0.1:8642`） |
| `npm run build` | 类型检查 + 构建 → `web/dist`（后端静态 serve 该目录） |
| `npm run test` | vitest 单测（jsdom） |

## 目录

- `src/App.tsx`：三栏布局壳（顶栏 + 左流程树 / 中正文 / 右工作区+聊天）
- `src/api.ts`：`api.get/post` 薄封装（错误抛响应 `detail`）+ `useApi(path)` 数据获取 hook
- `src/types.ts`：与后端响应一比一的类型面
- `src/components/`：组件（`SessionBanner` 只读横幅；其余 T10–T13）
- `tailwind.config.ts`：ui-design-01 §2 语义 tokens 唯一映射源（组件禁裸色值，§6）
- `tailwind.config.test.ts`：token 防漂移锚（ui-design-01 §7）
