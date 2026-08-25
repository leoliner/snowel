# 级联检查计划 · 归档 Ledger

> 计划：`docs/v1.0.0/plans/2026-08-25-cascade-check/plan.md`（11 任务，2026-08-25 用户批准全量）。
> 分支：`feat/cascade-check`（基于 dev-1.0.0 @ bd1db0e）→ 已合并 `207a378`（--no-ff）。
> 本文件由 live ledger（`.superpowers/sdd/plan/progress.md`，git-ignored）于收尾时归档而来；worktree 删除时 live 副本已销毁，内容经会话记录 + git log 重建，与执行期逐条对应。

## 1. 执行总览

| 项 | 值 |
|---|---|
| 执行模式 | Subagent-Driven（superpowers:subagent-driven-development），控制器 + 每任务实现者 + 两席评审（spec 合规 + 质量）+ scoped re-review |
| 执行期 | 2026-08-25，跨两个会话（T1–T6 于第一会话；T7–T11 + 收尾于第二会话经 handoff 续跑） |
| 测试基线 | 160/160（bd1db0e）→ 194/194（67e80ef，合并后主目录复验 194/194） |
| 任务 | T1–T11 全部 complete；修环 4 轮（T5×1、T6×1、T7×1、T8×1，全部 R1 闭环）；终审 1 波修复（Important 1 + 死分支清理）复审通过 |
| 交付 | consistency 六模块（engine/rules/wiring/seal/retcon/foreshadow）+ storage 扩展（deathbeat、queries L4、projector volume_sealed/retcon_applied、schema sealed_volumes）+ api 门面八件 + MCP/CLI 壳接线；挂账 L4/L13/L14 清偿 |
| 提交链 | bd1db0e → 0a35163(T1) → b3094ba(T2) → a6db6a4(T3) → 0d76e72(T4) → 36d184c(T5) → 2a74260(T6) → aa17bfd/5121001(T7+fix) → ef05bb3/3bb3357(T8+fix) → 1cba1ef(T9) → 5cf7349(T10) → cba7388(T11) → 67e80ef(终审修复) → 207a378(merge) |

### 1.1 会话交接（第一会话 → 第二会话）

T1–T6 完成后 live ledger 留 handoff.md 交接快照；第二会话经 editable 安装指向 worktree 的线索发现执行现场，验证基线 178/178 后自 T7 续跑。

## 2. Preflight（控制器双查）

### 2.1 挂账裁决（继承计划 §Preflight）

L4+L13 → Task 1；L14 → Task 8 顺带；L15/L16 不携带（已登记）。

### 2.2 任务间共享文件/接口冲突扫描（T1–T11）

| 对 | 产消关系 | 结论 |
|---|---|---|
| T1↔存量 | descendants 重写（接口扩展向后兼容）；deathbeat 助手替换 state_at/_alive/snowflake 三处 | 既有测试为守卫，顺序无冲突 |
| T6/T7/T8/T9↔api.py | 连续追加门面 + confirm/extract 接线 | 顺序执行，同函数不同位置，低冲突 |
| T7/T8↔projector.py | T7 加 volume_sealed handler + sealed_volumes 表；T8 扩展 retcon_applied 的 track_updates | 不同 handler，无冲突 |
| T8↔T7 | confirm_retcon 依赖"冻结线豁免"（T7 存在则豁免自然成立） | 依赖顺序 T7→T8 ✓ |
| T10↔T6 | confirm 响应 cascade 键消费 api.last_cascade（T6 产） | ✓ |
| T2↔T3-6 | engine.register 需覆盖式幂等 | Ruling E1 |
| T10↔存量 | ADVANCED_CATALOG 翻转；CLI seal 拆 not_wired | 测试翻转清单在计划 T10 节 |

## 3. Ruling 全录（决策—理由—若错的成本）

| # | 阶段 | Ruling | 若错的成本 |
|---|---|---|---|
| E1 | preflight | engine.register 同 name 后注册覆盖（幂等），T3-5 测试与 T6 wiring 统一注册互不污染 | 无（覆盖语义最简） |
| — | T2 | 计划缺陷：brief 测试 test_diff_proposal 跨库（api fixture 在 tmp_path/api、core_conn 在 tmp_path 根，字面实现不可能通过）→ 最小修正：测试内 SnowelAPI(core_conn) 构造，断言逐字保留。**教训：写计划凡 api+core_conn 混用的测试都要查库一致性** | 无 |
| — | T6 | 计划缺陷：projector 在确认事务内覆写 props，post-commit 一站式分析看不到旧值 → confirm 接线拆两段（事务前 wiring.analyze 只读分析 / 事务后 wiring.finalize 产 diff 提案） | 无 |
| — | T6 | 评审 Important×2：auto 写入点 contradiction 无条件死亡（同 props 覆写时序）→ extract 镜像两段式；retraction 轻量级联恒空（kind 门控跳过）→ dependents 加 retraction 分支 | 无 |
| — | T7 | 双席 Important：冻结线逃逸窗口（存盘于已封卷的节点借同笔变更改址迁出绕过拦截）→ `sealed_volume_of` 改**联合语义**：存盘归属卷或变更地址归属卷任一已封即拦。C7 意图=已封卷内容改动须走 retcon；投影器全组覆写 props，改址迁出即整笔改写 | 作者无法用普通确认搬内容出冻结卷（须走 retcon）——恰为 C7 严格读法 |
| — | T8 | spec ⚠️：P4 括号"renames 两端"→ 维持 **id 集合解读**（被改名节点的 node_id）；按 name 检索属语义级依赖图（计划豁免登记的后续优化） | payload 用名字引用被改名节点的提案不标 stale——作者可强行确认，语义安全 |
| — | T8 | 质量 Important：api.confirm 对 retcon kind → **抛 ValueError** 指引 confirm_retcon，不自动路由（分派职责归 T10 壳层经 proposal_kind） | 无 |
| — | T9 | 实现者提前写 tests/README §1 consistency 行（T11 职责）→ 保留，T11 核对内容（后经核对修正：+TC-WB-08、-TC-ON-14） | 无 |
| — | T10 | ⚠️1：revision 面 last_cascade 既有行为经控制器核实（confirm 尾部置 None）；⚠️2：MCP confirm 响应 cascade 键**恒在、无级联为 None**（schema 稳定） | 客户端需判键存在性——一行防御 |
| — | 终审 | 修复波范围 = Important 1（撤回复活逃逸）+ T8 ⑥ 死分支清理；其余 Minor 按 triage 挂账不扩 scope | 无 |

## 4. 任务完成记录（含 deferred minors）

- **T1** complete（bd1db0e..0a35163，review clean 一次过）— L4（descendants CTE 级 kinds+时效谓词，两臂生效）+ L13（deathbeat 助手三站点替换）。minor：①is_dead 回退分支二次 json.loads；②descendants docstring 未提 kinds=[] 恒空边界；③snowflake 传 is_dead 的行隐式列耦合。
- **T2** complete（0a35163..b3094ba，review clean）— 前一实现者超时零落盘已重派。minor：②引擎去重未严格断言（③模块级注册残留——E1 覆盖接受；①E1 探针测试由 T6 补齐关闭）。
- **T3** complete（b3094ba..a6db6a4，review clean）— minor：③同节点多键矛盾被 (rule,refs) 去重折叠、diff 提案只留首键（挂账 L19；①注册休眠经 T6 wiring 关闭）。
- **T4** complete（a6db6a4..0d76e72，review clean）— 首派模型错误中断，二次实现者校验 brief 后保留。fts 检索名取 fact 名 ∪ 物化行名。minor：①peer_names 顺序未锚定；②edges dict 可换 set；③fts.search limit=20 长篇截断（挂账 L17）；④get_node 无 active 过滤（挂账 L17）。
- **T5** complete（0d76e72..36d184c，fix round 1 后 clean）— 微裁决 3 处（自跳/哨兵排除、拍地址 props 优先、definition JSON 语义比较）。minor：①track 变更缺 definition 键对冻结轨误报（T8 契约恒带）；②两微裁决路径无回归锚点（挂账 L18）。
- **T6** complete（36d184c..2a74260，fix round 1 后 clean）— 两段式 + retraction 分支（见 Ruling）；E1 覆盖探针补齐；注册休眠关闭。minor：①preview 的 conflicts 拼装内联重复两行；②_last_cascade 异常路径残留上轮值；③retraction→edge 两端反查无独立回归锚点（挂账 L18）。
- **T7** complete（2a74260..5121001，fix round 1 后 clean）— 封卷/冻结线/拦截/豁免 + 联合语义 Ruling + extract 拦截锚定测试。minor：①extract 拦截命中时悬挂 high pending（惰性，confirm 再拦）；②pytest.raises(Exception) 基类过宽（brief 自带写法）；③api.sealed_volumes 门面无提交内测试、类型标注 list vs list[dict]；④_volume_node_id 全表扫描；⑤停用 Volume 节点致卷映射失联（终审 triage：accept，无停用 Volume 用户流程——**注意内容节点撤回复活逃逸不在此列，由终审 Important 1 堵漏**）。
- **T8** complete（5121001..3bb3357，fix round 1 后 clean）— propose_retcon（P5）+ confirm_retcon（E1 单事务双事件）+ affected_pending（P4）+ mark_stale_batch（L14）+ track_updates 物化（P3）+ revision 面切精确 stale（既有测试按 P4 最小重写）。minor：①mark_stale_batch 绕过状态机 _ALLOWED 校验（调用点均经 pending 过滤）；②frozen==1 未断言；③空 retcon 无守卫（挂账 L18）；④P4 包含匹配对引号/反斜杠 id 假阴性、短 id 假阳性（v1 规格内）；⑤status!=pending 守卫为 brief 外新增（无害）；⑥api.py retcon 豁免分支死代码（终审修复波清理）。
- **T9** complete（3bb3357..1cba1ef，review clean 一次过）— 伏笔门面 + 校验 + README 行（Ruling 保留）。minor：①校验失败无"未创建提案"断言；②Scene/Chapter 锚点与错型拒绝、payoff_beat/note 物化未断言（挂账 L18）；③校验错误消息不分不存在/停用/错型。
- **T10** complete（1cba1ef..5cf7349，review clean 一次过）— proposal_kind 门面 + writeback 三 action + CATALOG 翻转 + confirm 分派与 cascade 键 + CLI seal。judgment call（propose_retcon 同步 _last_cascade）经 spec 席验证为 P5 下唯一连贯读数。minor：①MCP confirm 分派 retcon 分支无协议层测试（挂账 L18）；②api.py:23/201 docstring 未提 retcon-propose 写路径；③propose 与 confirm 间无关 confirm 覆盖 _last_cascade（单槽缓存窗口，挂账 L19）；④空 retcon 产出空提案；⑤缺参 KeyError 裸文案（沿文件约定）；⑥壳重编码门面默认值；⑦foreshadow 分支多透传 payoff_beat?（超规格纯透传）。
- **T11** complete（5cf7349..cba7388）— README 行核对修正（+TC-WB-08、-TC-ON-14，计划规格逐字对齐）；全量 192/192。

## 5. 终审（全分支 bd1db0e..cba7388）与修复波

- **终审结论**：With fixes——P1–P5 全部按裁决落地；E1 两段式（confirm/extract 双写入点）无漂移；E2/铁律 1 保持；L4/L13/L14 可验证；rebuild 完备（sealed_volumes 清表 + 双 handler 重放）；向后兼容（CREATE TABLE IF NOT EXISTS + open 即 migrate）；覆盖矩阵全有锚；零 LLM。
- **Important 1（撤回复活逃逸）**：已封卷内节点被 C11 撤回（active=0、props 保留）后，无地址 low 事实因 `volume_id_of` 的 `AND active=1` 查不到存盘归属卷 → 不拦 → projector ON CONFLICT 复活覆写正典。撤回是既有用户流程，逃逸实际可达。
- **修复波**（cba7388..67e80ef，`fix(consistency): close retract-revival freeze-line escape, clean dead retcon branch`）：`volume_id_of` 去 active=1（撤回行即前 canon）；confirm/extract 两路"撤回→无地址重确认被拦"回归测试（RED→GREEN）；api.confirm 死分支清理 `("revision","retcon")`→`("revision",)`。定向复审：两项 ADDRESSED、无新破坏（影响面全量排查：C11 豁免不受影响、无新误拦路径、数字陷阱规避核实）。
- **终审 Minor（挂账/接受）**：②dependents 反查含已撤回边（→L17）；③at_story_order 未透传 api 门面（计划只要求 queries 级，accept）；④finalize 事后异常假失败（概率极低，accept）；⑤TC-CC-04 接线层锚（→L18）。
- **终审 Recommendations**：①存盘口径读取一律不设 active 过滤（已随修复波落地于 volume_id_of）；②反查族统一（→L17）；③engine.run 按变更归因供多键冲突（→L19）；④MCP confirm 从 payload 读 impact 替代单槽缓存（→L19）。

## 6. 挂账表（跨计划 L 系列）

| # | 挂账 | 状态 | 承接 |
|---|---|---|---|
| L4 | descendants 无边时效过滤、kinds 未消费 | **关闭**（T1） | — |
| L13 | dead 单扫与 state_at 口径分叉、死亡判定三处重复 | **关闭**（T1 deathbeat 统一） | — |
| L14 | C5 stale 循环事务外标记 | **关闭**（T8 mark_stale_batch 单事务） | — |
| L15 | 零事实章 appeared 丢失（接受边维持） | 开放 | 与级联无交集，随 Web 计划处置 |
| L16 | Windows python.org 构建扩展加载 + core/壳同步发包 | 开放 | v1.0.0 发版前发布债 |
| **L17**（新） | inactive 实体反查口径统一：edges_of 无 active/valid_until 过滤、get_node 无 active 过滤（旧名参与反查）、fts limit=20 长篇截断、snowflake is_dead 行隐式列耦合、dependents 提示面含已撤回边——一次性统一 edges_of/get_node/fts 语义并落 docstring | 开放 | 下一计划 preflight（Web 三栏或补丁） |
| **L18**（新） | 测试锚与守卫补强包：撤回边/顶层拍地址两微裁决无锚、retraction→edge 反查无锚、空 retcon 无守卫、伏笔 Scene/Chapter 锚点与物化断言、MCP confirm retcon 分派协议层测试、TC-CC-04 三类统一跑接线层锚 | 开放 | 下一计划 preflight |
| **L19**（新） | Web 面板伴生项：同节点多键矛盾被去重折叠（diff 提案只留首键，面板呈现需展开）、_last_cascade 单槽缓存窗口（改从提案 payload/retcon_applied 事件读 impact） | 开放 | Web 三栏界面计划 |

## 7. 验收

- 全量 194/194（基线 160 + 本计划新增 34），主目录合并后复验 194/194。
- 覆盖矩阵（计划 §覆盖矩阵）TC-CC-01~08、TC-WB-08 后半、TC-ON-10 后半、TC-ON-16、TC-PR-02 retcon 面全部有测试锚；`tests/README.md` §1 已登记反向索引。
- 豁免登记（计划原文）：区间空洞检测（v1 只做重叠）；P4 字符串交集保守超集（语义依赖图后续）；E4 扩展包注册接口预留；P5 确认后不重跑（stale 补偿）；setting_gap/mechanism_detail 归 Web 计划。
