# Snowel 本体 Schema 与事件溯源设计（第一版）

> 日期：2026-08-23
> 依据：docs/requirements-01.md（含 C1~C12 裁决）。
> 上游：需求定稿；下游：模块设计 → 实现计划（writing-plans）。
> 本文只覆盖本体 schema、事件溯源层与存储结构；模块划分是下一份文档。

---

## 1. 本阶段裁决（D1~D8，2026-08-23 苏格拉底式澄清）

| # | 疑点 | 裁决 | 落点 |
|---|---|---|---|
| D1 | state_at(拍N) 推导语义 | **真重放 + fold 检查点**：日志是唯一真相源；state_at = fold 到末尾后按叙事时间投影；物化图 = 永不过期的检查点缓存；批量入典合并单事件控量 | §3 / §4 |
| D2 | 节点 ID 方案 | **UUID（v7）+ name 属性 + alias 表**；多类型叠加 = 单节点多类型标签 | §2.1 |
| D3 | 属性组存储与校验 | **注册式 schema + 命名空间 JSON 分组**（pydantic）；组版本落库，不匹配降级警告、迁移显式；未注册组标 `unmanaged` | §2.2 |
| D4 | 拍号编址 | **层级地址 + 派生序**：拍 ID = (chapter, scene, beat_index)；全局先后为派生序号，插入章节只重算派生序；轨内世界时间独立存放不参与编址 | §2.4 |
| D5 | completeness 判据 | **确认制**：profiled = core 齐备且经作者确认；active = 已确认正文中登场（图谱引用不算）；允许作者手动升降级并记事件 | §2.1 |
| D6 | MicroBeat 形态 | **独立节点**：自有 UUID，地址存 props；拍合并/删除走显式事件，伏笔引用不漂移，可被级联检查反查 | §2.1 / §2.4 |
| D7 | 提案否决 vs 作废 | **两态分离**：否决 = 创作决策，追加 proposal_rejected 事件（含可选原因）；作废 = 队列清理，轻量不构成决策；行永不删；生成端注入近期被否提案防重复 | §3.2 / §3.4 |
| D8 | 正文全文是否入库 | **库内全文镜像**：章节表存全文 + 哈希，FTS5/段落向量从镜像构建；文件仍是真相源，哈希不一致以文件为准重灌 | §4 |

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

- **types 是标签集而非单值**：核心类型 Character / Concept / Relationship / Mechanism / Foreshadow / Scene / MicroBeat / Volume / Chapter / Track（Relationship、Foreshadow 均为节点，需求四.4 / 四.8）。
- **completeness 判据（D5 确认制）**：
  - `draft`：仅有名字或灵感原话；
  - `profiled`：core 组必填字段齐备**且经作者确认**（提案确认或手动编辑均算）；
  - `active`：profiled 且在已确认正文中登场（图谱引用不算登场）。
  - 状态默认从日志推导；允许作者手动升降级（记事件）。
- **MicroBeat 为独立节点（D6）**：自有 UUID，拍地址 (chapter, scene, beat_index) 存 props；拍的合并/删除是显式事件，伏笔引用不漂移。
- **alias 表**：`(node_id, alias, source)`；retcon 改名时旧名入 alias，FTS 索引覆盖 alias。

### 2.2 可插拔属性组

- `props` JSON 按命名空间分组：`core`（动机/谎言信念/恐惧/弧光，永远在场）、`mechanism`（规则原文/生效范围/漏洞/growth_curve/narrative_role）、各题材包（`wuxia`、`horror`…）。
- 每组注册一个 pydantic schema；写入时校验。组实例结构：`{"_schema": "mechanism@2", ...字段}`——组内嵌版本号。
- 扩展包 = schema 声明文件 + 可选检查钩子（如 growth_curve 指数警告）。后挂时对已有节点零影响。
- schema 版本不匹配：读取侧降级为警告不阻断；升级迁移是显式命令。
- 未注册组照存但标 `unmanaged`，不参与护栏与级联检查。

### 2.3 边（edges 表）

```sql
edges(
  id          TEXT PRIMARY KEY,      -- UUIDv7
  src         TEXT NOT NULL,         -- 节点 id
  dst         TEXT NOT NULL,
  kind        TEXT NOT NULL,         -- IS_A / REQUIRES / EXPLOITS / DERIVED_FROM / PARTICIPATES / ...
  props       TEXT NOT NULL DEFAULT '{}',
  valid_from  INTEGER,               -- 派生序（叙事生效起点），可空
  valid_until INTEGER,               -- 派生序（叙事失效点，如关系终止），可空
  created_event TEXT NOT NULL
)
```

- 边的强度曲线、起止拍（Relationship 节点需求）作为 Relationship 节点的 props 存，边表只保留结构关系。
- valid_from/until 是**物化派生列**（由检查点维护），真相在事件 payload 里。

### 2.4 拍与叙事顺序

- **拍的地址** = `(chapter_id, scene_id, beat_index)` 三段结构，稳定永不漂移；MicroBeat 即此地址的最细粒度。
- **派生序（story_order）**：物化的全局单调整数，= 按卷序/章序/场序/拍序的字典序编号。章改卷、插章只重算派生序，ID 与历史事件引用不动。重算由检查点增量完成。
- **世界内时间**：挂轨场景携带 `(track_id, duration, world_time_interval)`，由轨道定义的换算规则计算，仅服务于剧情逻辑查询，不参与 story_order。
- **层间换算（planted_at，需求四.8）**：伏笔定位存**最高可得精度**的结构化地址（beat / scene / chapter 区间）；派生序在检查点统一物化，层间换算 = 对地址求 story_order，自动传播。

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

## 5. 与需求的对照检查

- C8/C9（重放修正后视角）→ §3.3 D1 路径，字面矛盾由"fold 到 HEAD 再投影"消解；
- C1（哈希短路）→ §3.2 `prose_hash_registered`；
- C5（stale 无 TTL）→ §3.2 `stale_marked` + §3.4；
- C7（轨道棘轮）→ §2.5；
- 四.7（灵感原话永久保留）→ Layer 1 附属节点（types 含 Concept，DERIVED_FROM 边），正文级原文存 props。

## 6. 留给模块设计阶段的问题

1. snowel-core 内部模块划分与三个 LLM 口的接口签名；
2. 检查点增量应用的模块归属（存储层自带 vs 独立投影器）；
3. 题材扩展包的加载机制与钩子注册接口；
4. completeness 判据中"必填字段齐备"由 core schema 声明的方式。

---

## 追溯：本阶段裁决 → 章节表

见 §1（D1→§3/§4；D2→§2.1；D3→§2.2；D4→§2.4）。
