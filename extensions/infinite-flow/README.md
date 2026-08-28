# infinite-flow —— 无限流题材扩展包

Snowel 预制薄包：**四个属性组 + 一条示范级联规则**，既是无限流题材的开箱素材，
也是扩展包机制的示范与 TC-EX 测试锚（载荷上限裁决：包只含属性组与级联规则两类）。

## 目录结构

| 文件 | 内容 |
|---|---|
| `schema.json` | 包清单：name / version + 四属性组的 JSON Schema 片段 |
| `hooks.py` | `register(registry)` 注册示范规则（挂载时加载，卸载时随包撤销） |
| `README.md` | 本文件 |

## 四组字段速览

示例值取自示范小说主角**林晚**的档案（字段语义见各组说明）：

| 组名 | 字段 | 类型 | 约束 | 林晚示例 |
|---|---|---|---|---|
| `flow_space_seniority` 空间资历 | `entered_at` | string | required | `"首夜"` |
| | `cycles` | integer | optional | `17` |
| | `status` | string | enum `[active, escaped, lost, deceased]`，optional | `"active"` |
| `flow_rank_track` 排名轨迹 | `current_rank` | integer | required | `480000` |
| | `peak_rank` | integer | optional | `10000` |
| | `direction` | string | enum `[ascending, descending, volatile, held]`，optional | `"descending"` |
| `flow_abilities` 能力清单 | `abilities` | array of string | required | `["时滞"]` |
| | `source` | string | optional | `"排名入前 1 万副本奖励"` |
| `flow_blindspot` 盲区特权 | `description` | string | required + pattern `^.+` | `"已死过一次"` |
| | `exploited` | boolean | optional | `true` |

`direction` 刻意 optional：形状归 schema、语义归 hooks——写入 `flow_rank_track`
而缺 `direction`（或空值）会被示范规则 `flow_rank_track_direction_required`
报一条 major Violation（refs 含节点 id），不阻断落库。

## 数据示例：林晚档案 props

```json
{
  "flow_space_seniority": {"entered_at": "首夜", "cycles": 17, "status": "active"},
  "flow_rank_track": {"current_rank": 480000, "peak_rank": 10000, "direction": "descending"},
  "flow_abilities": {"abilities": ["时滞"], "source": "排名入前 1 万副本奖励"},
  "flow_blindspot": {"description": "已死过一次", "exploited": true}
}
```

## 挂载与卸载

在 Snowel 项目目录（含 `snowel.db` 的工作区）执行：

```bash
snowel ext list                  # 发现全集 × 挂载态（本包应显示为项目/全局侧未挂载）
snowel ext mount infinite-flow   # 挂载：四组即刻可写，hooks 规则同引擎生效
snowel ext status                # 健康明细（schema 不一致等异常在此呈现）
snowel ext unmount infinite-flow # 卸载：活跃节点仍引用组键时拒绝；卸后数据保留
```

**升级语义**：schema 升级不自动跟随——磁盘包与挂载时不一致（digest 变化）时
已挂载会话维持旧形状并标记不健康，须显式重新挂载（re-mount）后新 schema 才生效。

## 进一步阅读

扩展包机制全貌（目录双位置、schema 规范、hooks API、发布建议）见
[`extensions/SKILL.md`](../SKILL.md)（snowel-extension skill，唯一源）。
