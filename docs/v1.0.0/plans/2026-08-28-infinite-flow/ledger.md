# Step 3 预制无限流扩展包 + skill 双落计划 ledger（2026-08-28-infinite-flow）

> 归档自 `.superpowers/sdd/plan/progress.md`（live ledger，worktree 已删）。计划：同目录 `plan.md`（2026-08-28 批准，含向 `~/.agents/skills/snowel-extension/` 落全局副本授权）。

## 1. 执行总览

| 项 | 值 |
|---|---|
| 分支 | feat/infinite-flow（worktree `D:\Code\snowel-infinite-flow`，已删）→ merge --no-ff 回 dev-1.0.0 @ 53fc674 |
| 提交链 | b94d576 (T1 真包+冒烟) → 8bed662 (T2 fixture 真包化) → 4ae2b21→bbd6e01 (T3 skill 双落+修复环 amend) → 78c9b72 (终审修复波) |
| 模式 | Subagent-Driven，3 任务严格串行；T1/T2 首轮即 Approved，T3 经 1 轮修复环 |
| 测试基线 | 后端 305→**309**（净增 4 冒烟）、前端 vitest 74/74 + build 绿；合并后主仓库 editable 重装全量复跑确认；src/ 零改动 |
| 验收闭环 | addendum §3.2–§3.3 全兑现：预制薄包 `extensions/infinite-flow/`（四组+示范规则+README）、`extensions/SKILL.md` 162 行双落（全局 cmp 逐字节一致）、根 README 一行指针、TC-EX-01–04 主锚真包化（TC-EX-05 保留合成）；EX-①② 挂账随 skill 关闭 |

## 2. Ruling 裁决记录（决策—理由—若错的成本）

### 计划级（用户批准，详见 plan.md §4）

| # | 裁决 | 若错的成本 |
|---|---|---|
| R1 | 四组字段细则定稿（组名 `flow_` 前缀；enum 示范在 status/direction、pattern 示范在 description `^.+`；不写未映射 keyword 防教学误导）——字段表见 plan §4.1 | schema.json 一处 + 断言，纯数据 |
| R2 | 示范规则 `flow_rank_track_direction_required`：direction 在 schema 上**刻意 optional**、hooks 规则管"写入须附"——形状归 schema、语义归 hooks 的正统分工示范 | 教学效果弱化，改规则一条 |
| R3 | fixture 迁移 = 真包**只读 copytree** 到 tmp 挂载（不原地挂载、不直连）；TC-EX-01 全局侧改 version 副本造同名异 digest；TC-EX-05 与畸形场景保留合成 | 用例语义漂移 → 断言微调，评审锁定 |
| R4 | skill 同步机制 = **文件复制**（Windows 软链不可靠：mklink 需特权、Git Bash ln -s 退化为复制）；代码库 `extensions/SKILL.md` 为唯一源，头部写同步命令；Task 3 实际落全局副本 | 两副本漂移 → 同步命令显眼可见 |
| R5 | skill 六节大纲（定位载荷上限/目录双位置/schema 规范/hooks API/挂载校验卸载流程/测试发布）——覆盖面为验收硬标准，实现者行文自由 | 大纲漏点 → 评审按 addendum 六要点对照补 |

### 执行期追加

| # | 裁决 | 理由 | 若错的成本 |
|---|---|---|---|
| 执行-1 | T3 评审的 3 条 Minor（ECMA 术语/节选标注/非 string pattern 点名）随 2 条 Important 同轮顺手收口 | 同文件同性质措辞级，分开修多一轮独立评审无增益 | 无（纯措辞准确性提升） |
| 执行-2 | 终审 Yes-to-merge 下仍做 3 Minor 小修复波（skill 新包措辞消歧/pycache 卫生/真包分发物去内部编号） | 分发物自足性对用户可见品质有实际收益，一行级成本 | 无 |

## 3. 挂账表

| L 项/新登记 | 内容 | 状态 | 承接 |
|---|---|---|---|
| EX-① | pattern 可移植写法约束 | **关闭**（真包示范 + skill §3/L147/L156 教程三处落实） | — |
| EX-② | 组名/规则名约定（`<前缀>_`、拒元字符） | **关闭**（真包 `flow_` 示范 + skill §3/§4/§7 落实，含同名遮蔽连根撤销警示） | — |
| EX-③ | discovery 警告池归因漂移 + per-instance 注册表决策 | **开放——Step 4 preflight 必查**（Web 常驻进程会放大暴露面） | Step 4 |
| EX-④ | ride 小项：冒烟 startswith 死断言、SNOWEL_PROJECT 回落未提（Step 6 手册章节补更合适）、skill stale/孤儿豁免措辞（§5 已覆盖） | 记录性 | Step 6 / 顺手 |
| L16 / L25 / L26 / L27 | 发布债 / 壳端暴露 / 记录性 / 卫生项 | 开放（未携带） | Step 8 / Step 4 / — / 专门时机 |

顺带完成（非挂账）：tests/README.md 反向索引补 `test_infinite_flow_pack` 行；`_copy_pack` 四处 `ignore_patterns("__pycache__")` + 真包目录清扫 fixture（终审修复波收口）。

## 4. 终审修复波

- 终审（全分支 62e82c1..bbd6e01）：**Yes（可合并）**——Critical×0、Important×0、Minor×3（skill 新包措辞/pycache 卫生/分发物内部编号）；skill 15+ 处最易漂移技术断言经源码逐条核验无失实、迁移判定为"强迁移"（EX-01/02/04 断言只增不减）、真包经 parse→build→CLI 生命周期→规则混跑全链路实证、终审席实跑全量 309 passed 与 cmp 副本一致。
- 修复波 78c9b72（单提交三 fix）：M-1 skill §2 新包消歧一句（全局副本重新 cmp 一致）；M-2 `_copy_pack` 四处 ignore_patterns + 冒烟 autouse 清扫 fixture（`find extensions -name __pycache__` → 0）；M-3 hooks.py docstring 与 README 去内部编号换自足表述（schema.json 未动 digest 不变、skill §4 代码块程序化比对无需同步）。
- 定向复审：三条全 ADDRESSED、无新 Critical/Important 破坏（现存命令名逐个对照 cli.py 复核、真包目录 R 系编号零匹配）。
- T3 修复环（前置于终审）：2 Important（skill 教了不存在的 `snowel open`/`snowel rebuild` 命令——教学文档技术性错误）+ 3 Minor（执行-1 裁量随轮），bbd6e01 amend 修复，定向复审 5/5 ADDRESSED。

## 5. 覆盖口径备忘

黑盒用例口径不变（9 域 76 例；TC-EX-01–05 五例实现锚由合成 fixture 迁至真包主锚，TC-EX-05 双场景仍合成——"真包是好的，演不了坏"）。AGENTS.md 阶段指针随本 ledger 归档同步更新（Step 3 完成 → Step 4 壳端暴露为下一步）。
