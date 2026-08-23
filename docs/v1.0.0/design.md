# Snowel 设计文档（v1.0.0 定稿）

> 日期：2026-08-23
> 来源：docs/v1.0.0/details/schema-design-01.md（裁决 D1~D8）与 module-design-01.md（裁决 E1~E5）合并而成。
> 上游：requirements.md（含 C1~C12 裁决）；下游：实现计划（writing-plans）。

---

## 1. 设计裁决总表（D1~D8 + E1~E5）

| # | 疑点 | 裁决 |
|---|---|---|
| D1 | state_at(拍N) 推导语义 | **真重放 + fold 检查点**：日志是唯一真相源；state_at = fold 到末尾后按叙事时间投影；物化图 = 永不过期的检查点缓存；批量入典合并单事件控量 |
| D2 | 节点 ID 方案 | **UUID（v7）+ name 属性 + alias 表**；多类型叠加 = 单节点多类型标签 |
| D3 | 属性组存储与校验 | **注册式 schema + 命名空间 JSON 分组**（pydantic）；组版本落库，不匹配降级警告、迁移显式；未注册组标 `unmanaged` |
| D4 | 拍号编址 | **层级地址 + 派生序**：拍 ID = (chapter, scene, beat_index)；全局先后为派生序号，插入章节只重算派生序；轨内世界时间独立存放不参与编址 |
| D5 | completeness 判据 | **确认制**：profiled = core 齐备且经作者确认；active = 已确认正文中登场（图谱引用不算）；允许作者手动升降级并记事件 |
| D6 | MicroBeat 形态 | **独立节点**：自有 UUID，地址存 props；拍合并/删除走显式事件，伏笔引用不漂移，可被级联检查反查 |
| D7 | 提案否决 vs 作废 | **两态分离**：否决 = 创作决策，追加 proposal_rejected 事件（含可选原因）；作废 = 队列清理，轻量不构成决策；行永不删；生成端注入近期被否提案防重复 |
| D8 | 正文全文是否入库 | **库内全文镜像**：章节表存全文 + 哈希，FTS5/段落向量从镜像构建；文件仍是真相源，哈希不一致以文件为准重灌 |
| E1 | 核心模块划分 | **领域横向分层**：九模块单向依赖，api 是三端唯一门面；领域模块发起事务、storage 不自开事务；一次确认 = 单事务（事件+物化+索引） |
| E2 | 投影器归属 | **storage 内部子模块**：纯函数 fold，暴露 apply/rebuild；物化图唯一写入口 = 投影器，领域模块只能追加事件 |
| E3 | compose_context 编排 | **ai_generate 内部编排**：生成第一步固定内部 compose_context，审计自动全覆盖；compose_context 另以只读 dry_run 暴露；三端无法裸生成 |
| E4 | 扩展包机制 | **目录式发现**：自包含目录（schema.json 必选 + hooks.py 可选），项目 `extensions/` 与全局 `~/.snowel/extensions/` 双位置，同名项目内覆盖 |
| E5 | 级联检查 | **三类全跑 + 规则引擎**：每个变更集统一跑矛盾/依赖/叙事区间三类检查，"向前/向后"仅作裁剪优化；consistency 规则引擎 + 注册接口，核心自带通用规则，扩展包可注册领域规则，全量/轻量两档 |

## 2. 本体 Schema

### 2.1 节点（nodes 表）

```sql
nodes(
  id            TEXT PRIMARY KEY,      -- UUIDv7
  types         TEXT NOT NULL,         -- JSON 数组：["Character","Concept"]，多类型叠加=单节点多标签
  name          TEXT NOT NULL,
  completeness  TEXT NOT NULL DEFAULT 'draft',  -- draft → profiled → active
  props         TEXT NOT NULL,         -- JSON：{组名: {字段: 值}}，见 2.2
  created_event TEXT NOT NULL,         -- 创建它的日志序列号
  FOREIGN KEY (created_event) REFERENCES events(seq)
)
```

- **types 是标签集而非单值**：核心类型 Character / Concept / Relationship / Mechanism / Foreshadow / Scene / MicroBeat / Volume / Chapter / Track（Relationship、Foreshadow 均为节点）。
- **completeness 判据（D5 确认制）**：
  - `draft`：仅有名字或灵感原话；
  - `profiled`：core 组必填字段齐备**且经作者确认**（提案确认或手动编辑均算）；
  - `active`：profiled 且在已确认正文中登场（图谱引用不算登场）。
  - 状态默认从日志推导；允许作者手动升降级（记 completeness_override 事件）。
- **MicroBeat 为独立节点（D6）**：自有 UUID，拍地址 (chapter, scene, beat_index) 存 props；拍的合并/删除是显式事件（beat_merged/beat_deleted），伏笔引用不漂移。
- **alias 表**：`(node_id, alias, source)`；retcon 改名时旧名入 alias，FTS 索引覆盖 alias。

### 2.2 可插拔属性组

- `props` JSON 按命名空间分组：`core`（动机/谎言信念/恐惧/弧光，永远在场）、`mechanism`（规则原文/生效范围/漏洞/growth_curve/narrative_role）、各题材包（`wuxia`、`horror`…）。
- 每组注册一个 pydantic schema；写入时校验。组实例结构：`{"_schema": "mechanism@2", ...字段}`——组内嵌版本号。
- 扩展包 = schema 声明文件 + 可选检查钩子（如 growth_curve 指数警告）。后挂时对已有节点零影响。
- schema 版本不匹配：读取侧降级为警告不阻断；升级迁移是显式命令。
- 未注册组照存但标 `unmanaged`，不参与护栏与级联检查。
- core 组必填字段 = 核心硬编码 pydantic model 声明（core 组永远在场）；扩展组必填由各包 schema 自声明。

### 2.3 边（edges 表）

```sql
edges(
  id          TEXT PRIMARY KEY,      -- UUIDv7
  src         TEXT NOT NULL,
  dst         TEXT NOT NULL,
  kind        TEXT NOT NULL,         -- IS_A / REQUIRES / EXPLOITS / DERIVED_FROM / PARTICIPATES / ...
  props       TEXT NOT NULL DEFAULT '{}',
  valid_from  INTEGER,               -- 派生序（叙事生效起点），可空
  valid_until INTEGER,               -- 派生序（叙事失效点），可空
  created_event TEXT NOT NULL
)
```

- 边的强度曲线、起止拍（Relationship 节点需求）作为 Relationship 节点的 props 存，边表只保留结构关系。
- valid_from/until 是**物化派生列**（由检查点维护），真相在事件 payload 里。

### 2.4 拍与叙事顺序

- **拍的地址** = `(chapter_id, scene_id, beat_index)` 三段结构，稳定永不漂移；MicroBeat 即此地址的最细粒度。
- **派生序（story_order）**：物化的全局单调整数，= 按卷序/章序/场序/拍序的字典序编号。章改卷、插章只重算派生序，ID 与历史事件引用不动。重算由检查点增量完成。
- **世界内时间**：挂轨场景携带 `(track_id, duration, world_time_interval)`，由轨道定义的换算规则计算，仅服务于剧情逻辑查询，不参与 story_order。
- **层间换算（planted_at）**：伏笔定位存**最高可得精度**的结构化地址（beat / scene / chapter 区间）；派生序在检查点统一物化，层间换算 = 对地址求 story_order，自动传播。

### 2.5 轨道（tracks）

```sql
tracks(
  id           TEXT PRIMARY KEY,
  name         TEXT NOT NULL,
  definition   TEXT NOT NULL,   -- JSON：换算规则/流速/语义；首次被场景挂载后冻结（C7）
  frozen       INTEGER DEFAULT 0
)
```

- 轨道集合可增不可删改（C7）；单轨定义冻结由 `frozen` 位 + 级联检查执行。

## 3. 事件溯源层

### 3.1 事件表（唯一真相源）

```sql
events(
  seq        INTEGER PRIMARY KEY AUTOINCREMENT,  -- 日志序 = 生效顺序
  ts         TEXT NOT NULL,
  kind       TEXT NOT NULL,
  payload    TEXT NOT NULL     -- JSON
)
```

### 3.2 事件类型清单（v1）

| kind | 时机 | payload 要点 |
|---|---|---|
| `proposal_confirmed` | 提案确认 | 提案 id、产物类型、事实集（批量：N 条事实单事件，D1） |
| `auto_canonized` | auto 批量入典 | 事实集 + 抽取来源（章节哈希） |
| `retraction` | auto 条目否决（纠错，C11） | 目标事实、下游级联提示结果 |
| `retcon_applied` | 显式 retcon 确认 | 影响清单、旧→新版事实、关联正文提示 |
| `revision_applied` | 层间修订（卷改书/章改卷） | 结构变更、受影响派生序区间 |
| `prose_hash_registered` | 核心代写章节文件（C1） | 章节、哈希 |
| `prose_external_change` | hook 检测到未登记变更（C1） | 章节、旧/新哈希 |
| `volume_sealed` | 封卷 | 卷 id、封卷时 seq |
| `track_added` / `track_frozen` | 轨道生命周期（C7） | track id、definition |
| `stale_marked` | 上游变更标 stale（C5） | 提案 id、差异提示 |
| `proposal_rejected` | 作者否决提案（D7，创作决策） | 提案 id、可选否决原因 |
| `proposal_voided` | 手动作废（C5/D7，队列清理，不构成决策） | 提案 id |
| `completeness_override` | 作者手动升降级 completeness（D5） | 节点 id、旧→新状态、原因 |
| `beat_merged` / `beat_deleted` | 微节拍合并/删除（D6，显式事件） | 拍地址、受影响伏笔引用及迁移结果 |

### 3.3 重放与检查点（D1）

- **state_at(拍N)**：fold 日志到 HEAD → 得当前生效事实集（含叙事有效期）→ 过滤"在拍 N 生效"的条目。C9 修正后视角天然成立：retraction/retcon 是追加事件，fold 到 HEAD 即已生效。
- **物化图 = fold 检查点**：记录已应用到的 `seq` 水位线；新事件只增量应用。事件不可变，检查点永不过期，可随时从日志全量重建（`snowel rebuild` 类命令）。
- 事件 payload 中所有结构引用使用稳定 ID（节点 UUID、拍结构地址），不用派生序——派生序只出现在物化层。

### 3.4 提案表（pending 态，不入事件日志）

```sql
proposals(
  id         TEXT PRIMARY KEY,
  kind       TEXT NOT NULL,        -- 产物类型（premise/scene/正文/microbeat_group/...）
  payload    TEXT NOT NULL,        -- 提案内容 + diff
  status     TEXT NOT NULL,        -- pending / stale / confirmed / rejected / voided
  stale_hint TEXT,                 -- C5 差异提示
  created_ts TEXT NOT NULL
)
```

- 确认/否决不删行，状态迁移写入事件日志（§3.2）；生成端提示词注入近期被否决提案，防止重复提案（D7）。

## 4. 检索层映射

- **正文全文镜像（D8）**：章节镜像表存全文 + 哈希；FTS5 与段落向量均从镜像构建。Markdown 文件仍是真相源：启动/定期对账，哈希不一致时以文件为准重灌镜像。
- FTS5：节点 name/alias/props 扁平文本 + 章节镜像全文。
- sqlite-vec：正文段落与设定节点的嵌入向量；嵌入模型配置 per-project（C6），存项目配置表。
- **retrieval_audit**：storage 中的审计表，retrieval 模块在每次 compose_context（含 dry_run，标注类型）时写入。

## 5. snowel-core 模块划分（E1）

```
snowel_core/
  api/          # 对外壳的唯一门面：SnowelAPI 类，三端只许 import 这里
  flow/         # 雪花流程编排：L1-5、卷/章滚动展开、封卷触发、对账偏离报告（C12）
  proposal/     # 提案队列：生成入库、确认/否决（D7）/作废、stale 标记（C5）
  consistency/  # 规则引擎（E5）、retcon、state_at 重放投影查询、密封线
  retrieval/    # compose_context（含 dry_run）、retrieval_audit 写入
  writeback/    # 抽取管线、正文镜像与哈希对账（D8/C1）、hook 摄取
  ontology/     # 节点类型注册、属性组 schema 注册表（D3）、completeness 推导（D5）
  llm/          # litellm 适配；三个口唯一实现处（铁律 2）
  storage/      # SQLite 连接/事务、事件日志、projector（E2）、FTS、vec、租约（C10）
```

**依赖方向**：api → {flow, proposal, consistency, retrieval, writeback, ontology} → {llm, storage}；同层之间不互相 import（flow 编排 proposal/consistency 一律经 api 内部服务层或显式注入）。

**事务规则**：storage 只提供 `with core.transaction() as tx:` 上下文，领域模块在事务内调 storage 原子操作；投影器在同一事务内应用事件与刷新索引（D1 检查点的增量应用与事件追加原子绑定）。

**单写者租约（C10）**：storage 实现 `acquire_lease`/`renew`/`release` + 心跳时间戳，api 门面暴露给三端；外壳只调不实现；租约获取失败 → 外壳降级只读并提示。

## 6. 投影器（E2）

- `storage/projector.py`：`fold(state, event) -> state` 纯函数（按 §3.2 的全部事件类型分派物化动作）；`apply(events, tx)` 增量应用；`rebuild()` 从日志全量重建。
- **纪律：物化图（nodes/edges/派生序/FTS/vec 索引）唯一写入口是投影器。** 领域模块改物化图的唯一方式 = 追加事件。代码评审以此为红线。
- 检查点水位线存库；rebuild 供 `snowel rebuild` 类命令与损坏恢复。

## 7. 三个 LLM 口（E3）

| 口 | 模块 | 签名要点 |
|---|---|---|
| `ai_generate(artifact_type, locate, extra=None) -> Proposal` | llm + retrieval | 内部第一步 compose_context（策略由 artifact_type 决定）；产出进 proposal 队列，永不直接落正典 |
| `extract_and_writeback(chapter_ref) -> WritebackResult` | llm + writeback | 输入正文镜像；输出按确认分级拆分：高敏感 → 提案，低敏感 → auto_canonized 事件（单事件批量，D1） |
| `rewrite_query(query, context) -> query'`（可选） | llm + retrieval | 检索改写；未启用时检索为纯确定性代码 |

- `compose_context(strategy, locate, dry_run=False) -> ContextBundle` 同时暴露为只读 API（Web 预览 / MCP 查询用）；dry_run 记审计但标注类型。
- 生成端提示词注入近期 proposal_rejected 摘要（D7）。

## 8. 扩展包机制（E4）

```
<pack_dir>/
  schema.json   # 必选：属性组名、版本、JSON Schema、必填字段
  hooks.py      # 可选：def register(registry): ...（级联规则、护栏检查、生成提示词片段）
```

- 发现顺序：项目 `extensions/` → 全局 `~/.snowel/extensions/`，同名项目内覆盖；启动时注册进 ontology registry，已挂载数据的组不可卸载（校验拦截）。
- hooks 注册接口即级联规则接口与提示词片段接口；文档标注"只装可信来源的包"。

## 9. 级联检查引擎（E5）

- 统一模型：每个变更集跑三类检查——①矛盾检测（变更后事实 vs 当前生效集）②依赖检测（引用反查）③叙事区间检测（有效期投影重叠/空洞）。"向前查矛盾/向后查依赖"仅是按变更类型裁剪检查子图的范围优化。
- 规则接口：`Rule(change_set, graph_query) -> [Violation(level, message, refs)]`；核心内置：集合一致性、边反查（IS_A/REQUIRES/EXPLOITS）、区间重叠、冻结线（含轨道棘轮 C7）、growth_curve 护栏（mechanism 组自带）。
- 四个写入点统一调用：提案确认（全量）、auto 入典（轻量）、retcon（全量）、retraction（轻量，C11）。
- 冲突产出 diff 式修订提案，不自动改。

## 10. 对外壳的约束

- 三端只 import `snowel_core.api`；租约获取失败 → 外壳降级只读并提示。
- MCP 六工具、CLI 命令、Web 路由各自映射到 api 门面方法，一比一，无编排逻辑。

## 11. 与需求文档的对照

- 铁律 1~5（需求 2）→ §5 划分、§7 三口、§10 门面与租约；
- C1（哈希短路）→ §3.2 事件 / §5 writeback；C5（stale）→ §3.2/§3.4；C7（轨道棘轮）→ §2.5/§9；C8/C9（重放修正后视角）→ §3.3；C11（纠错 vs 改设）→ §9 轻量档；C12（对账偏离报告）→ flow 模块职责（确定性比对，非 LLM 口）；
- D1~D8 全部落位：D1→§3.3；D2→§2.1；D3→§2.2/§8；D4→§2.4；D5→§2.1；D6→§2.1/§3.2；D7→§3.2/§3.4/§7；D8→§4。

## 12. 留给实现计划阶段的问题

1. 各模块文件级骨架与测试切片顺序（writing-plans 拆解）；
2. api 门面的具体方法清单（从 MCP 六工具 + Web 交互反推）；
3. hooks.py 的进程内注册协议细节（错误隔离、包升级时钩子失效策略）。
