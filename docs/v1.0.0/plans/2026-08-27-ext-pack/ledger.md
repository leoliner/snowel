# Step 2 扩展包机制计划 ledger（2026-08-27-ext-pack）

> 归档自 `.superpowers/sdd/plan/progress.md`（live ledger，worktree 已删）。计划：同目录 `plan.md`（2026-08-27 批准；用户裁决 R1 修订版：放开 jsonschema 依赖、schema.json 采用标准 JSON Schema）。

## 1. 执行总览

| 项 | 值 |
|---|---|
| 分支 | feat/ext-pack（worktree `D:\Code\snowel-ext-pack`，已删）→ merge --no-ff 回 dev-1.0.0 @ 37baa4a |
| 提交链 | 147babb (T1 发现解析) → 9c064fe (T1 修复) → 5c4e12b (T2 事件面) → c13c815 (T3 hooks+CLI) → 9368d9f (T3 执行-2 修复) → eebb50a (T4 minor) → 614f2e1 (终审修复波) |
| 模式 | Subagent-Driven，4 任务；T1/T3 各经 1 轮修复环，T2/T4 首轮即 Approved |
| 测试基线 | 后端 280→**305**（净增 25）、前端 vitest 74/74 + build 绿；合并后主仓库 editable 重装全量复跑确认 |
| 验收闭环 | TC-EX-01–05 五例测试锚全落（tests/extensions/ 三件 + tests/shell/test_cli.py）；L24 关闭；conftest fastapi 条件化落地（core-only 模拟态实证 261 passed + web 整文件 skip） |

交付面：`src/snowel_core/extensions/`（discovery.py 双位置发现解析 + mounting.py 挂载编排）、`extensions` 投影表 + 两事件 handler、groups/engine `unregister`、api 四门面 + open/init 重载接线、CLI `snowel ext list/mount/unmount/status`。

## 2. Ruling 裁决记录（决策—理由—若错的成本）

### 计划级（用户批准，详见 plan.md §4）

| # | 裁决 | 若错的成本 |
|---|---|---|
| R1 | **用户修订版**：schema.json = 标准 JSON Schema 外壳；jsonschema 库校验片段合法性（依赖入 core pyproject）；合法片段映射构 pydantic 组模型复用 groups.validate 四态链路；digest=sha256(原文字节)；不支持 keyword 收集跳过警告 | 映射漏常用 keyword 在 mapping 处纯增量补 |
| R2 | hooks 协议照 design §8 `register(registry)`，registry 仅 `rule(name, fn, tiers)`；错误隔离以**包为单位**回滚（暂存→统一提交→败则 unregister 已进者） | 条级隔离改 collection 为逐条提交，数行 |
| R3 | 启动重载挂 core `open()`/`init_project()` 尾部（进程态填充不触库），整体吞错转警告；digest 不一致→不激活须显式 re-mount；孤儿降级状态保持 mounted | 调用点外移即可，函数位置不动 |
| R4 | 卸载引用校验只查 active=1 节点组键（json_extract IS NOT NULL），文案列 id 封顶 10+总数 N；失效节点不拦 | 全量拦截去掉 WHERE 一处 |
| R5 | mount 顺序：manifest+建模全成功→落事件投影→进程注册；hooks 失败仅降级返回 warnings 不阻断挂载 | hooks 必须健康才能挂则前置 dry-load |

### 执行期追加

| # | 裁决 | 理由 | 若错的成本 |
|---|---|---|---|
| 执行-1 | unmount 引用校验的组名集合 = 现场 parse_manifest(包目录) 的 groups 键；孤儿（目录缺失）跳过校验直接放行 | addendum 定死 mounted 载荷 `{name,version,source_path,schema_digest}` 无组名清单，状态表无组名列 | 未来要求校验孤儿卸载则扩投影表列一处迁移 |
| 执行-2 | unmount 成功路径必须撤本包 hooks 规则——API 实例记账 `_active_rules: dict[pack, list[rule]]`，mount/reload 记账、unmount pop 清账逐名 engine.unregister；否决"现场 load_hooks"方案 | T3 实现者自查发现缺口：残留规则继续产生 Violation 属行为面偏差违背卸载降级语义（非警告域）；记账方案孤儿场景也干净且无新噪声 | 两调用点漏记账则单包规则漏撤（双锁定测试已防） |
| 终审-1 | pattern 可移植性前置预检不用 `re.compile`（fixer 实证任务书回归用例 `(?!《》).+` 可过 Python re），改用与挂载期同源的 pydantic 微型探针试编译；ECMA-only 正则误杀为知情接受 | 探针与构模期同一机制，凡挂载会炸必被拦下；Step 3 制作 skill 将教可移植语法 | 误杀边角见 §3 新登记项① |
| 终审-2（偏差采纳记录） | digest 不跟随实际作用于**全部 scope**（addendum §3.1 字面只限全局包升级）——保守超集，方向正确 | 实现自然形态；Step 3 skill 描述升级语义时按此口径 | 若要求项目内目录改动免 re-mount，放宽 discover 比 one 点即可 |

## 3. 挂账表

| L 项/新登记 | 内容 | 状态 | 承接 |
|---|---|---|---|
| L24 | TC-EX 扩展包机制全域 | **关闭**（本计划全兑现，五例有锚） | — |
| L16 | Windows python.org 构建扩展加载崩 + 同步发包 | 开放（未携带） | Step 8 |
| L25 | 壳端暴露部分（Web 灵感/拍操作、MCP advanced） | 开放（未携带） | Step 4 |
| L26 | chat 召回 hybrid 默认 20 有意上限 | 开放（记录性，勿再报） | — |
| L27 | pydantic_settings 'lifespan' 前向引用警告 | 开放——**本步实测定位为第三方库内部路径非本项目代码**，从"顺手修"降级专门时机 | 后续小计划或 Step 7 再评估 |
| EX-① | 终审-1 探针两理论误杀边角：pattern 声明在非 string 字段 / string 字段 enum+pattern 同现（均 schema 坏味输入，知情伞内） | 新登记（ride） | Step 3 skill 教 pattern 规范时一并约束写法 |
| EX-② | 规则/组扁平命名空间遮蔽：hook 名撞内置或他包，unmount/unregister 连根拔掉原有主，重启自愈（终审 M-1）＋元字符组名 json_extract 漏检方向偏宽容（T2-②） | 新登记（ride，同根源合并处置） | Step 3 skill 立组名/规则名约定（如 `<pack>` 前缀）；或后续 parse 入口拒非标识符 |
| EX-③ | discovery 警告池模块级 drain 归因漂移：list/status 内部 discover 注入不清空、mount 全量 drain 算旧账；现管理面仅 CLI 单命令进程爆炸半径小（终审 M-3） | 新登记（ride） | **Step 4 壳端暴露评审必查项**——长驻进程触碰 api.list/status 时升级为必修；per-instance 注册表决策同步做 |
| EX-④ | 其余 ride 小项：阴影包建议性警告双入池、_scope_of global 正路零测、discovery docstring 措辞滞后、status 未挂载文案双报、test_web_server E402 固有代价、conftest except 口径宽于 importorskip、跨实例撤已撤名（no-op 安全实证）、reload 中途半注册 best-effort 兜底已在 | 记录性（明细见 live ledger 已随工作区删除，此处留目） | 终审 triage 全判 ride，无承接硬期限 |

顺带完成（非挂账）：tests/shell/test_cli.py 差分回退 fixture（EX 挂账顺手清）；core-only 测试能力本身（pytest importorskip 只吞 ModuleNotFoundError 的发现已记录于任务报告）。

## 4. 终审修复波

- 终审（全分支 65c904a..eebb50a）：**With fixes**——Critical×0、Important×2（I-1 mount 构模异常裸逃逸——check_schema 放行但 pydantic 编译 pattern 抛 SchemaError 致 CLI traceback；I-2 conftest api fixture 未隔家目录——本机全局包污染 17 个跨域测试文件进程态）、Minor×4（M-1 遮蔽连根拔/M-2 孤儿 stale 文案/M-3 警告池归因/M-4 高级 keyword 警告不全——除 M-2 外 triage ride）。TC-EX 五例语义逐字核对无缺项；R 系列裁决逐条有测试锁定。
- 修复 614f2e1（一提交三 finding）：I-1 双修（mount except 转 ValueError 文案链 + parse 前置探针试编译 fatal 化，附两条回归）；I-2 session 级 autouse 家目录隔离（HOME/USERPROFILE/Path.home 三钉，teardown 对称回填）+ test_cli 差分回退收口；M-2 孤儿行 digest_matches=None + CLI stale 分支收紧。聚焦 37 passed、全量 302→**305**。
- 定向复审：三条全 ADDRESSED、无新 Critical/Important 破坏。Out-of-scope 两条转录 §3 EX-① 与纯风格空行（不再记）。
