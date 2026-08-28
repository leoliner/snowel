## 检索与偏好

百万字的书，AI 每次动笔前都要"翻资料"：当前场景有谁、谁的旧账没结、相关设定原文是什么。本章讲这条检索管线怎么工作、哪些偏好可以调，以及一个重要的省钱开关。

### 混合检索：三路合流

检索（hybrid retrieval，混合检索）由三路结果合流：

| 路 | 靠什么 | 擅长 |
|---|---|---|
| 图谱精确拉取 | 知识图谱按场景卡、在场角色、未回收伏笔直接取 | 精确设定：名字、规则、生死状态 |
| 全文检索（FTS5） | 中文分词的关键词匹配 | 记得原文措辞时的定位 |
| 向量召回 | 语义相似度（本地嵌入模型） | 换个说法也能找到相关内容 |

所有需要"翻资料"的入口——写前上下文组装（compose_context）、生成与聊天时的查询、《聊天侧栏》里的检索工具——走的都是同一条管线；检索死亡角色时还会自动附上"已死亡@第 N 拍"，防止 AI 写活死人。

### 检索改写开关：`retrieval.rewrite`

`retrieval.rewrite` 控制检索前要不要先让 LLM 把检索词改写得更利于召回（展开别名、补同义词）。两条铁的事实：

- **默认开**。开着时每次检索都多一次 LLM 调用（改写词本身）；改写失败会自动回落原始检索词照常出结果，并在检索审计里记 `rewrite_failed` 标记——功能坏不掉，但会白付调用。
- **没有配置 LLM（无 key）的环境，建议关掉**。否则每一次检索都会先撞一次注定失败的改写调用：结果不受影响（回落兜底），但每次检索平白多一次失败调用与一条审计噪声。

关闭方法：改项目库里的 config 表（`snowel.db`）。停掉 Snowel 进程后，任选其一：

```bash
# 有 sqlite3 命令行工具时
sqlite3 snowel.db "INSERT INTO config(key, value) VALUES('retrieval.rewrite', 'false') ON CONFLICT(key) DO UPDATE SET value=excluded.value;"
```

```bash
# 只有 Python 时
python -c "import sqlite3; c = sqlite3.connect('snowel.db'); c.execute(\"INSERT INTO config(key, value) VALUES('retrieval.rewrite', 'false') ON CONFLICT(key) DO UPDATE SET value=excluded.value\"); c.commit()"
```

改完重新启动即生效（开关在每次检索时读取）。想重新打开，把值改回 `'true'`；删掉这行配置等效于默认开。

### config 表直改：当前的全部偏好

偏好统一存在项目库的 config 表，按需直改（同样停机后操作）：

| 键 | 默认 | 含义 |
|---|---|---|
| `retrieval.rewrite` | `true` | 检索改写开关（见上） |
| `retrieval.rewrite_model` | （空） | 指定改写专用模型；空则用默认模型 |
| `llm.backend` | `litellm` | LLM 接入方式 |
| `llm.model` | `gpt-4o-mini` | 默认生成模型（生成表单的 extra 里写 `{"model": "…"}` 可单次换；抽取换模型走 MCP 回写 trigger 的 `model` 参数） |

LLM 接入统一走 litellm：`llm.model` 填各家模型名，凭证按 litellm 惯例用环境变量提供（如 `OPENAI_API_KEY`）。

### 检索审计：AI 忘了什么，查得到

每次上下文组装了什么、检索词有没有被改写、改写是否失败，都记在检索审计（retrieval_audit）里。当你觉得"AI 写崩是因为忘了某事"，先查审计核对它当时看到了什么——是检索没召回（调关键词、看改写开关），还是召回了没用上（生成质量问题）。审计可经 MCP `snowel_advanced` 的 `audit` 操作查看。用真实失误数据调偏好，比凭感觉猜有效得多。
