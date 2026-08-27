# Step 1 core 功能债计划 ledger（2026-08-27-core-debt）

> 归档自 `.superpowers/sdd/plan/progress.md`（live ledger，worktree 已删）。计划：同目录 `plan.md`（2026-08-27 批准，R1/R1 边界裁决同批用户确认）。

## 1. 执行总览

| 项 | 值 |
|---|---|
| 分支 | feat/core-debt（worktree `D:\Code\snowel-core-debt`，已删）→ merge --no-ff 回 dev-1.0.0 @ e388269 |
| 提交链 | 64240d5 (T1 beat_deleted) → a9dbbef (T2 merge 语义+TOCTOU) → 7629a07 (T3 两阶段恢复+去重) → d111aec (T4 minor 包) → 731f445 (终审修复波) |
| 模式 | Subagent-Driven，4 任务，每任务两席评审（spec+quality）全 Approved，修环 0 轮 |
| 测试基线 | 后端 264→**280**（净增 16）、前端 vitest 74/74、`npm run build` 绿；合并后在主仓库全量复跑确认（editable 重装后） |
| 验收闭环 | TC-ON-17 落锚（testcases.md ON 域 16→17 例，§11.2 范围 01–17）；L23 关闭；L25 core 部分关闭；TOCTOU/两阶段恢复落地；core 侧 minor 池清空 |

## 2. Ruling 裁决记录（决策—理由—若错的成本）

计划级 R1–R5 已在 plan.md §4 预登记并经用户批准（R1 边界单独确认：delete 不查 active、引用检查只查 planted_at）。执行期追加：

| # | 裁决 | 理由 | 若错的成本 |
|---|---|---|---|
| 执行-1 | 恢复扫描不对 dsts 去重（pre-R5 历史提案落在崩溃窗口内可能补出平行边） | R5"单点防御"字面范围；正常路径生成入口已去重 | 一条 SQL 清平行边 |
| 执行-2 | delete_beat/merge_beats 的存在性/类型校验仍在事务外 | R3 窄域（addendum 只要求迁移预查入事务）；写租约下单进程写者 | 校验移入事务，两行 |

备忘（非挂账）：DERIVED_FROM 边存在性按 (src, dst, kind) 全行匹配——若未来引入撤回语义需回看（recover 与 confirm 共用判断）。

## 3. 挂账表

| L 项 | 内容 | 状态 | 承接 |
|---|---|---|---|
| L16 | Windows python.org 构建扩展加载崩 + core/壳同步发包 | **开放**（不携带，环境/发布债） | Step 8 |
| L23 | beat_deleted 事件 + 拍 active 语义（merge 两端校验、valid_until_beat 迁移、重复合并拒绝） | **关闭**（T1/T2 全部兑现） | — |
| L24 | TC-EX-01~05 扩展包机制（E4 全域） | **开放** | Step 2/3 |
| L25 | core 部分（TOCTOU + 两阶段恢复 + derive_from 校验测试）**关闭**（T3）；壳端暴露部分（Web 灵感/拍操作、MCP advanced）**开放** | 部分 | Step 4 |
| L26 | chat 召回界 hybrid 默认 20 是**有意上限**（显式记录，非 bug） | 开放（记录性，勿再报） | — |
| L27 | 全量套件 pydantic_settings `IncompleteFieldDefinitionWarning`（lifespan 前向引用；test_lease_integration 路径，先于本计划存在） | **新登记**（卫生项） | 后续计划顺手 |

顺带 minor：core 侧清空（T4：inspirations 排序/空文本校验/json 防御、extract_many 异常类型、路由组合测试）；derive_from 重复 id 平行边防御已落（生成入口去重）；catch-all grep 结论——api.py 7 处 json.loads 均解析核心自身写入列，无其他需修点。测试级备忘（无后续动作）：N>1 拒绝文案仅锁模板形态、test_merge_migrates_valid_until fetchone 无 ORDER BY（单事件场景确定）、恢复扫描 N+1 SELECT（项目规模无感）。

## 4. 终审修复波

- 终审（全分支 d94c99f..d111aec）：**With fixes**——R1–R5 全兑现、跨任务交互全核（delete 不查 active 与 merge 两端查 active 的 R1 分工自洽；beat_merged 载荷增键对历史事件重放安全；confirm 抽函数行为等价；恢复与 json 防御数据路径互不干扰）、TC-ON-17 三处锚点 grep 实证。Important×1（reason=None 载荷形态无测试断言——契约分支可被无检测突变）。
- 修复 731f445：`test_delete_beat_empty_succeeds` 追加无 reason 删除（mb3）+ 载荷全等断言 `{"beat_id": "mb3"}`（原 T1 实现者；聚焦 11/11、全量 280/280）。
- 定向复审：ADDRESSED、无新破坏，变异杀伤力核验（条件改无条件写键则全等断言必红）。终审 triage 8 项 deferred：1 项升级修复、7 项 leave-deferred（见 §3 备忘）。

## 5. 覆盖口径备忘

黑盒用例 **75→76 例**（TC-ON-17 落 ON 域，9 域口径不变；testcases.md 通篇无显式总数文案，仅 §11.2 范围 01–16→01–17）；tests/README.md foreshadow/flow/shell 行同步（终审 grep 实证非虚登记）。AGENTS.md 口径随本 ledger 归档同步更新。
