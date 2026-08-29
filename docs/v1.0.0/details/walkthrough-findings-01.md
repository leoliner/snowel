# 人工走查发现清单（walkthrough-findings-01，进行中）

> 开始：2026-08-29。走查人：老大（浏览器黑盒主刀）+ 小弥夏（陪跑复现记清单）。
> 规约：每条一句话 + 复现路径 + 机制定位；全部收集后按 dev-workflow 开修复波计划 → 合并推送 → 回归确认（handoff §6）。
> 环境：dev-1.0.0 @ baa7458，服务 `snowel web` @ 127.0.0.1:8642，项目 `D:\Code\snowel-walkthrough`（空项目）。复现视口 1280×800（正常视口即复现，非矮窗口特有）。

## 1. 发现项

| # | 严重度 | 一句话 | 状态 |
|---|---|---|---|
| W-1 | P0 | tour 气泡定位系统性错误：步骤 1/2 正文被顶出视口、按钮不可点；步骤 5 目标缺失气泡漂移 | 已复现（数值实证） |
| W-2 | P1（UX） | 正文编辑区无视觉容器：空项目下中间栏看不出正文在哪里写 | 已复现 |
| W-3 | P1（bug） | 空态"去生成"是死按钮：点击后 UI 零变化 | 已复现 |
| W-4 | P0 | 无 LLM 凭据时 `POST /api/generate` 裸告 500，前端红条无指引 | 已复现（服务端 traceback + 前端红条） |
| W-5 | P2 | 矮窗口（高约 500px）下组件裁切看不全，无响应式适配 | 用户报告，未逐项复现 |
| W-6 | P0（设计） | **页面完全体现不出雪花法逐层递进方法论**：不知道第一步做什么、层与层的关系、当前层完成后下一步去哪——唯一引导面（tour）恰是坏的（W-1） | 用户走查总评 |
| W-7 | P0 | **Web 无 LLM 配置入口**：打开页面后第一件该做的事（确认模型可用）无处可做，只能撞上 W-4 的 500 才知道没配；配置入口只存在于手册第 12 章 | 用户走查发现 |
| W-8 | P1（UX） | 生成表单裸露 `locate`/`extra` 两个原始 JSON 输入框——开发者调试参数不是作者语言；作者不知道 JSON 语法与键名约定 | 用户走查发现 |

**走查结论（2026-08-29，用户裁决）**：W-6/W-7/W-8 叠加表明 Web 界面需要**重新设计与重构**。流程定为：按 `sim-walkthrough-01.md` 逐步绘制 Web demo → 逐屏向用户确认调整与后端交互 → **设计稿定稿后统一修复**（W-1～W-8 全部纳入定稿后的修复波）。定稿前不改实现代码。设计过程文档：`details/web-redesign/`。

## 2. 复现与机制明细

### 2.1 W-1 tour 气泡定位（`web/src/components/Tour.tsx:107-117`）

| 步骤 | 目标 testid | 1280×800 实测 | 机制 |
|---|---|---|---|
| 1/6 三栏布局 | `app-main`（全高） | 气泡 top=**−105**，"下一步"按钮 y=−2（视口外，鼠标不可点） | 目标全高 → `rect.top+rect.height+8+200 < innerHeight` 恒 false → 上方分支 `translateY(-100%)` → 146px 气泡整体推出视口上沿 |
| 2/6 流程树 | `col-flow`（全高） | 同上（top=−105，按钮 y=−3） | 同上 |
| 3/6 生成表单 | `generate-form` | 正常（504–650） | 目标在视口内、矩形合理 |
| 4/6 提案确认 | `proposal-panel` | 正常（430–598） | 同上 |
| 5/6 正文编辑 | `prose-editor` | 气泡兜底钉在 (16,64)，**无高亮环** | 空项目不渲染 `prose-editor` → rect null → FALLBACK_POS，指向性丢失 |
| 6/6 | — | 未逐项测量 | — |

- 与视口高度无关：全高目标使 below 判定在任意 `innerHeight` 下失败（用户矮窗口 502px 下更雪上加霜：步骤 4 按钮也出视口，导览鼠标走不完）。
- MT-② 候选池（魔数 200 + BUBBLE_WIDTH 双源）是同一区域的已知挂账，本条升级为 P0。

### 2.2 W-2 正文区无框（`App.tsx` col-prose / `ProseEditor` 空态）

空项目中间栏实测：`prose-editor` testid 数 0、textarea 数 0，仅一行空态文案 + "去生成"按钮悬在整片空白中央。用户无从知道正文编辑会长什么样、在哪出现。

### 2.3 W-3 死按钮（`App.tsx:143`）

`onGoGenerate={() => setWorkspaceTab('proposals')}`——右栏默认就停在"提案"tab，点击前后 UI 状态逐字节相同（实测 before/after 全等）。L22#3 的修复只是把 no-op 换了个 no-op。

### 2.4 W-4 500 裸告（`shell/src/snowel/web_server.py` 错误映射面）

- 服务端：`generate → llm/backend.py litellm.completion → litellm.InternalServerError: Missing credentials ... OPENAI_API_KEY`——壳只映射 ValueError/SealedVolumeError/ProposalStateError 三类，litellm 异常直穿 → 500。
- 前端：红条"请求失败（500 Internal Server Error）"，无"该去配 key"的指引。
- 测试盲区：全部测试注入 FakeBackend，"无 key 生产默认"路径零覆盖。
- 同面端点：/api/expand/*、rewrite、chat 非流式等（chat 流式有 error 事件兜底不 500）。

## 3. 修复波候选方向（未裁决，仅备忘）

| # | 方向 | 量级预估 |
|---|---|---|
| W-1 | 重写气泡定位：目标不可见/缺失时改挂"锚点邻近或居中"，禁 translateY 出屏；按钮保证视口内；空目标步骤跳过或改全局提示 | 中 |
| W-2 | ProseEditor 空态给编辑器骨架容器（边框框体 + 引导文案） | 小 |
| W-3 | 去生成 → 滚动/focus 生成表单（或文案改"先去生成前提"并联动） | 小 |
| W-4 | 壳层错误映射补 LLM 凭据类异常 → 400 + 中文指引；考虑 /api/session 暴露 llm_configured 状态供前端置灰 | 小～中 |
| W-6 | 方法论可见性：FlowTree 层卡加"当前层待办 + 完成条件 + 下一步"行动指引；空态首屏直接引导生成前提 | **需专门设计裁决**（可能走 spec 小环） |

## 4. 待走查余项（handoff §3 其余清单项）

- [ ] 暗色一致性 / WCAG 对比度；1280 与 1920 布局
- [ ] 骨架屏 / 空态 / 错误反馈（W-4 已覆盖一角）
- [ ] 中文输入法聊天（IME Enter 不误发）
- [ ] SSE 流式体验（需 LLM key）
- [ ] 正文编辑全流程（需先有章节提案；当前被 W-6 卡住——用户无法自然走到的面）
- [ ] 封卷 / 否决二次确认
- [ ] 拍操作 / 手册弹窗（含 ch08/ch12 长表格）/ MT-①②③ 候选池
- [ ] 扩展包 CLI 走查、MCP stdio/HTTP 走查
- [ ] 手册内容"照做"口径复核（第 1 章快速上手）
