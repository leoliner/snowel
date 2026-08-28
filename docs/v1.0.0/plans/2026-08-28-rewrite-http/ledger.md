# Step 5 rewrite_query + streamable HTTP 计划 ledger（2026-08-28-rewrite-http）

> 归档自 `.superpowers/sdd/plan/progress.md`（live ledger，worktree 已删）。计划：同目录 `plan.md`（2026-08-28 批准）。

## 1. 执行总览

| 项 | 值 |
|---|---|
| 分支 | feat/rewrite-http（worktree `D:\Code\snowel-rewrite-http`，已删）→ merge --no-ff 回 dev-1.0.0 @ 6858af9 |
| 提交链 | c31fd05 (T1 rewrite) → 28f80af (T1 封闭性修复) → 1ebb159 (T2 HTTP) → 064cf89 (T2 IPv6/字节比较修复) → 7e5cd84+37ac799 (T3 minor+落锚) |
| 模式 | Subagent-Driven，3 任务；T1/T2 各经 1 轮修复环，T3 首轮 Approved |
| 测试基线 | 后端 318→**328**（净增 10）、前端零改动（合并后复跑 vitest 91 + build 绿）；合并后主仓库 editable 重装全量复跑确认 |
| 验收闭环 | addendum §5 全兑现：rewrite_query 默认开+三入口统一+失败回落审计+关闭纯确定性（TC-RT-07 落锚）；MCP streamable HTTP 保守分层（`snowel mcp --http`、通配强制 token、401、枚举一致，TC-SH-12 落锚，79→**81 例**）；SH-① 响应键名统一 + reject_auto 注释纠错清账；schema 零变更、前端零改动 |

## 2. Ruling 裁决记录（决策—理由—若错的成本）

### 计划级（用户批准，详见 plan.md §4）

| # | 裁决 | 若错的成本 |
|---|---|---|
| R1 | rewrite 翻转 `llm/ports.py` 预留桩（签名扩 conn 读 config）；模型键 `retrieval.rewrite_model` 仿 small_model 先例；strip 非空校验 | 改签名同步桩测试一处 |
| R2 | 三入口统一 = `hybrid.search` 内前置（`backend=None` 关键字参保位置签名）；**api.search 不全量落审计**——仅改写发生（生效/失败）时落 `strategy="search"` 行，compose_context 并入既有行 | 要全量审计去掉条件一行 |
| R3 | FastMCP 原生 token 机制，不自写 middleware；预留 fallback 条款"不满足再换 auth=AuthSettings"——**执行中实际触发**（mcp 1.29.0 强校验 token_verifier 须伴随 auth），middleware 仍全 SDK 原生 | 已按预留条款消化，零返工 |
| R4 | CLI 新增 `snowel mcp` 子命令仿 web 形状；通配 host 无 token 拒启守卫在 shell 侧 | 挪入口同步文档 |
| R5 | SH-① 统一为 `event_seq`（merge 改名 + delete 补键）；reject_auto 注释按 acceptance-gap 执行-1 口径纠错 | 前端将来消费时再改成本更高 |

### 执行期追加

| # | 裁决 | 理由 | 若错的成本 |
|---|---|---|---|
| 执行-1 | T1 修复环：**conftest 特许扩入范围**——autouse fixture 包裹 `db.migrate` 预置 `retrieval.rewrite=false`（非依赖两 fixture：罩不住 shell 本地 project fixture 且避免双 tmp 库）；新 rewrite 测试回锚 true + "未 set 时 get 返回 True"默认值断言保 TC-RT-07 语义 | 默认开使既有 ~8 条路径真实穿越 litellm（真实 key 下发真调用、套件失封闭性）；migrate 层注入点全覆盖（复审 grep 实证） | 无（回锚保语义） |
| 执行-2 | T2 计划外 3 行（test_cli import rules 预热）**追认保留**——修既有子集顺序依赖（`_restore_ext_registries` 把内置规则误判为污染），干净树聚焦即红 | 测试卫生正收益非范围蔓延；评审同判 | revert 即可 |
| 执行-5 | T3 两处文档裁量：TC-SH-12 覆盖列取 `增补 §5.2 / §7.2` 非 C10/铁律5（零租约断言，挂上即虚登记）；§11.3 删两条失效豁免（streamable HTTP/rewrite_query 转正后自然失效） | 防虚登记与 §11 内部矛盾；评审核实均正确 | 无 |

## 3. 挂账表

| L 项/新登记 | 内容 | 状态 | 承接 |
|---|---|---|---|
| SH-① | 拍操作响应键名统一 | **关闭**（R5 兑现，两壳 `event_seq` 形状一致） | — |
| reject_auto 注释 | "→ 500"应为"→ 200（假成功）" | **关闭** | — |
| RW-① | **mcp 依赖下限 `shell/pyproject.toml` `mcp>=1.2,<2` 已陈旧**——新代码消费的 SDK 面（token_verifier/auth 构造参、AccessToken、streamable_http_client 注入参）1.2 时代不存在，装旧版连 stdio 一起崩 | 新登记（ride，终审判定不阻塞） | **Step 8/L16 依赖锁定**（提 `>=1.29` 或锁版） |
| RW-② | `--host` 带方括号形态（"[::1]"）二次包裹构造崩；IPv6 zone ID RFC 6874 未处理——守卫集合外极端边缘 | 新登记（ride） | Step 6/7 polish 波 |
| RW-③ | 默认开 × 无 key 环境生产语义：每次 api.search 白付一次快速失败 + 落一条 rewrite_failed 审计行（规格内行为） | 记录性 | **Step 6 手册必写**：无 key 用户建议关 `retrieval.rewrite` |
| RW-④ | `rewrite_query` 的 `context` 参数未入 prompt（R1 桩签名同构保留）；TC-RT-07 "rewrite_failed 标记"为 addendum 规范简称（实际载荷 `{"failed": true}`，README 已消歧） | 记录性 | 注释标注 + Step 7 终核括注 |
| T1 复审 | migrate 层预置固有权衡：同项目二次 open 静默重置 rewrite=false（当前套件无此形态） | 记录性 | 触发时处理 |
| L16 / L26 / L27 | 发布债 / 记录性 / 卫生项（L16 现含 RW-①） | 开放 | Step 8 / — / 专门时机 |

## 4. 终审修复波

- T1 修复环（c31fd05..28f80af）：Important×1（默认开致套件失封闭性）——conftest migrate 层预置 + 5 例回锚/撤键；复审全绿（litellm 真实尝试 7→0 实证）。
- T2 修复环（1ebb159..064cf89）：Important×1（IPv6 `::` 携 token 构造崩）+ Minor×2（非 ASCII token 500、host 透传断言）——方括号 URL + 字节比较 + 断言补齐；复审全绿。
- 终审（全分支 34703dd..37ac799）：**Yes（可合并）**——Critical×0、Important×0、Minor×4 全 ride（RW-①～④）。终审席独立复跑 328 passed 无新噪声；三入口收敛/审计双消费/conftest 封闭性抽验/HTTP 安全姿态全链路实证；schema 零变更、前端零改动、monkeypatch 锚未破。

## 5. 覆盖口径备忘

黑盒用例 **79→81 例**（TC-RT-07 落 §7 RT 域、TC-SH-12 落 §9 SH 域；§11.1 E3 行 +07、§11.2 §6 行 01–07、§7.2 行 +12；§11.3 两条失效豁免删除）；tests/README.md retrieval/shell 行反向索引同步（grep 实证零虚登记，评审逐锚验证）。AGENTS.md 阶段指针随本 ledger 归档同步更新。
