# v1.0.0 验收交接文档（handoff-acceptance-01）

> 写于 2026-08-26，Web 计划合入后。新会话从本文件 + AGENTS.md 阶段指针 + memory（snowel-v1-todo）恢复，执行 v1.0.0 验收链。
> **性质**：v1.0.0 全部四步实现计划已完成，本链是验收与发布准备，不再有大型实现计划（L22 小补包走补丁即可，无需拆大计划）。

## 1. 当前状态

| 项 | 值 |
|---|---|
| 分支 | dev-1.0.0 @ b6d331b（已推送 origin） |
| 已完成计划 | core（08-23）→ MCP/CLI 壳（08-24）→ 回写环+检索+生成环（08-24/25 两波）→ 级联检查（08-25）→ Web 三栏（08-25，单会话 T1-T14+终审修复波） |
| 测试基线 | 后端 252/252 + 前端 vitest 71/71 + `npm run build` 绿（主目录合并后复验过） |
| 环境 | 主仓库 editable 已指向 `D:\Code\snowel`；`web/` 需 node ≥18，首次 `cd web && npm install` |
| 挂账 | L1–L19 全部关闭；开放：L16（发布债）、L20（测试卫生）、L21（检索统一）、L22（验收小补）——明细见各计划 ledger，汇总在 AGENTS.md |

## 2. 验收链（顺序执行）

### 2.1 黑盒用例 66 例终核

- 基准：`docs/v1.0.0/testcases.md`（10 域 66 例 + 覆盖矩阵 §11）。
- 做法：逐域核对每例是否有测试锚（tests/README.md §1 有反向索引）；发现的缺口记清单——小缺口并入 2.2 补丁，大缺口（不应有）回报用户裁决。
- 注意：§11.3 已知豁免（rewrite_query、E4 扩展包等）不算缺口；Web 域 TC-SH-08 的浏览器级呈现属 2.3 人工走查。

### 2.2 L22 小补包（一个补丁计划或单次 dev-workflow 小执行）

清单（全部小改动，终审 triage park 项）：
1. favicon 模板紫替换（`web/public/favicon.svg` → token 琥珀系 SVG，一行资产）
2. `POST /api/writeback/reject_auto` 条目形状校验（畸形二元组 500 → 400，一行 ValueError）
3. ProseEditor 空态"去生成"死按钮接线（`onGoGenerate` → `setWorkspaceTab('proposals')`，一行）
4. `/api/chat` 聚合端点 `iterate_in_threadpool` 化（阻塞事件循环 → 一行 await 化）
5. ForeshadowMap 高拍数（>30）x 轴溢出（slot 下限改上限，一行）
6. sse.ts 非 2xx 文本回落死代码清理（先 text 再 JSON.parse 或删误导注释）
- 顺带可选：L20（session 级 autouse fixture 停心跳线程）、L21（api.search limit 统一为 100）。

### 2.3 真浏览器人工走查（用户主刀，助手可陪跑）

```bash
# 构建前端产物 + 启动（生产形态）
cd web && npm install && npm run build && cd ..
snowel web --project <测试项目路径>          # 默认 127.0.0.1:8642，浏览器打开
# 或开发形态：cd web && npm run dev（vite proxy /api → 8642，另起 snowel web）
```

走查清单（ui-design-01 §7 尾项）：暗色整体一致性；对比度 WCAG（正文 ≥7:1、次要 ≥4.5:1）；1280px 与 1920px 布局；骨架屏/空态/错误反馈；中文输入法聊天（IME Enter 不误发）；SSE 流式体验（工具卡片渐进 + 打字机 + 中断）；正文编辑（加载/未保存圆点/切章确认）；封卷/否决二次确认。发现项记清单并入补丁。

### 2.4 L16 发布债（发版前）

- Windows python.org 构建扩展加载崩（jieba/sqlite-vec 族）验证与规避；
- core/壳（snowel-core + snowel CLI/MCP/web）同步发包方案。

### 2.5 v1.0.0 发布

- dev-1.0.0 → main PR（**建 PR 须用户发话**；merge commit 保历史）；
- main 打 tag v1.0.0；发布说明素材：四计划 ledger 总览 + 66 例覆盖矩阵。

## 3. 新会话恢复入口

1. AGENTS.md（每会话必读）——阶段指针已指向验收链 + L 项汇总。
2. memory `snowel-v1-todo`——同口径 + 写计划教训清单。
3. 各计划 `docs/v1.0.0/plans/<plan>/ledger.md`——Ruling 全录与挂账明细。
4. 本文件——验收链操作单。

## 4. 注意事项

- 主仓库 pytest 前确认 editable 指向（`python -c "import snowel_core; print(snowel_core.__file__)"` 应为 `D:\Code\snowel\src\...`；若曾在别的 worktree 装过，重跑 `pip install -e . -e ./shell`）。
- `web/node_modules` 不在 git（首次 npm install）；`web/dist` 由 build 产出、后端存在才挂载。
- 验收期间发现 bug：小修直接在 dev-1.0.0 走 dev-workflow 小执行（补丁任务 + 测试 + 提交）；建 PR 前不合并无关改动。
