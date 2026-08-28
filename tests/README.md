# snowel-core 测试目录

> 目录结构镜像 `src/snowel_core/` 模块划分（design §5 E1）：一个核心模块一个子目录。
> 黑盒用例（`docs/v1.0.0/testcases.md`，TC-XX-NN）是验收基准；本目录是其实码落点，下表"覆盖用例"列可反向索引。

## 1. 目录结构

| 测试目录 | 被测模块 | 覆盖黑盒用例 |
|---|---|---|
| `storage/test_db.py` | `storage/db.py`（建库/迁移/事务） | TC-EV-08（事务语义基础） |
| `storage/test_events.py` | `storage/events.py`（事件日志） | TC-EV-06（append-only） |
| `storage/test_projector.py` | `storage/projector.py`（投影器/story_order/rebuild） | TC-EV-01/02/05、TC-ON-02/07/09/10、C2 边撤回回归 |
| `storage/test_queries.py` | `storage/queries.py`（state_at/图查询） | TC-EV-03/04、TC-ON-01/02 |
| `storage/test_lease.py` | `storage/lease.py`（单写者租约） | TC-SH-04/05（核心层） |
| `storage/test_vec.py` | `storage/vec.py`（sqlite-vec 扩展/嵌入 provider） | TC-RT-06（provider 切换/按项目重建）、L8 原子重建回归 |
| `ontology/test_ontology.py` | `ontology/`（属性组注册表/completeness） | TC-ON-03/04/05（推导面） |
| `proposal/test_proposal.py` | `proposal/queue.py`（提案状态机） | TC-PR-01~07、TC-EV-07/08 |
| `api/test_api.py` | `api.py`（门面端到端） | 冒烟：init→create→confirm→query→rebuild |
| `consistency/`（test_engine / test_rules_* / test_seal / test_wiring / test_deathbeat / test_retcon / test_foreshadow） | `consistency/`（级联引擎/封卷/retcon/伏笔注册） | TC-CC-01~08、TC-WB-08、TC-ON-10 后半、TC-ON-16、TC-ON-17、TC-PR-02 retcon 面 |
| `extensions/`（test_discovery / test_mounting / test_hooks / test_infinite_flow_pack） | `extensions/`（扩展包发现与 manifest 解析/挂卸载事件闭环+启动重载/hooks 隔离加载，规则进一致性引擎/真包冒烟——`extensions/infinite-flow` 即 TC-EX 素材源） | TC-EX-01（项目优先同名覆盖）、02（中途挂载零影响）、03（卸载引用校验拦截）、04（hooks 与核心规则同引擎）、05（schema 缺失跳过/hooks 错误隔离）；CLI `ext` 出口面锚在 `shell/test_cli.py` |
| `shell/`（test_project / test_mcp_server / test_cli / test_lease_integration / test_web_server） | 壳包 `snowel`（project.py/cli.py/mcp_server.py/web_server.py） | TC-SH-01/02/04/05/06、TC-SH-03 子集、TC-SH-07（status/backup/export）、TC-SH-08 面 + TC-SH-09/10 端点契约（test_web_server：租约/写守卫/写 API/聊天约束/端到端/灵感与拍操作端点/derive_from 透传）、TC-SH-11（test_mcp_server：advanced 四新 op 目录/写操作租约）、L25 open_project 接线补锚 |
| `llm/`（test_backend / test_embed / test_chat） | `llm/`（backend 协议/litellm 适配、embed provider 接口、聊天代理 JSON 指令循环） | TC-RT-05（小模型路由面）、W1 聊天代理（§7.1） |
| `web/`（vitest：App / sse / components/*.test.tsx） | Web 前端（React 三栏界面；vitest + @testing-library/react，vi.mock 数据层不发真实请求） | TC-SH-08 组件锚（浏览器级 E2E 豁免 W3）、TC-SH-09 组件锚（InspirationPanel / GenerateForm derive_from / App 挂载）、TC-SH-10 组件锚（ProseEditor 拍侧栏合并/删除/拒绝红条） |
| `retrieval/test_context.py` | `retrieval/`（compose_context/审计/hybrid） | TC-RT-01/02/03、TC-ON-02（FTS 面） |
| `writeback/`（test_mirror / test_confirm_prose / test_extract / test_hook / test_active_and_deviation / test_review） | `writeback/`（镜像对账/确认即写/抽取分级/hook/active+偏离/auto 否决） | TC-WB-01~08、TC-PR-10、TC-ON-05/06、TC-FL-05 |
| `flow/`（test_generate / test_snowflake / test_state / test_revision / test_volume / test_inspiration） | `flow/`（生成环路由/小雪花展开/流程状态/统一 revision/卷级重放/灵感层） | TC-FL-01~04/06、TC-PR-02/08/09、TC-RT-04、TC-ON-12、ON-14 补锚、L25 恢复补锚 |

## 2. 运行

```bash
pip install -e . pytest   # 首次
pip install -e . -e ./shell
pytest                    # 全量
pytest tests/storage      # 单模块
```

## 3. 约定

- 新模块落地时在此建同名子目录，README §1 同步登记一行（含覆盖用例反向索引）。
- 模块间共享 fixture 写 `conftest.py`（目前提供 `core_conn`/`api` 真库 fixture 与 `FakeBackend` 确定性生成端）；跨目录共用的放根级。
- LLM 依赖的模块（llm/retrieval/writeback/flow）测试一律注入确定性生成端（`FakeBackend`/`DeterministicEmbed`），不发真实请求。
