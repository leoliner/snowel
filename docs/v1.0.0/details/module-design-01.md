# Snowel 模块设计（第一版）

> 日期：2026-08-23
> 依据：docs/requirements-01.md（C1–C12）、docs/schema-design-01.md（D1–D8）。
> 范围：snowel-core 内部模块划分、三个 LLM 口接口、检查点/投影器、扩展包机制、级联检查引擎。外壳内部结构不在本文范围。

---

## 1. 本阶段裁决（E1–E5，2026-08-23 苏格拉底式澄清）

| # | 疑点 | 裁决 | 落点 |
|---|---|---|---|
| E1 | 核心模块划分 | **领域横向分层**：九模块单向依赖，api 是三端唯一门面；领域模块发起事务、storage 不自开事务；一次确认 = 单事务（事件+物化+索引） | §2 |
| E2 | 投影器归属 | **storage 内部子模块**：纯函数 fold，暴露 apply/rebuild；物化图唯一写入口 = 投影器，领域模块只能追加事件 | §3 |
| E3 | compose_context 编排 | **ai_generate 内部编排**：生成第一步固定内部 compose_context，审计自动全覆盖；compose_context 另以只读 dry_run 暴露；三端无法裸生成 | §4 |
| E4 | 扩展包机制 | **目录式发现**：自包含目录（schema.json 必选 + hooks.py 可选），项目 `extensions/` 与全局 `~/.snowel/extensions/` 双位置，同名项目内覆盖 | §5 |
| E5 | 级联检查 | **三类全跑 + 规则引擎**：每个变更集统一跑矛盾/依赖/叙事区间三类检查，"向前/向后"仅作裁剪优化；consistency 规则引擎 + 注册接口，核心自带通用规则，扩展包可注册领域规则，全量/轻量两档 | §6 |

派生小项（由既有裁决推导，未单独裁决）：core 组必填字段 = 核心硬编码 pydantic（D3 + 需求 4.1）；单写者租约 = storage 实现、api 暴露（C10）；retrieval_audit = storage 审计表、retrieval 写入（六.2）。

## 2. 模块划分（E1）

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

## 3. 投影器（E2）

- `storage/projector.py`：`fold(state, event) -> state` 纯函数（按 schema-design §3.2 的全部事件类型分派物化动作）；`apply(events, tx)` 增量应用；`rebuild()` 从日志全量重建。
- **纪律：物化图（nodes/edges/派生序/FTS/vec 索引）唯一写入口是投影器。** 领域模块改物化图的唯一方式 = 追加事件。代码评审以此为红线。
- 检查点水位线存库；rebuild 供 `snowel rebuild` 类命令与损坏恢复。

## 4. 三个 LLM 口（E3）

| 口 | 模块 | 签名要点 |
|---|---|---|
| `ai_generate(artifact_type, locate, extra=None) -> Proposal` | llm + retrieval | 内部第一步 compose_context（策略由 artifact_type 决定）；产出进 proposal 队列，永不直接落正典 |
| `extract_and_writeback(chapter_ref) -> WritebackResult` | llm + writeback | 输入正文镜像；输出按确认分级拆分：高敏感 → 提案，低敏感 → auto_canonized 事件（单事件批量，D1） |
| `rewrite_query(query, context) -> query'`（可选） | llm + retrieval | 检索改写；未启用时检索为纯确定性代码 |

- `compose_context(strategy, locate, dry_run=False) -> ContextBundle` 同时暴露为只读 API（Web 预览 / MCP 查询用）；dry_run 记审计但标注类型。
- 生成端提示词注入近期 proposal_rejected 摘要（D7）。

## 5. 扩展包（E4）

```
<pack_dir>/
  schema.json   # 必选：属性组名、版本、pydantic 等价的 JSON Schema、必填字段
  hooks.py      # 可选：def register(registry): ...（级联规则、护栏检查、生成提示词片段）
```

- 发现顺序：项目 `extensions/` → 全局 `~/.snowel/extensions/`，同名项目内覆盖；启动时注册进 ontology registry，已挂载数据的组不可卸载（校验拦截）。
- hooks 注册接口即 E5 的规则接口与提示词片段接口；文档标注"只装可信来源的包"。

## 6. 级联检查引擎（E5）

- 统一模型：每个变更集跑三类检查——①矛盾检测（变更后事实 vs 当前生效集）②依赖检测（引用反查）③叙事区间检测（有效期投影重叠/空洞）。"向前查矛盾/向后查依赖"仅是按变更类型裁剪检查子图的范围优化。
- 规则接口：`Rule(change_set, graph_query) -> [Violation(level, message, refs)]`；核心内置：集合一致性、边反查（IS_A/REQUIRES/EXPLOITS）、区间重叠、冻结线（含轨道棘轮 C7）、growth_curve 护栏（mechanism 组自带）。
- 四个写入点统一调用：提案确认（全量）、auto 入典（轻量）、retcon（全量）、retraction（轻量，C11）。
- 冲突产出 diff 式修订提案，不自动改（需求 5.5）。

## 7. 对外壳的约束汇总

- 三端只 import `snowel_core.api`；租约获取失败 → 外壳降级只读并提示。
- MCP 六工具、CLI 命令、Web 路由各自映射到 api 门面方法，一比一，无编排逻辑。

## 8. 与上游文档的对照

- 铁律 1/2/3/4/5（需求二）→ §2 划分、§4 三口、§7 门面与租约；
- D1 检查点 → §3；D3/D5 → §5/§2 ontology；D7 → §4；D8/C1 → §2 writeback；
- C12 对账偏离报告 → flow 模块职责（确定性比对，非 LLM 口）。

## 9. 留给实现计划阶段的问题

1. 各模块文件级骨架与测试切片顺序（writing-plans 拆解）；
2. api 门面的具体方法清单（从 MCP 六工具 + Web 交互反推）；
3. hooks.py 的进程内注册协议细节（错误隔离、包升级时钩子失效策略）。
