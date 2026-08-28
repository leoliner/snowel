# v1.0.0 范围扩容 Step 3：预制无限流扩展包 + snowel-extension skill 双落

> 日期：2026-08-28。来源：范围增补 `requirements-addendum.md` §3.2–§3.3 / §8（Step 3 行）——8 step 链第 3 步。
> 性质：内容交付计划——挂载机制 Step 2 已落地（`plans/2026-08-27-ext-pack/ledger.md`，L24 关闭），本步交付**数据（薄包）+ 文档（skill）**，src 预计零改动。四组字段细则与示范规则按 addendum 授权在本计划定稿（§4 R1/R2，随计划批准生效，勿执行期重开）。
> 上游素材：`details/sim-walkthrough-01.md` §第 5 步人物模板（无限流四组语义与林晚档案实例值）。

## 1. 背景与范围

| 项 | 内容 |
|---|---|
| 预制薄包 | 仓库 `extensions/infinite-flow/`：schema.json（四属性组）+ hooks.py（一条示范级联规则）+ README（结构说明 + 指向 skill + 林晚档案示例值）——既是示范包也是 TC-EX 测试素材 |
| skill 双落 | 代码库 `extensions/SKILL.md`（唯一源）→ 全局 `~/.agents/skills/snowel-extension/SKILL.md`（复制同步）；根 `README.md` 一行指针 |
| fixture 迁移 | TC-EX-01–05 测试 fixture 主锚从合成包换真包；畸形路径（TC-EX-05）保留合成 fixture |
| 挂账示范 | 包自身示范 EX-①（pattern 可移植写法）与 EX-②（组名/规则名 `<前缀>_` 约定）；skill 教升级语义按终审-2 口径（全 scope 不自动跟随、须显式 re-mount） |

不在范围：壳端暴露（Step 4——EX-③ 警告池归因漂移届时必查）；Web 手册扩展包章节（Step 6）；包分发/版本管理工具（薄包即目录，无发布机制）；core/shell 代码改动（机制已备，发现缺口停下问）。

## 2. Global Constraints

- 薄包边界（裁决 11 修订）：载荷只有属性组 + 级联规则两类；生成偏好、文风、角色模板不做。
- 领域逻辑只在 snowel-core；本步产物是数据文件与文档，**不碰 src/**——若实现中发现机制缺口（如映射表不够用），STOP 呈报控制器裁决，不得顺手扩机制。
- 包自身必须与 skill 教的约定互相印证（组名前缀、pattern 写法、升级语义口径），skill 示例直接引用真包。
- 每任务 TDD（T1 的冒烟测试先行）、conventional commits、文档与包分任务提交、中文注释/文档与仓库现有风格一致。
- 全量基线：dev-1.0.0 @ 62e82c1，后端 305 + 前端 74 + build 绿。

## 3. Preflight 挂账裁决（同版本已归档 ledger 全量双查：ext-pack ledger §3）

| 挂账 | 内容 | 裁决 | 去向 |
|---|---|---|---|
| EX-① | pattern 可移植写法约束 | **携带**——Task 1 包示范 + Task 3 skill 教程 | Task 1 / Task 3 |
| EX-② | 组名/规则名约定（`<前缀>_`、拒元字符） | **携带**——Task 1 包示范（`flow_` 前缀）+ Task 3 skill 立约 | Task 1 / Task 3 |
| 终审-2 | 升级语义偏差口径（全 scope 不自动跟随） | **携带**——skill 升级语义章节按此口径 | Task 3 |
| EX-③ | discovery 警告池归因漂移 | 不携带 | **Step 4 必查项** |
| EX-④ | 其余 ride 小项（阴影包警告双入池、docstring 滞后等） | 不携带（记录性） | — |
| L16 / L25 / L26 / L27 | 发布债 / 壳端暴露 / 记录性 / 卫生项 | 不携带 | Step 8 / Step 4 / — / 专门时机 |

任务间共享文件冲突：T1 产包 → T2 消费 → T3 引用（严格串行，无并行冲突）；tests 多文件改动集中在 T2 单任务内。

## 4. 计划级设计裁决（预登记 Ruling，随计划批准生效）

| # | 裁决 | 理由 | 若错的成本 |
|---|---|---|---|
| R1 | **四组字段细则定稿**（见 §4.1 表）。组名 `flow_` 前缀（EX-② 示范）；字段类型只用已映射词表（string/integer/number/boolean/array-of-string + enum/required/单个宽松 pattern）；约束力示范分工：enum 展示在 `status`/`direction`，pattern 示范在 `description`（保守语法 `^.+`），**不用 minimum/minimum 类未映射 keyword**（M-4 挂账：静默无效会教学误导） | addendum 授权拆计划时定；林晚档案提供全部示例值 | 字段增删改 schema.json 一处 + 对应断言，纯数据 |
| R2 | **示范规则**：`flow_rank_track_direction_required`——变更 fact 的 props 含 `flow_rank_track` 组键而 `direction` 缺失/空值 → major Violation（refs=[节点 id]）；`tiers=("full",)` 默认档。**direction 在 schema 上保持 optional**——形状归 schema、语义归 hooks 的正统分工示范（schema 管字段形状，规则管跨字段语义义务） | addendum §3.2 原话"排名轨迹组写入须附轨迹方向说明"；TC-EX-04 要求规则与内置规则同引擎运行 | 教学效果弱化；改规则一条函数 |
| R3 | **fixture 主锚迁移方式**：测试从仓库真包路径 `Path(__file__).parents[2] / "extensions" / "infinite-flow"` **只读 copytree** 到 tmp 项目 `extensions/` 后挂载（真包目录不原地挂载、不直连）；TC-EX-01 全局侧用真包副本改 version 字节制造同名不同 digest；TC-EX-05 两场景（schema 缺失 / hooks 语法错）与通用畸形小场景**保留合成 fixture**（真包是好的，演不了坏） | 主锚真包（addendum §3.2 字面）、畸形合成（同节"另造最小 fixture"）；copytree 保持测试零污染仓库工作区 | 个别用例语义漂移 → 断言同步微调，评审锁定 |
| R4 | **skill 同步机制**：代码库 `extensions/SKILL.md` 为唯一源，全局副本用**文件复制**同步（Windows 软链不可靠：mklink 需特权、Git Bash `ln -s` 退化为复制）；skill 头部维护说明写明同步命令（`mkdir -p ~/.agents/skills/snowel-extension && cp extensions/SKILL.md ~/.agents/skills/snowel-extension/SKILL.md`，仓库根执行）；Task 3 实际落一份到全局 | 双落是 addendum §3.3 定稿需求，批准计划即授权全局落点；软链在 Windows 是假选项 | 两副本漂移 → 头部同步命令显眼可见 |
| R5 | **skill 内容大纲**（Task 3 按 §4.2 展开，实现者行文自由、评审核大纲覆盖与与包一致性）：①定位与载荷上限（组+规则两类；生成偏好排除；"只装可信来源"）②目录结构与双位置（项目覆盖全局）③schema 规范（词表、pattern 可移植性+发现期拒绝行为、组名约定、版本对账：**数据不手写 `_schema`**，挂载侧 digest 管版本）④hooks API（`register(registry)` 协议、`rule(name, fn, tiers)`、fn 签名与 change 结构、包级回滚语义）⑤挂载/校验/卸载流程（ext 四命令、active 引用拦截、升级不自动跟随须 re-mount、错误隔离行为）⑥测试与发布建议（最小 fixture 自测、挂载冒烟） | addendum §3.3 六要点全落；与真包互证 | 大纲漏点 → 评审席按 addendum 六要点对照补 |

### 4.1 四组字段细则（R1 定稿，示例值取自林晚档案）

| 组名 | 语义 | 字段 | 类型 | 约束 | 林晚示例 |
|---|---|---|---|---|---|
| `flow_space_seniority` | 空间资历 | `entered_at` | string | required | `"首夜"` |
| | | `cycles` | integer | optional | `17` |
| | | `status` | string | enum `[active, escaped, lost, deceased]`，optional | `"active"` |
| `flow_rank_track` | 排名轨迹 | `current_rank` | integer | required | `480000` |
| | | `peak_rank` | integer | optional | `10000` |
| | | `direction` | string | enum `[ascending, descending, volatile, held]`，**optional（R2 规则管语义）** | `"descending"` |
| `flow_abilities` | 能力清单 | `abilities` | array of string | required | `["时滞"]` |
| | | `source` | string | optional | `"排名入前 1 万副本奖励"` |
| `flow_blindspot` | 盲区特权 | `description` | string | required + pattern `^.+` | `"已死过一次"` |
| | | `exploited` | boolean | optional | `true` |

schema.json 顶层：`name: "infinite-flow"`、`version: "1.0.0"`（discovery 要求非空字符串）；每组片段 `{"type": "object", "properties": {...}, "required": [...]}` 形态（build_group_models 消费 properties/required）。

### 4.2 hooks.py 骨架（R2）

```python
def register(registry):
    registry.rule("flow_rank_track_direction_required", _check)

def _check(change, conn):
    # fact kind=="node" 且 props 组键含 flow_rank_track：direction 缺失或空
    # → [{"level": "major", "rule": "flow_rank_track_direction_required",
    #     "message": "排名轨迹写入须附轨迹方向 direction", "refs": [节点 id]}]
```

实现细节（change/fact 精确结构、Violation 字典形态）照抄 `consistency/rules.py` 内置规则同款；规则名带 `flow_` 前缀（EX-② 示范）。

## 5. 文件结构总表

| 文件 | 动作 | 任务 |
|---|---|---|
| `extensions/infinite-flow/schema.json` | 新建（R1 细则） | T1 |
| `extensions/infinite-flow/hooks.py` | 新建（R2 规则） | T1 |
| `extensions/infinite-flow/README.md` | 新建（结构说明 + 指向 skill + 林晚示例 + 挂载命令） | T1 |
| `tests/extensions/test_infinite_flow_pack.py` | 新建（真包冒烟：parse 合法四组 / digest 稳定 / load_hooks 恰一条规则无警告） | T1 |
| `tests/extensions/test_discovery.py` | TC-EX-01 主锚换真包副本（R3） | T2 |
| `tests/extensions/test_mounting.py` | TC-EX-02/03 主锚换真包（mount 真包 → 写 `flow_rank_track` 数据 → validate 四态 / 卸载拦截 / 数据保留降级） | T2 |
| `tests/extensions/test_hooks.py` | TC-EX-04 主锚改真包规则触发（缺 direction → Violation；附 direction → 无）；TC-EX-05 保持合成 | T2 |
| `tests/shell/test_cli.py` | list 覆盖标记 / 挂载态用例换真包 | T2 |
| `tests/README.md` | 反向索引核对同步（新增 extensions 域冒烟行） | T2 |
| `extensions/SKILL.md` | 新建（R5 大纲全文，唯一源） | T3 |
| `~/.agents/skills/snowel-extension/SKILL.md` | 复制落盘（R4，仓库外副作用——计划批准即授权） | T3 |
| `README.md`（根） | +一行指针（实现者读现状选位，扩展包小节或安装节后） | T3 |

**共享文件冲突扫描**：串行 T1→T2→T3，T2 独占 tests/，T3 独占 SKILL 与 README；无跨任务同文件并行。

## 6. 任务清单

### Task 1: 预制无限流薄包（TC-EX 素材源）

**实现**：按 §4.1/§4.2 建 `extensions/infinite-flow/` 三件 + README；README 含四组字段速览表、林晚档案示例 props JSON、`snowel ext` 挂载命令、升级语义一句话（不自动跟随须 re-mount）、指向 `extensions/SKILL.md`。

**测试**（`tests/extensions/test_infinite_flow_pack.py`，先写失败测试）：
```python
def test_pack_manifest_parses_clean()      # parse_manifest(真包) → manifest 合法、
                                           # name=="infinite-flow"、四组齐、零致命警告
def test_pack_digest_stable()              # 两次 parse digest 一致（内容即身份）
def test_pack_hook_loads_single_rule()     # load_hooks → 恰 1 条 flow_rank_track_direction_required、
                                           # 零警告；Registry 面只有 rule()（EX-② 名字前缀示范断言）
def test_pack_group_models_build()         # build_group_models 四模型齐；required/Optional
                                           # 形状与 §4.1 表逐项一致（pydantic 断言）
```

### Task 2: TC-EX fixture 真包化迁移（R3）

**实现**：按 R3 迁移五例主锚；各文件保留/新建 `_copy_pack()` helper（copytree 到 tmp）；迁移原则——**TC-EX 用例编号的承载测试必须主锚真包**，非编号的通用小场景合成保留即可。

**迁移对照表**（实现者照此逐例核对，评审逐例验证）：

| 用例 | 迁移后形态 |
|---|---|
| TC-EX-01 | 真包 copytree 到项目侧 + 改 version 副本到全局侧 → scope=project 生效 |
| TC-EX-02 | mount 真包 → 已有节点零影响；新写 `flow_rank_track` 数据 validate 四态 ok |
| TC-EX-03 | 写含 `flow_space_seniority` 的活跃节点 → unmount 拒绝文案含节点 id；清引用后降级 unmanaged 且 props 原样 |
| TC-EX-04 | 真包规则：写缺 direction 的 rank_track → analyze 出 Violation 含规则名；补 direction 后无；与内置规则混跑互不影响 |
| TC-EX-05 | **保持合成**（无 schema 包 / hooks 语法坏 / 坏目录 open 不崩） |

**验证**：聚焦 tests/extensions + tests/shell；全量回归 305 绿（迁移不减断言强度——删除的合成锚若有独立语义价值则保留为次锚，评审盯"虚迁移"）。

### Task 3: snowel-extension skill 双落 + README 指针

**实现**：`extensions/SKILL.md` 按 R5 六节大纲展开成文（frontmatter 形态参照 `~/.agents/skills/` 现有 skill：name + description + 正文；正文示例直接引用真包内容——组名、字段、规则名、命令）；按 R4 复制到全局；根 README.md 一行指针。

**验收**（文档任务无测试，验收=一致性核对清单，报告里逐条打勾）：
- 大纲六节全落；addendum §3.3 五要点（目录结构/schema 规范/hooks API/挂载校验测试流程/发布方式）与 EX-①②、终审-2 口径全被 skill 覆盖
- skill 中每条命令、组名、字段名、规则名与真包/引擎实际行为一致（对照 Task 1 产物与 ext-pack ledger 裁决）
- 全局副本与源逐字节一致（diff 实证）；根 README 指针一行且指向正确

### 收尾（dev-workflow §7 全流程）

终审（全分支独立评审）→ 修复波 + 定向复审 → 合并 `dev-1.0.0`（合并结果主仓库全量重跑：pytest + vitest + `npm run build`；worktree 干活后先 editable 重装校正指向）→ 删 worktree/feat 分支 → ledger 归档 `plans/2026-08-28-infinite-flow/ledger.md`（EX-①② 随 skill 关闭登记）→ 更新 AGENTS.md 阶段指针（Step 3 完成 → 下一步 Step 4 壳端暴露；EX-③ 移交必查）→ 推送 dev。

## 7. 执行参数

| 项 | 值 |
|---|---|
| 模式 | Subagent-Driven（3 任务严格串行 T1→T2→T3；两席评审/任务；controller 不写码） |
| worktree | `D:\Code\snowel-infinite-flow`（兄弟目录，从 dev-1.0.0 切） |
| 分支 | `feat/infinite-flow` → merge --no-ff 回 `dev-1.0.0` |
| 测试基线 | 合并前 305/305 全绿为底（T1 +4 冒烟，T2 迁移后总量持平或微增）+ 74/74 + build 绿 |
| 修环上限 | 5 轮（R1-3 原实现者，R4-5 换强模型新派） |
| Step 4 接口 | EX-③ 警告池归因漂移 + per-instance 注册表决策（ext-pack ledger 挂账）为 Step 4 preflight 必读 |
