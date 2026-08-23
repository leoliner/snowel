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
| `ontology/test_ontology.py` | `ontology/`（属性组注册表/completeness） | TC-ON-03/04/05（推导面） |
| `proposal/test_proposal.py` | `proposal/queue.py`（提案状态机） | TC-PR-01~07、TC-EV-07/08 |
| `api/test_api.py` | `api.py`（门面端到端） | 冒烟：init→create→confirm→query→rebuild |

## 2. 运行

```bash
pip install -e . pytest   # 首次
pytest                    # 全量
pytest tests/storage      # 单模块
```

## 3. 约定

- 新模块落地时在此建同名子目录，README §1 同步登记一行（含覆盖用例反向索引）。
- 模块间共享 fixture 写 `conftest.py`（目前为空占位）；跨目录共用的放根级。
- LLM 依赖的模块（llm/retrieval/writeback/flow，后续计划）测试一律注入确定性生成端，不发真实请求。
