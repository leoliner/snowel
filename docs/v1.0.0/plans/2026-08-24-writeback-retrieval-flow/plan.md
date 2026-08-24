# 回写环 + 混合检索 + 生成环 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 落地需求 §9 落地顺序第 3 步全量：正文镜像与回写环（D8/C1）、FTS5+sqlite-vec 混合检索与 compose_context（E3/§6）、llm 三口基座与生成环（flow 雪花编排），并修复挂账 L1/L2/L5，接线 MCP/CLI 壳全部 not_wired 面。

**Architecture:** 全部领域逻辑进 snowel-core 四个新模块（writeback/retrieval/llm/flow），storage 扩镜像表、FTS/vec 虚表、审计表、配置表；投影器仍是物化唯一写入口，镜像全文不进事件（文件为真相源，对账重灌）；LLM 经 GenerationBackend/EmbeddingProvider 协议注入，测试用确定性实现不发真实请求；壳只做一比一映射。

**Tech Stack:** Python 3.12+ / SQLite（FTS5 + jieba Python 侧预分词、sqlite-vec）/ litellm（extras 可选 fastembed 真嵌入）

**Spec:** `docs/v1.0.0/requirements.md`（C1–C12）、`docs/v1.0.0/design.md`（D1–D8 + E1–E5）、`docs/v1.0.0/testcases.md`（黑盒验收基准）

## Global Constraints

- Python ≥3.12；core 纯 Python；三端只 import `snowel_core.api`（铁律 1）；壳零领域逻辑。
- LLM 调用只存在于三个口：`ai_generate` / `extract_and_writeback` / `rewrite_query`（铁律 2，rewrite_query v1 豁免返回 None）。
- 物化图（nodes/edges/派生序/FTS/vec/镜像）唯一写入口 = 投影器（E2 红线）；领域模块只追加事件。
- 一次确认 = 单事务（事件 + 物化 + 索引，E1）。
- 事件 payload 的结构引用只用稳定 ID（节点 UUID、拍结构地址），不用派生序（design §3.3）。
- LLM/嵌入依赖一律注入确定性生成端，测试不发真实请求（tests/README §3）；真嵌入模型 = extras `snowel-core[embed]`（fastembed）。
- 新依赖进 core `pyproject.toml`：`litellm`、`jieba`、`sqlite-vec`；`fastembed` 仅入 `[project.optional-dependencies] embed`。
- conventional commits；每任务一提交；新模块建 `tests/<module>/` 同名子目录并在 `tests/README.md` §1 登记一行（含黑盒用例反向索引）。
- 沿用现有代码风格：sqlite3.Row、`dict` 返回、中文 docstring、文件首行 `# src/...` 路径注释。

## Preflight 挂账裁决（同版本已归档 ledger）

| # | 挂账 | 裁决 | 落点 |
|---|---|---|---|
| L1 | `groups.validate` 畸形 `_schema` 版本串抛 ValueError | **携带，本计划修复** | Task 1（修复）+ Task 8（接入典写入路径） |
| L2 | `completeness.derive(props)` 无测试、文档签名漂移 | **携带：以实现为准 `derive(props)`，先补测试；active 判定接线** | Task 1（测试）+ Task 11（active） |
| L4 | `descendants` 无边时效过滤、kinds 未消费 | **不携带**——级联检查计划承接（继承未变） | — |
| L5 | 心跳失租后 `ctx.readonly` 不翻转（双写窗口） | **携带，本计划修复** | Task 1 |
| L3 | api.open() 校验 | 已由壳计划修复关闭 | — |

随行小项顺带（不强制，评审核验机会）：MCP `snowel_status` 的 lease_holder 只报自己（Task 18 顺带 core 只读门面 `current_lease_holder()`）；`graph_stats` 生效图分列（Task 13 顺带 active 过滤计数）。

## 计划级设计裁决（预登记 Ruling，执行期可依证修订）

| # | 裁决 | 理由 | 若错的成本 |
|---|---|---|---|
| P1 | **镜像全文不进事件日志**：`prose_hash_registered`/`prose_external_change` 只存章节 id、路径、哈希；镜像全文由 writeback 层在对账/登记时从文件读入 `chapter_prose.prose` 列 | D8 文件是真相源；日志体积不随正文膨胀；投影器不加 IO | rebuild 后镜像空表，需一次对账重灌（启动对账天然覆盖，CLI/MCP 均已挂） |
| P2 | **FTS 在投影器事务内全量重灌，vec 显式重建**：FTS（含 jieba 预分词）便宜，apply 尾部重灌；嵌入计算贵，`rebuild_embeddings()` 显式命令（对账/切换模型/抽取后调用），apply 不自动刷新 | 300 章级 nodes 表毫秒级重灌可接受；真嵌入全量重算不可接受 | vec 与 nodes 短暂不一致——兜底召回语义可容忍，检索审计可查 |
| P3 | **FTS 分词 = Python 侧 jieba 预分词**：写入前 `jieba.cut_for_search` 切词存空格分隔 token 串（unicode61 分词器），查询侧同样切词后拼 FTS5 前缀/短语表达式 | Python sqlite3 无法注册自定义 tokenizer；老大裁决采用 jieba | 同义改写查询不命中——兜底向量召回承担 |
| P4 | **hook = 轮询对账**（老大裁决）：自动模式 = 短周期轮询 reconcile；定时 = 长周期；手动 = 不轮询仅显式触发。三种模式共用同一 reconcile 代码路径 | 与启动对账（D8/TC-WB-05）一套代码；无 watchdog 依赖 | 改动检测有秒级延迟 |
| P5 | **章节文件路径约定** `chapters/<chapter_id>.md`（相对项目根），创建章节节点时写入 `props.file` | 单一约定，镜像/导出/对账共用 | 作者重命名文件 → 对账以路径扫描不到，视为删除侧警告（不删库） |
| P6 | **偏离报告判据（C12 确定性比对）**：微节拍完成度 = 节点 `props.keywords`（生成时标注）全部关键词在正文出现；场景卡要素 = `props.required_elements` 同法 | 全确定性、零 LLM；判据写死可测 | 语义等价但换词的节拍被判未完成——报告是提示不阻断，可接受 |
| P7 | **active 判定**：抽取产物 `appeared`（登场实体 id 列表）随事实入典事件 payload；投影器仅对 completeness=='profiled' 的登场节点置 active（draft 不可跳级） | D5 确认制链式；登场信息只有抽取知道 | 图谱引用被误当登场——prompt 判据明确"仅正文名词出场" |

## 文件结构总表

| 文件 | 动作 | 职责 |
|---|---|---|
| `src/snowel_core/storage/schema.sql` | 修改 | +`chapter_prose`/`retrieval_audit`/`config` 表，+`node_fts`/`prose_fts`（fts5）、`node_vec`/`prose_vec`（vec0）虚表 |
| `src/snowel_core/storage/config.py` | 新建 | 项目配置 KV（C6 嵌入配置、hook 模式、llm 模型） |
| `src/snowel_core/storage/fts.py` | 新建 | jieba 预分词、FTS 索引重灌、fts_search |
| `src/snowel_core/storage/vec.py` | 新建 | sqlite-vec 加载、嵌入写读、rebuild_embeddings、vec_search |
| `src/snowel_core/storage/projector.py` | 修改 | +prose 两事件/appeared 物化 handler；apply 尾部 FTS 重灌；rebuild 清单扩展 |
| `src/snowel_core/llm/backend.py` | 新建 | GenerationBackend 协议 + LitellmBackend |
| `src/snowel_core/llm/embed.py` | 新建 | EmbeddingProvider 协议 + DeterministicEmbed + fastembed 工厂（extras） |
| `src/snowel_core/llm/ports.py` | 新建 | 三口签名：ai_generate / extract_and_writeback / rewrite_query（桩） |
| `src/snowel_core/retrieval/context.py` | 新建 | compose_context（策略表、dry_run、死亡过滤、TODO 排除） |
| `src/snowel_core/retrieval/audit.py` | 新建 | retrieval_audit 写入/查询 |
| `src/snowel_core/retrieval/hybrid.py` | 新建 | search()：FTS+vec 混合召回 |
| `src/snowel_core/writeback/mirror.py` | 新建 | write_prose / reconcile（D8 对账） |
| `src/snowel_core/writeback/hook.py` | 新建 | HookScheduler 三模式轮询 |
| `src/snowel_core/writeback/extract.py` | 新建 | extract_and_writeback 分级管线 |
| `src/snowel_core/writeback/review.py` | 新建 | auto 条目枚举/批量否决 + 轻量反查 |
| `src/snowel_core/writeback/deviation.py` | 新建 | 偏离报告（C12） |
| `src/snowel_core/flow/registry.py` | 新建 | 产物类型注册表（层/策略/模板） |
| `src/snowel_core/flow/state.py` | 新建 | flow_state 进度与卷章结构 |
| `src/snowel_core/flow/generate.py` | 新建 | ai_generate 编排（E3 内部 compose、D7 注入） |
| `src/snowel_core/flow/snowflake.py` | 新建 | 小雪花章级 / 中雪花卷级展开编排 |
| `src/snowel_core/flow/revision.py` | 新建 | 统一 revision 流程 + 提案改写 |
| `src/snowel_core/proposal/queue.py` | 修改 | confirm(pid, exclude=None)（TC-PR-09 剔除）；get() 公开 |
| `src/snowel_core/ontology/groups.py` | 修改 | L1 畸形版本串降级 |
| `src/snowel_core/ontology/completeness.py` | 修改 | 仅补 docstring 签名说明（实现不变） |
| `src/snowel_core/api.py` | 修改 | +新门面方法（各任务逐个登记）；open/init 记录项目根路径 |
| `shell/src/snowel/mcp_server.py` | 修改 | generate/writeback/search/audit/rewrite 接线 |
| `shell/src/snowel/cli.py` | 修改 | export 接线、status 流程行 |
| `shell/src/snowel/project.py` | 修改 | L5 readonly 翻转 |
| `tests/conftest.py` | 修改 | core_conn/api fixture、FakeBackend |
| `tests/{llm,retrieval,writeback,flow}/` | 新建 | 四模块测试目录（README §1 登记） |

---

### Task 1: 挂账修复波 L1 + L2 + L5 与测试基建

**Files:**
- Modify: `src/snowel_core/ontology/groups.py:14-29`、`src/snowel_core/ontology/completeness.py`（docstring）
- Modify: `shell/src/snowel/project.py:49-63`
- Modify: `tests/conftest.py`（空占位 → 公共 fixture）
- Test: `tests/ontology/test_ontology.py`（追加）、`tests/shell/test_project.py`（追加）

**Interfaces:**
- Consumes: 现有 `groups.validate(group_name, data) -> (status, warn)`、`ProjectContext.require_write()`。
- Produces: `validate` 对畸形 `_schema` 返回 `("version_mismatch", ...)` 不抛异常；`derive(props)` 签名冻结为 `derive(props: dict) -> str`；`ProjectContext.readonly` 在失租后翻转为 True；`tests/conftest.py` 提供 `core_conn`/`api` fixture 与 `FakeBackend`（后续全部任务共用）。

- [ ] **Step 1: 写失败测试（L1）**

```python
# tests/ontology/test_ontology.py 追加
def test_validate_malformed_schema_version_degrades():  # L1：D3 降级精神
    status, warn = groups.validate("core", {
        "_schema": "demo@x",  # 畸形版本串
        "motivation": "m", "lie": "l", "fear": "f", "arc": "a"})
    assert status == "version_mismatch"
    assert warn and "demo@x" in warn
```

- [ ] **Step 2: 写失败测试（L2 签名冻结 + L5 翻转）**

```python
# tests/ontology/test_ontology.py 追加
def test_derive_signature_frozen():  # L2：以实现为准 derive(props)
    from snowel_core.ontology.completeness import derive
    assert derive({}) == "draft"
    assert derive({"core": {"motivation": "a", "lie": "b",
                            "fear": "c", "arc": "d"}}) == "profiled"
    assert derive({"core": {"motivation": "a"}}) == "draft"
```

```python
# tests/shell/test_project.py 追加
def test_lease_lost_flips_readonly(tmp_path):
    # L5：心跳失租后 readonly 必须翻转，require_write 拒绝
    from snowel import project as P
    from snowel_core.api import SnowelAPI
    SnowelAPI.init_project(tmp_path)
    ctx = P.open_project(tmp_path, stale_after=0.2, heartbeat=True)
    assert not ctx.readonly
    # 模拟持租进程僵死：把心跳戳拨回过去，他端抢租
    other = SnowelAPI.open(tmp_path)
    other._conn.execute("UPDATE lease SET heartbeat_ts=0")
    assert other.acquire_lease("rival@x:1", stale_after=0.2)
    other.close()
    import time; time.sleep(0.5)  # 等心跳线程 renew 失败（interval≈0.067s）
    assert ctx.readonly
    with pytest.raises(P.ProjectError):
        ctx.require_write()
    ctx.close()
```

- [ ] **Step 3: 跑测试确认失败**

Run: `pytest tests/ontology tests/shell/test_project.py -v`
Expected: 新增 3 例 FAIL（L1 抛 ValueError；L5 readonly 仍 False）——`test_derive_signature_frozen` 可能直接 PASS，属冻结性回归测试，允许。

- [ ] **Step 4: 最小实现**

```python
# groups.py validate() 内 declared 解析处替换
    declared = None
    if isinstance(data.get("_schema"), str) and "@" in data["_schema"]:
        try:
            declared = int(data["_schema"].split("@")[1])
        except ValueError:  # L1：畸形版本串按版本不匹配降级警告，不阻断（D3）
            return "version_mismatch", (
                f"组 {group_name} 版本串畸形: {data['_schema']!r}")
```

```python
# project.py _loop() 失租分支
                if not api2.renew_lease(self.holder):
                    self.readonly = True  # L5：失租即翻只读，关死双写窗口
                    break
```

```python
# completeness.py derive 上补 docstring（签名以实现为准，L2 关账）
def derive(props: dict) -> str:
    """draft/profiled 推导（props 无 IO）；active=正文登场，由抽取 appeared 接线（回写环计划）。"""
```

```python
# tests/conftest.py 全量替换
import pytest
from snowel_core.storage import db


@pytest.fixture
def core_conn(tmp_path):
    conn = db.connect(tmp_path / "snowel.db")
    db.migrate(conn)
    yield conn
    conn.close()


@pytest.fixture
def api(tmp_path):
    from snowel_core.api import SnowelAPI
    a = SnowelAPI.init_project(tmp_path)
    yield a
    a.close()


class FakeBackend:
    """确定性生成端（tests/README §3）：按预设队列返回响应，记录调用供断言。"""

    def __init__(self, responses: list[str]):
        self.calls: list[dict] = []
        self._responses = list(responses)

    def generate(self, prompt: str, *, model: str | None = None,
                 system: str | None = None) -> str:
        self.calls.append({"prompt": prompt, "model": model, "system": system})
        return self._responses.pop(0)
```

- [ ] **Step 5: 跑测试通过后提交**

Run: `pytest tests/ontology tests/shell -v` → PASS
```bash
git add -A && git commit -m "fix: ledger L1 malformed schema degrade, L5 readonly flip on lease loss, L2 derive freeze + test infra"
```

---

### Task 2: 项目配置 KV 与嵌入 provider 接口

**Files:**
- Modify: `src/snowel_core/storage/schema.sql`（+config 表）
- Create: `src/snowel_core/storage/config.py`、`src/snowel_core/llm/__init__.py`、`src/snowel_core/llm/embed.py`
- Modify: `pyproject.toml`（dependencies + extras）
- Test: `tests/llm/test_embed.py`

**Interfaces:**
- Consumes: `db.connect/migrate`。
- Produces:
  - `storage.config.get(conn, key, default=None) -> Any`（JSON 编解码）；`storage.config.set(conn, key, value) -> None`。
  - `llm.embed.EmbeddingProvider` 协议：`embed(texts: list[str]) -> list[list[float]]`、`name() -> str`、`dim -> int`。
  - `llm.embed.DeterministicEmbed`（dim=64，sha256 派生向量，name `"deterministic-hash-64"`）。
  - `llm.embed.get_provider(conn) -> EmbeddingProvider`：读 config `embedding.provider`（默认 `"deterministic"`）；`"fastembed"` 时 `import fastembed`（未装 extras 抛 ImportError 带安装指引）。

- [ ] **Step 1: 写失败测试**

```python
# tests/llm/test_embed.py
import json
import pytest
from snowel_core.storage import config
from snowel_core.storage.db import transaction
from snowel_core.llm.embed import DeterministicEmbed, get_provider


def test_config_kv_roundtrip(core_conn):
    config.set(core_conn, "embedding.provider", "deterministic")
    assert config.get(core_conn, "embedding.provider") == "deterministic"
    assert config.get(core_conn, "nope", default=42) == 42


def test_deterministic_embed_stable_and_dim():
    e = DeterministicEmbed()
    v1, v2 = e.embed(["林晚握紧了积分卡", "林晚握紧了积分卡"])
    assert v1 == v2 and len(v1) == e.dim == 64
    assert e.embed(["另一段"])[0] != v1


def test_get_provider_default_and_fastembed_missing(core_conn):
    assert isinstance(get_provider(core_conn), DeterministicEmbed)
    config.set(core_conn, "embedding.provider", "fastembed")
    with pytest.raises(ImportError, match="pip install snowel-core\\[embed\\]"):
        get_provider(core_conn)
```

- [ ] **Step 2: 跑测试确认失败**（ModuleNotFoundError: snowel_core.llm）

- [ ] **Step 3: 最小实现**

```sql
-- schema.sql 追加
CREATE TABLE IF NOT EXISTS config(
  key   TEXT PRIMARY KEY,
  value TEXT NOT NULL
);
```

```python
# src/snowel_core/storage/config.py
import json
import sqlite3


def get(conn: sqlite3.Connection, key: str, default=None):
    row = conn.execute("SELECT value FROM config WHERE key=?", (key,)).fetchone()
    return json.loads(row["value"]) if row else default


def set(conn: sqlite3.Connection, key: str, value) -> None:
    conn.execute(
        "INSERT INTO config(key, value) VALUES(?, ?) "
        "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
        (key, json.dumps(value, ensure_ascii=False)))
```

```python
# src/snowel_core/llm/embed.py
import hashlib
import sqlite3

from ..storage import config


class EmbeddingProvider:
    def embed(self, texts: list[str]) -> list[list[float]]: ...
    def name(self) -> str: ...
    dim: int = 0


class DeterministicEmbed(EmbeddingProvider):
    """零依赖确定性嵌入（默认）：sha256 派生定长向量，测试与离线兜底。"""
    dim = 64

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [self._vec(t) for t in texts]

    def name(self) -> str:
        return "deterministic-hash-64"

    @staticmethod
    def _vec(text: str) -> list[float]:
        out: list[float] = []
        seed = text.encode("utf-8")
        while len(out) < DeterministicEmbed.dim:
            seed = hashlib.sha256(seed).digest()
            out.extend(b / 255.0 for b in seed)
        return out[:DeterministicEmbed.dim]


def get_provider(conn: sqlite3.Connection) -> EmbeddingProvider:
    kind = config.get(conn, "embedding.provider", "deterministic")
    if kind == "deterministic":
        return DeterministicEmbed()
    if kind == "fastembed":
        try:
            from fastembed import TextEmbedding  # extras: snowel-core[embed]
        except ImportError as e:
            raise ImportError(
                "embedding.provider=fastembed 需要 pip install snowel-core[embed]"
            ) from e

        class FastembedProvider(EmbeddingProvider):
            dim = 512  # bge-small-zh-v1.5

            def __init__(self):
                self._m = TextEmbedding("BAAI/bge-small-zh-v1.5")

            def embed(self, texts):
                return [list(map(float, v)) for v in self._m.embed(texts)]

            def name(self):
                return "fastembed:bge-small-zh-v1.5"

        return FastembedProvider()
    raise ValueError(f"未知 embedding.provider：{kind}")
```

```toml
# pyproject.toml
dependencies = ["pydantic>=2.7", "litellm", "jieba>=0.42", "sqlite-vec>=0.1.6"]

[project.optional-dependencies]
embed = ["fastembed>=0.3"]
```

（litellm 不锁下界——2026 年主版本更迭快，执行期以当时最新稳定版安装并 Ruling 记录锁定上界；LitellmBackend 只用 `litellm.completion` 基础面，跨版本稳定。）

注意：`litellm`/`jieba`/`sqlite-vec` 本任务只进依赖声明（后续任务 import），执行者需 `pip install -e .` 刷新环境后跑全量。

- [ ] **Step 4: 跑测试通过**：`pytest tests/llm -v`
- [ ] **Step 5: 提交**：`git commit -m "feat(core): config kv + embedding provider interface with deterministic default"`

---

### Task 3: 正文镜像与对账（D8/C1 存储面）

**Files:**
- Modify: `src/snowel_core/storage/schema.sql`（+chapter_prose）
- Create: `src/snowel_core/writeback/__init__.py`、`src/snowel_core/writeback/mirror.py`
- Modify: `src/snowel_core/storage/projector.py`（+2 handler、rebuild 清单）
- Test: `tests/writeback/test_mirror.py`

**Interfaces:**
- Consumes: `events.append_event`、`projector.apply`、`db.transaction`。
- Produces:
  - 事件 `prose_hash_registered` payload `{chapter_id, path, hash}`；`prose_external_change` payload `{chapter_id, path, old_hash, new_hash}`（P1：全文不进事件）。
  - `writeback.mirror.write_prose(conn, project_root: Path, chapter_id: str, content: str) -> int`：写文件（P5 路径 `chapters/<chapter_id>.md`，父目录自动建）→ 事务内追加 `prose_hash_registered` + apply → 返回事件 seq。哈希 = `sha256(content)` 十六进制。
  - `writeback.mirror.reconcile(conn, project_root: Path) -> list[dict]`：对每个已登记章节，文件存在且哈希≠登记值 → 事务内追加 `prose_external_change` + apply + 镜像全文重灌（从文件读）；文件缺失 → 结果含 `{chapter_id, status: "missing_file"}` 警告不写事件；哈希一致 → 跳过（hook 短路基础，TC-WB-02）。返回变更列表。
  - 投影器：两 handler 只 upsert `chapter_prose(chapter_id, path, hash, prose='', updated_event)`；`rebuild` 清空清单加 `chapter_prose`（P1：全文靠对账重灌）。

- [ ] **Step 1: 写失败测试**

```python
# tests/writeback/test_mirror.py
import hashlib
from snowel_core.storage import db, events, queries
from snowel_core.writeback import mirror


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def test_write_prose_registers_file_and_event(api, tmp_path):
    seq = mirror.write_prose(api._conn, tmp_path, "ch1", "第一章正文")
    f = tmp_path / "chapters" / "ch1.md"
    assert f.read_text(encoding="utf-8") == "第一章正文"
    row = events_by_kind(api, "prose_hash_registered")
    assert row["seq"] == seq
    assert _sha("第一章正文") in (row["payload_hash"])
    prose = api._conn.execute(
        "SELECT * FROM chapter_prose WHERE chapter_id='ch1'").fetchone()
    assert prose["hash"] == _sha("第一章正文") and prose["path"] == str(f)


def events_by_kind(api, kind):
    r = api._conn.execute(
        "SELECT * FROM events WHERE kind=? ORDER BY seq DESC", (kind,)).fetchone()
    r = dict(r); r["payload_hash"] = __import__("json").loads(r["payload"])["hash"]
    return r


def test_reconcile_rebuilds_mirror_from_file(api, tmp_path):  # TC-WB-05
    mirror.write_prose(api._conn, tmp_path, "ch1", "旧正文")
    (tmp_path / "chapters" / "ch1.md").write_text("新正文（外部编辑）", encoding="utf-8")
    changes = mirror.reconcile(api._conn, tmp_path)
    assert changes == [{"chapter_id": "ch1", "status": "external_change"}]
    ev = api._conn.execute(
        "SELECT payload FROM events WHERE kind='prose_external_change'").fetchone()
    import json
    p = json.loads(ev["payload"])
    assert p == {"chapter_id": "ch1",
                 "path": str(tmp_path / "chapters" / "ch1.md"),
                 "old_hash": _sha("旧正文"), "new_hash": _sha("新正文（外部编辑）")}
    prose = api._conn.execute(
        "SELECT prose, hash FROM chapter_prose WHERE chapter_id='ch1'").fetchone()
    assert prose["prose"] == "新正文（外部编辑）"      # 镜像以文件为准重灌


def test_reconcile_shortcircuits_registered_hash(api, tmp_path):  # TC-WB-02 基础
    mirror.write_prose(api._conn, tmp_path, "ch1", "正文")
    assert mirror.reconcile(api._conn, tmp_path) == []   # 哈希已登记 → 短路
    n = api._conn.execute(
        "SELECT count(*) c FROM events WHERE kind='prose_external_change'"
    ).fetchone()["c"]
    assert n == 0


def test_reconcile_reports_missing_file(api, tmp_path):
    mirror.write_prose(api._conn, tmp_path, "ch1", "正文")
    (tmp_path / "chapters" / "ch1.md").unlink()
    assert mirror.reconcile(api._conn, tmp_path) == [
        {"chapter_id": "ch1", "status": "missing_file"}]
```

- [ ] **Step 2: 跑测试确认失败**（No module named snowel_core.writeback / no such table: chapter_prose）

- [ ] **Step 3: 最小实现**

```sql
-- schema.sql 追加
CREATE TABLE IF NOT EXISTS chapter_prose(
  chapter_id    TEXT PRIMARY KEY,
  path          TEXT NOT NULL,
  hash          TEXT NOT NULL,
  prose         TEXT NOT NULL DEFAULT '',
  updated_event INTEGER NOT NULL REFERENCES events(seq)
);
```

```python
# src/snowel_core/writeback/mirror.py
import hashlib
import json
import sqlite3
from pathlib import Path

from ..storage import events, projector
from ..storage.db import transaction


def _sha(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def prose_path(project_root: Path, chapter_id: str) -> Path:  # P5 约定
    return project_root / "chapters" / f"{chapter_id}.md"


def write_prose(conn: sqlite3.Connection, project_root: Path,
                chapter_id: str, content: str) -> int:
    """确认即写文件（C1）：文件落盘 + 登记哈希（事件+镜像），同一事务物化。"""
    f = prose_path(project_root, chapter_id)
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(content, encoding="utf-8")
    with transaction(conn):
        seq = events.append_event(conn, "prose_hash_registered", {
            "chapter_id": chapter_id, "path": str(f), "hash": _sha(content)})
        projector.apply(conn)
    return seq


def reconcile(conn: sqlite3.Connection, project_root: Path) -> list[dict]:
    """D8 对账：文件是真相源，哈希不一致以文件为准重灌镜像。"""
    changes = []
    for r in conn.execute("SELECT chapter_id, path, hash FROM chapter_prose"):
        f = Path(r["path"])
        if not f.exists():
            changes.append({"chapter_id": r["chapter_id"], "status": "missing_file"})
            continue
        content = f.read_text(encoding="utf-8")
        new_hash = _sha(content)
        if new_hash == r["hash"]:
            continue  # 已登记写入短路（TC-WB-02）：核心代写的文件不再触发
        with transaction(conn):
            events.append_event(conn, "prose_external_change", {
                "chapter_id": r["chapter_id"], "path": str(f),
                "old_hash": r["hash"], "new_hash": new_hash})
            projector.apply(conn)
            conn.execute("UPDATE chapter_prose SET prose=? WHERE chapter_id=?",
                         (content, r["chapter_id"]))
        changes.append({"chapter_id": r["chapter_id"], "status": "external_change"})
    return changes
```

```python
# projector.py 追加 handler（并入 HANDLERS）
def _prose_event(tx, payload: dict, seq: int):
    # P1：事件只登记哈希；全文由 writeback 对账从文件灌入
    tx.execute(
        """INSERT INTO chapter_prose(chapter_id, path, hash, prose, updated_event)
           VALUES(?,?,?,?,?)
           ON CONFLICT(chapter_id) DO UPDATE SET
             hash=excluded.hash, path=excluded.path,
             updated_event=excluded.updated_event""",
        (payload["chapter_id"], payload["path"], payload["hash"], "", seq))


HANDLERS.update({
    "prose_hash_registered": _prose_event,
    "prose_external_change": _prose_event,
})
# rebuild() 清空清单："alias","edges","nodes","tracks","chapter_prose","checkpoint"
```

- [ ] **Step 4: 跑测试通过**：`pytest tests/writeback -v`
- [ ] **Step 5: 提交**：`git commit -m "feat(writeback): chapter prose mirror, hash registration and file-first reconcile (D8/C1)"`

---

### Task 4: FTS5 + jieba 检索（nodes + prose）

**Files:**
- Modify: `src/snowel_core/storage/schema.sql`（+2 fts5 虚表）
- Create: `src/snowel_core/storage/fts.py`
- Modify: `src/snowel_core/storage/projector.py`（apply 尾部 FTS 重灌）
- Test: `tests/storage/test_fts.py`

**Interfaces:**
- Consumes: Task 3 的 `chapter_prose`（prose 列灌全文）。
- Produces:
  - `fts.tokenize(text: str) -> str`：jieba `cut_for_search` 切词、去空白标点、空格连接（P3）。
  - `fts.refresh(conn) -> None`：全量重灌 `node_fts(node_id UNINDEXED, text)`（nodes active=1 的 name+alias+props 扁平串）与 `prose_fts(chapter_id UNINDEXED, para_idx UNINDEXED, text)`（镜像 prose 按空行分段）。apply 尾部自动调用（P2）。
  - `fts.search(conn, q: str, limit: int = 20) -> dict`：`{"nodes": [{node_id, name}], "paragraphs": [{chapter_id, para_idx, text}]}`。查询侧同 tokenize 后拼 AND 短语（词带引号 + 前缀 `*`）。

- [ ] **Step 1: 写失败测试**

```python
# tests/storage/test_fts.py
from snowel_core.storage import db, events, fts, projector


def _confirm(conn, facts):
    with db.transaction(conn):
        events.append_event(conn, "proposal_confirmed",
                            {"facts": facts, "artifact_type": "t"})
    projector.apply(conn)


def test_fts_finds_node_by_name_and_alias(core_conn):
    _confirm(core_conn, [{"fact": "node", "id": "n1",
                          "types": ["Character"], "name": "江晚",
                          "props": {"core": {"motivation": "活下去"}}}])
    with db.transaction(core_conn):
        events.append_event(core_conn, "retcon_applied", {"renames": [
            {"node_id": "n1", "old_name": "林晚", "new_name": "江晚"}]})
    projector.apply(core_conn)
    r = fts.search(core_conn, "林晚")          # TC-ON-02 FTS 面：旧名经 alias 命中
    assert [h["node_id"] for h in r["nodes"]] == ["n1"]
    r2 = fts.search(core_conn, "活下去")        # props 扁平文本命中
    assert [h["node_id"] for h in r2["nodes"]] == ["n1"]


def test_fts_finds_prose_paragraph(core_conn, tmp_path):
    from snowel_core.writeback import mirror
    mirror.write_prose(core_conn, tmp_path, "ch1", "第一段：林晚登场\n\n第二段：积分兑换")
    core_conn.execute(
        "UPDATE chapter_prose SET prose=? WHERE chapter_id='ch1'",
        ("第一段：林晚登场\n\n第二段：积分兑换",))
    fts.refresh(core_conn)
    r = fts.search(core_conn, "积分兑换")
    assert r["paragraphs"] and r["paragraphs"][0]["para_idx"] == 1
    assert r["paragraphs"][0]["chapter_id"] == "ch1"


def test_fts_retraction_removes_hit(core_conn):
    _confirm(core_conn, [{"fact": "node", "id": "n1", "types": ["Concept"],
                          "name": "临时设定", "props": {}}])
    assert fts.search(core_conn, "临时设定")["nodes"]
    with db.transaction(core_conn):
        events.append_event(core_conn, "retraction",
                            {"target": "node", "target_id": "n1"})
    projector.apply(core_conn)
    assert fts.search(core_conn, "临时设定")["nodes"] == []
```

- [ ] **Step 2: 跑测试确认失败**（No module named snowel_core.storage.fts）

- [ ] **Step 3: 最小实现**

```python
# src/snowel_core/storage/fts.py
import json
import re
import sqlite3

import jieba

_PUNCT = re.compile(r"^[\W_]+$", re.UNICODE)


def tokenize(text: str) -> str:  # P3：Python 侧 jieba 预分词，空格分隔 token 串
    return " ".join(t for t in jieba.cut_for_search(text)
                    if t.strip() and not _PUNCT.match(t))


def refresh(conn: sqlite3.Connection) -> None:  # P2：FTS 便宜，apply 内全量重灌
    conn.execute("DELETE FROM node_fts")
    rows = conn.execute("SELECT id, name, props FROM nodes WHERE active=1").fetchall()
    data = []
    for r in rows:
        props = json.loads(r["props"])
        flat = " ".join(str(v) for g in props.values()
                        if isinstance(g, dict) for v in g.values())
        aliases = [a["alias"] for a in conn.execute(
            "SELECT alias FROM alias WHERE node_id=?", (r["id"],))]
        text = tokenize(" ".join([r["name"], *aliases, flat]))
        data.append((r["id"], text))
    conn.executemany("INSERT INTO node_fts(node_id, text) VALUES(?,?)", data)

    conn.execute("DELETE FROM prose_fts")
    paras = []
    for r in conn.execute("SELECT chapter_id, prose FROM chapter_prose"):
        for i, para in enumerate(r["prose"].split("\n\n")):
            if para.strip():
                paras.append((r["chapter_id"], i, tokenize(para)))
    conn.executemany(
        "INSERT INTO prose_fts(chapter_id, para_idx, text) VALUES(?,?,?)", paras)


def _query_expr(q: str) -> str:
    return " AND ".join(f'"{t}"*' for t in tokenize(q).split()[:8])


def search(conn: sqlite3.Connection, q: str, limit: int = 20) -> dict:
    expr = _query_expr(q)
    if not expr:
        return {"nodes": [], "paragraphs": []}
    nodes = [{"node_id": r["node_id"],
              "name": conn.execute("SELECT name FROM nodes WHERE id=?",
                                   (r["node_id"],)).fetchone()["name"]}
             for r in conn.execute(
                 "SELECT node_id FROM node_fts WHERE node_fts MATCH ? LIMIT ?",
                 (expr, limit))]
    paras = [dict(r) for r in conn.execute(
        "SELECT chapter_id, para_idx, text FROM prose_fts "
        "WHERE prose_fts MATCH ? LIMIT ?", (expr, limit))]
    return {"nodes": nodes, "paragraphs": paras}
```

```sql
-- schema.sql 追加
CREATE VIRTUAL TABLE IF NOT EXISTS node_fts USING fts5(
  node_id UNINDEXED, text);
CREATE VIRTUAL TABLE IF NOT EXISTS prose_fts USING fts5(
  chapter_id UNINDEXED, para_idx UNINDEXED, text);
```

```python
# projector.py apply() 尾部（checkpoint 写入前）：
    from . import fts
    fts.refresh(conn)
```

注意：`apply` 在事务内被调用，FTS 重灌同事务（E1 一次确认=事件+物化+索引）。`search` 内逐 node_id 查 name 保留 N+1（检索低频路径，沿用仓库已知 minor 风格，不修）。

- [ ] **Step 4: 跑测试通过**：`pytest tests/storage/test_fts.py tests/writeback -v`
- [ ] **Step 5: 提交**：`git commit -m "feat(storage): FTS5 with jieba pre-tokenization for nodes and prose (P2/P3)"`

---

### Task 5: sqlite-vec 向量与嵌入重建（C6）

**Files:**
- Modify: `src/snowel_core/storage/schema.sql`（+2 vec0 虚表，见实现内 SQL）
- Create: `src/snowel_core/storage/vec.py`
- Test: `tests/storage/test_vec.py`

**Interfaces:**
- Consumes: Task 2 `llm.embed.get_provider`/`DeterministicEmbed`、`storage.config`；Task 3 `chapter_prose`。
- Produces:
  - `vec.ensure(conn) -> None`：`sqlite_vec.load(conn)` + 建 `node_vec`/`prose_vec` 虚表（`embedding float[64]`，`node_id TEXT PRIMARY KEY` / `chapter_id, para_idx` 复合主键）。db.migrate 后由 api.open/init 调用。
  - `vec.rebuild_embeddings(conn, provider=None) -> dict`：provider 缺省 `get_provider(conn)`；nodes（name+扁平 props 文本）与 prose 段落全量重算写入；返回 `{"provider": name, "nodes": n, "paragraphs": m}`；同时 config.set `embedding.built_with = name`（C6 校验依据）。
  - `vec.search(conn, q: str, limit: int = 10) -> list[dict]`：查询向量 KNN，返回 `[{kind: "node"|"paragraph", node_id/chapter_id, para_idx?, distance}]`。

- [ ] **Step 1: 写失败测试**

```python
# tests/storage/test_vec.py
from snowel_core.llm.embed import DeterministicEmbed
from snowel_core.storage import config, db, events, projector, vec


def _confirm(conn, facts):
    with db.transaction(conn):
        events.append_event(conn, "proposal_confirmed",
                            {"facts": facts, "artifact_type": "t"})
    projector.apply(conn)


def test_rebuild_and_knn_search(core_conn, tmp_path):
    from snowel_core.writeback import mirror
    vec.ensure(core_conn)
    _confirm(core_conn, [{"fact": "node", "id": "n1", "types": ["Character"],
                          "name": "林晚", "props": {}}])
    mirror.write_prose(core_conn, tmp_path, "ch1", "林晚在轮回游戏里攒积分")
    core_conn.execute("UPDATE chapter_prose SET prose=? WHERE chapter_id='ch1'",
                      ("林晚在轮回游戏里攒积分",))
    stats = vec.rebuild_embeddings(core_conn)
    assert stats == {"provider": "deterministic-hash-64",
                     "nodes": 1, "paragraphs": 1}
    r = vec.search(core_conn, "林晚", limit=5)
    assert {h["kind"] for h in r} == {"node", "paragraph"}


def test_switch_provider_rebuilds_per_project(core_conn, api, tmp_path):  # TC-RT-06
    # core_conn 与 api 是两个独立库：切换只重建该书
    vec.ensure(core_conn); vec.ensure(api._conn)
    _confirm(core_conn, [{"fact": "node", "id": "n1", "types": ["Character"],
                          "name": "林晚", "props": {}}])
    config.set(core_conn, "embedding.provider", "deterministic")  # 模拟"切换"
    a = vec.rebuild_embeddings(core_conn)
    assert config.get(core_conn, "embedding.built_with") == a["provider"]
    assert config.get(api._conn, "embedding.built_with") is None  # 另一书未动
```

- [ ] **Step 2: 跑测试确认失败**

- [ ] **Step 3: 最小实现**

```python
# src/snowel_core/storage/vec.py
import json
import sqlite3

import sqlite_vec

from ..llm.embed import get_provider
from ..storage import config

_VEC_SQL = """
CREATE VIRTUAL TABLE IF NOT EXISTS node_vec USING vec0(
  node_id TEXT PRIMARY KEY, embedding float[64]);
CREATE VIRTUAL TABLE IF NOT EXISTS prose_vec USING vec0(
  chapter_id TEXT, para_idx INTEGER, embedding float[64]);
"""


def ensure(conn: sqlite3.Connection) -> None:
    sqlite_vec.load(conn)
    conn.executescript(_VEC_SQL)


def _node_text(r) -> str:
    props = json.loads(r["props"])
    flat = " ".join(str(v) for g in props.values()
                    if isinstance(g, dict) for v in g.values())
    return f"{r['name']} {flat}"


def rebuild_embeddings(conn: sqlite3.Connection, provider=None) -> dict:  # P2：显式重建
    p = provider or get_provider(conn)
    nodes = conn.execute(
        "SELECT id, name, props FROM nodes WHERE active=1").fetchall()
    paras = [(r["chapter_id"], i, t)
             for r in conn.execute("SELECT chapter_id, prose FROM chapter_prose")
             for i, t in enumerate(r["prose"].split("\n\n")) if t.strip()]
    vecs_n = p.embed([_node_text(r) for r in nodes])
    vecs_p = p.embed([t for _, _, t in paras])
    conn.execute("DELETE FROM node_vec"); conn.execute("DELETE FROM prose_vec")
    conn.executemany("INSERT INTO node_vec(node_id, embedding) VALUES(?,?)",
                     [(r["id"], json.dumps(v)) for r, v in zip(nodes, vecs_n)])
    conn.executemany(
        "INSERT INTO prose_vec(chapter_id, para_idx, embedding) VALUES(?,?,?)",
        [(c, i, json.dumps(v)) for (c, i, _), v in zip(paras, vecs_p)])
    config.set(conn, "embedding.built_with", p.name())
    return {"provider": p.name(), "nodes": len(nodes), "paragraphs": len(paras)}


def search(conn: sqlite3.Connection, q: str, limit: int = 10) -> list[dict]:
    p = get_provider(conn)
    qv = json.dumps(p.embed([q])[0])
    out = []
    for r in conn.execute(
            "SELECT node_id, distance FROM node_vec "
            "WHERE embedding MATCH ? AND k=?", (qv, limit)):
        out.append({"kind": "node", "node_id": r["node_id"],
                    "distance": r["distance"]})
    for r in conn.execute(
            "SELECT chapter_id, para_idx, distance FROM prose_vec "
            "WHERE embedding MATCH ? AND k=?", (qv, limit)):
        out.append({"kind": "paragraph", "chapter_id": r["chapter_id"],
                    "para_idx": r["para_idx"], "distance": r["distance"]})
    return out
```

`api.init_project`/`api.open` 末尾加 `vec.ensure(conn)`（migrate 后必然可用）。

- [ ] **Step 4: 跑测试通过**：`pytest tests/storage/test_vec.py -v`
- [ ] **Step 5: 提交**：`git commit -m "feat(storage): sqlite-vec embeddings with per-project provider rebuild (C6)"`

---

### Task 6: retrieval_audit + compose_context 基座（E3/§6）

**Files:**
- Modify: `src/snowel_core/storage/schema.sql`（+retrieval_audit）
- Create: `src/snowel_core/retrieval/__init__.py`、`src/snowel_core/retrieval/audit.py`、`src/snowel_core/retrieval/context.py`、`src/snowel_core/retrieval/hybrid.py`
- Test: `tests/retrieval/test_context.py`

**Interfaces:**
- Consumes: Task 4 `fts.search`、Task 5 `vec.search`、现有 `queries.state_at`。
- Produces:
  - `retrieval.audit.record(conn, strategy, locate, dry_run, bundle) -> int`；`retrieval.audit.recent(conn, limit=50) -> list[dict]`。
  - `retrieval.hybrid.search(conn, q, limit=20, mode="hybrid") -> dict`：`mode ∈ {fts, vec, hybrid}`；hybrid = FTS 命中优先 + vec 补充去重；node 命中附 `dead_beat` 标记（查 props.core.death_beat 的 story_order，TC-RT-03）。
  - `retrieval.context.compose_context(conn, strategy: str, locate: dict | None = None, dry_run: bool = False) -> dict`（E3 只读暴露）：策略表 v1 三条——
    - `"prose"`（正文/小雪花）：pull = 场景卡要素（locate.chapter 所属场景卡节点全文）+ 在场角色档案（场景卡 `props.characters` ∩ `state_at(locate.story_order)` 存活，裁剪到 core 组）+ 未回收伏笔 ∩ 相关（Foreshadow 节点 `props.payoff` 为空或 > locate.story_order，且 FTS 相关）+ 已确认世界观（types 含 Concept 的非 TODO 节点）；fallback = hybrid（用章关键词）；TODO 排除（`props.core.todo == true` 的节点不进任何 section）。
    - `"character"`：pull = 该角色节点 + 相邻关系边对端；fallback = fts。
    - `"generic"`：pull = 空；fallback = fts（查询词 = locate.query）。
  - 还认 `{"strategy", "locate", "sections": [{"kind", "refs", "text"}], "audit_id"}`；死亡角色过滤按 state_at（TC-RT-03 前半），兜底召回命中死亡角色时 section 条目附 `"dead_beat": <拍>`（后半）。
  - 每次调用（含 dry_run）写 audit（TC-RT-02），dry_run 行标注 `"dry_run": 1`。

- [ ] **Step 1: 写失败测试**

```python
# tests/retrieval/test_context.py
import json
from snowel_core.retrieval import audit, context, hybrid
from snowel_core.storage import db, events, projector


def _confirm(conn, facts, kind="t"):
    with db.transaction(conn):
        events.append_event(conn, "proposal_confirmed",
                            {"facts": facts, "artifact_type": kind})
    projector.apply(conn)


def _seed_book(conn):
    _confirm(conn, [
        {"fact": "node", "id": "sc1", "types": ["Scene"], "name": "雨夜初见",
         "props": {"characters": ["hero"], "required_elements": ["雨夜"],
                   "chapter": "ch1"}},
        {"fact": "node", "id": "hero", "types": ["Character"], "name": "林晚",
         "props": {"core": {"motivation": "活下来", "lie": "没人会救我",
                            "fear": "深渊", "arc": "学会信任"}}},
        {"fact": "node", "id": "dead1", "types": ["Character"], "name": "旧队友",
         "props": {"core": {"death_beat": "mb0", "motivation": "x",
                            "lie": "x", "fear": "x", "arc": "x"}}},
        {"fact": "node", "id": "mb0", "types": ["MicroBeat"], "name": "开场",
         "props": {"address": {"volume": 1, "chapter": 1, "scene": 1, "beat": 1}}},
        {"fact": "node", "id": "mb1", "types": ["MicroBeat"], "name": "遇难",
         "props": {"address": {"volume": 1, "chapter": 1, "scene": 1, "beat": 2}}},
        {"fact": "node", "id": "fs1", "types": ["Foreshadow"], "name": "怀表",
         "props": {"planted_at": "mb0"}},
        {"fact": "node", "id": "todo1", "types": ["Concept"], "name": "待补设定",
         "props": {"core": {"todo": True}}},
        {"fact": "node", "id": "w1", "types": ["Concept"], "name": "轮回游戏",
         "props": {}},
    ])


def test_compose_context_prose_strategy(core_conn):  # TC-RT-01
    _seed_book(core_conn)
    bundle = context.compose_context(
        core_conn, "prose", locate={"chapter": "ch1", "story_order": 1})
    kinds = [s["kind"] for s in bundle["sections"]]
    assert kinds == ["scene_card", "characters", "foreshadows", "worldview"]
    chars = bundle["sections"][1]
    assert chars["refs"] == ["hero"]                    # 死亡角色（death_beat=mb0≤1）被过滤
    world = bundle["sections"][3]
    assert "todo1" not in [r for s in bundle["sections"] for r in s["refs"]]  # TODO 排除
    assert "w1" in world["refs"]


def test_compose_context_dry_run_audited(core_conn):  # TC-RT-02
    _seed_book(core_conn)
    b1 = context.compose_context(core_conn, "generic", locate={"query": "轮回"},
                                 dry_run=True)
    rows = audit.recent(core_conn)
    assert len(rows) == 1 and rows[0]["dry_run"] == 1
    assert rows[0]["id"] == b1["audit_id"]
    context.compose_context(core_conn, "generic", locate={"query": "轮回"})
    assert audit.recent(core_conn)[0]["dry_run"] == 0   # 非 dry_run 标注 0


def test_hybrid_search_marks_dead(core_conn):  # TC-RT-03 兜底标记
    _seed_book(core_conn)
    r = hybrid.search(core_conn, "旧队友")
    dead = [h for h in r["nodes"] if h["node_id"] == "dead1"]
    assert dead and dead[0]["dead_beat"] == 1           # mb0 → story_order 1，附"已死亡@拍"
```

- [ ] **Step 2: 跑测试确认失败**

- [ ] **Step 3: 最小实现**

```python
# src/snowel_core/retrieval/audit.py
import json
import sqlite3
from datetime import datetime, timezone


def record(conn, strategy: str, locate, dry_run: bool, bundle: dict) -> int:
    cur = conn.execute(
        "INSERT INTO retrieval_audit(ts, strategy, dry_run, locate, bundle) "
        "VALUES(?,?,?,?,?)",
        (datetime.now(timezone.utc).isoformat(), strategy, int(dry_run),
         json.dumps(locate or {}, ensure_ascii=False),
         json.dumps({"sections": bundle["sections"]}, ensure_ascii=False)))
    return cur.lastrowid


def recent(conn, limit: int = 50) -> list[dict]:
    return [dict(r) for r in conn.execute(
        "SELECT * FROM retrieval_audit ORDER BY id DESC LIMIT ?", (limit,))]
```

```python
# src/snowel_core/retrieval/hybrid.py
import json
import sqlite3

from ..storage import fts, queries, vec


def search(conn: sqlite3.Connection, q: str, limit: int = 20,
           mode: str = "hybrid") -> dict:
    out: dict = {"nodes": [], "paragraphs": []}
    if mode in ("fts", "hybrid"):
        f = fts.search(conn, q, limit)
        out["paragraphs"] = f["paragraphs"]
        out["nodes"] = f["nodes"]
    if mode in ("vec", "hybrid"):
        vec.ensure(conn)  # vec0 虚表需扩展加载后建（幂等；直连 core_conn 的测试路径兜底）
        seen = {n["node_id"] for n in out["nodes"]}
        for h in vec.search(conn, q, limit):
            if h["kind"] == "node" and h["node_id"] not in seen:
                row = queries.get_node(conn, h["node_id"])
                if row is not None:
                    out["nodes"].append({"node_id": h["node_id"],
                                         "name": row["name"]})
    for n in out["nodes"]:  # TC-RT-03：死亡角色附"已死亡@拍N"
        row = queries.get_node(conn, n["node_id"])
        props = json.loads(row["props"])
        death = props.get("core", {}).get("death_beat")
        if death is not None:
            d = queries.get_node(conn, death)
            n["dead_beat"] = d["story_order"] if d and d["story_order"] is not None else -1
    return out
```

```python
# src/snowel_core/retrieval/context.py
import json
import sqlite3

from ..storage import queries
from . import audit, hybrid


def _alive(conn, node_ids, story_order):
    out = []
    for nid in node_ids:
        row = queries.get_node(conn, nid)
        if row is None or not row["active"]:
            continue
        props = json.loads(row["props"])
        death = props.get("core", {}).get("death_beat")
        if death is not None:
            d = queries.get_node(conn, death)
            if d is not None and d["story_order"] is not None \
                    and d["story_order"] <= story_order:
                continue  # 已死亡@拍 ≤ 目标拍 → 不在场
        out.append(row)
    return out


def _node_section(conn, kind, rows, trim_core=False):
    texts = []
    for r in rows:
        props = json.loads(r["props"])
        if props.get("core", {}).get("todo"):
            continue  # TODO 设定项排除（§6.1）
        shown = {"core": props.get("core", {})} if trim_core else props
        texts.append(f"[{r['name']}] {json.dumps(shown, ensure_ascii=False)}")
    return {"kind": kind, "refs": [r["id"] for r in rows], "text": "\n".join(texts)}


def compose_context(conn: sqlite3.Connection, strategy: str,
                    locate: dict | None = None, dry_run: bool = False) -> dict:
    """E3：上下文组装唯一实现；检索审计每次落表（含 dry_run 标注）。"""
    locate = locate or {}
    sections = []
    if strategy == "prose":
        so = locate.get("story_order", 10 ** 9)
        scene = _scene_of_chapter(conn, locate.get("chapter"))
        if scene is not None:
            sections.append(_node_section(conn, "scene_card", [scene]))
            chars = _alive(conn, json.loads(scene["props"])
                           .get("characters", []), so)
            sections.append(_node_section(conn, "characters", chars,
                                          trim_core=True))
        open_fs = [r for r in conn.execute(
            "SELECT * FROM nodes WHERE active=1") if "Foreshadow" in r["types"]]
        sections.append(_node_section(conn, "foreshadows", open_fs))
        world = [r for r in conn.execute(
            "SELECT * FROM nodes WHERE active=1") if "Concept" in r["types"]]
        sections.append(_node_section(conn, "worldview", world))
    elif strategy == "character":
        row = queries.get_node(conn, locate["node_id"])
        peers = [queries.get_node(conn, e["dst"] if e["src"] == locate["node_id"]
                                  else e["src"])
                 for e in queries.edges_of(conn, locate["node_id"])]
        sections.append(_node_section(conn, "character", [row] if row else []))
        sections.append(_node_section(
            conn, "relations", [p for p in peers if p is not None]))
    q = locate.get("query") or locate.get("chapter") or ""
    if q:
        fallback = hybrid.search(conn, q, mode="hybrid")
        if fallback["nodes"] or fallback["paragraphs"]:
            sections.append({"kind": "fallback_recall",
                             "refs": [n["node_id"] for n in fallback["nodes"]],
                             "text": json.dumps(fallback, ensure_ascii=False)})
    bundle = {"strategy": strategy, "locate": locate, "sections": sections}
    bundle["audit_id"] = audit.record(conn, strategy, locate, dry_run, bundle)
    return bundle


def _scene_of_chapter(conn, chapter_id):
    for r in conn.execute("SELECT * FROM nodes WHERE active=1"):
        if "Scene" in r["types"] and json.loads(r["props"]).get("chapter") == chapter_id:
            return r
    return None
```

```sql
-- schema.sql 追加
CREATE TABLE IF NOT EXISTS retrieval_audit(
  id       INTEGER PRIMARY KEY AUTOINCREMENT,
  ts       TEXT NOT NULL,
  strategy TEXT NOT NULL,
  dry_run  INTEGER NOT NULL DEFAULT 0,
  locate   TEXT,
  bundle   TEXT NOT NULL
);
```

注：dry_run 语义 = 只读组装 + 审计标注；compose_context 本身不发 LLM 请求、不写图，全部路径天然只读（E3 dry_run 暴露）。

- [ ] **Step 4: 跑测试通过**：`pytest tests/retrieval -v`
- [ ] **Step 5: 提交**：`git commit -m "feat(retrieval): compose_context strategies, hybrid search and retrieval audit (E3/6.1/6.2)"`

---

### Task 7: llm 基座（GenerationBackend + litellm + rewrite_query 桩）

**Files:**
- Create: `src/snowel_core/llm/backend.py`、`src/snowel_core/llm/ports.py`
- Test: `tests/llm/test_backend.py`

**Interfaces:**
- Consumes: `storage.config`。
- Produces:
  - `llm.backend.GenerationBackend` 协议：`generate(prompt: str, *, model: str | None = None, system: str | None = None) -> str`。
  - `llm.backend.LitellmBackend`：`__init__(default_model: str | None = None)`（缺省读 config `llm.model`）；`generate` 内 `import litellm; litellm.completion(...)` 返回文本。惰性 import——core 环境未装 litellm 时协议仍可独立单测。
  - `llm.ports.rewrite_query(query, context, backend=None)`：v1 恒返回 `None`（§11.3 豁免：未启用时检索为纯确定性代码）。
  - `llm.ports.get_backend(conn) -> GenerationBackend`：读 config `llm.backend`（默认 `"litellm"`），返回 `LitellmBackend`；测试注入路径 = 调用方显式传 `backend=`，不走此工厂。

- [ ] **Step 1: 写失败测试**

```python
# tests/llm/test_backend.py
from snowel_core.llm import backend, ports


def test_rewrite_query_stub_returns_none():  # §11.3 v1 豁免
    assert ports.rewrite_query("林晚", {"sections": []}) is None


def test_litellm_backend_lazy_and_default_model(core_conn, monkeypatch):
    from snowel_core.storage import config
    config.set(core_conn, "llm.model", "gpt-dummy")
    b = backend.LitellmBackend.for_conn(core_conn)
    assert b.default_model == "gpt-dummy"

    calls = {}
    monkeypatch.setattr("litellm.completion",
                        lambda **kw: calls.update(kw) or {
                            "choices": [{"message": {"content": "ok"}}]})
    assert b.generate("你好", model="small-model") == "ok"
    assert calls["model"] == "small-model"        # per-call 模型覆盖（§6.3 成本控制）
```

- [ ] **Step 2: 跑测试确认失败**

- [ ] **Step 3: 最小实现**

```python
# src/snowel_core/llm/backend.py
import sqlite3

from ..storage import config


class GenerationBackend:
    def generate(self, prompt: str, *, model: str | None = None,
                 system: str | None = None) -> str: ...


class LitellmBackend(GenerationBackend):
    """litellm 适配（铁律 2：LLM 调用唯一实现处之一）。惰性 import 供无网测试。"""

    def __init__(self, default_model: str = "gpt-4o-mini"):
        self.default_model = default_model

    @classmethod
    def for_conn(cls, conn: sqlite3.Connection) -> "LitellmBackend":
        return cls(config.get(conn, "llm.model", "gpt-4o-mini"))

    def generate(self, prompt: str, *, model: str | None = None,
                 system: str | None = None) -> str:
        import litellm
        resp = litellm.completion(
            model=model or self.default_model,
            messages=[*([{"role": "system", "content": system}] if system else []),
                      {"role": "user", "content": prompt}])
        return resp["choices"][0]["message"]["content"]
```

```python
# src/snowel_core/llm/ports.py
def rewrite_query(query: str, context: dict, backend=None) -> str | None:
    """检索改写口（E3 可选）：v1 未启用，恒 None（testcases §11.3 豁免）。"""
    return None
```

- [ ] **Step 4: 跑测试通过**：`pytest tests/llm -v`
- [ ] **Step 5: 提交**：`git commit -m "feat(llm): generation backend protocol, litellm adapter and rewrite_query stub"`

---

### Task 8: 抽取管线 extract_and_writeback（§5.3 分级 / 忽略修辞 / L1 接线）

**Files:**
- Create: `src/snowel_core/writeback/extract.py`
- Modify: `src/snowel_core/api.py`（+extract_and_writeback 门面方法）
- Test: `tests/writeback/test_extract.py`

**Interfaces:**
- Consumes: Task 3 `mirror`（读镜像全文）、Task 7 `GenerationBackend`、`groups.validate`（L1 已修）、`proposals.create`、事件 `auto_canonized`（handler 已存在）。
- Produces:
  - `llm.ports.extract_and_writeback(api, chapter_id: str, backend: GenerationBackend, model: str | None = None) -> dict`（三口之一，api 门面同签名代理）：
    1. 读镜像 `chapter_prose.prose`（空镜像 → `ValueError("章节无镜像全文，先对账")`）；
    2. 提示词固定含**忽略修辞判据**（§5.3："比喻、夸张、通感等修辞不构成事实，不得抽取"）与 JSON 返回约定 `{facts: [{sensitivity, fact}], appeared: [节点 id]}`；
    3. 解析响应；**确定性后校**：任一 fact 的 props 值含数字（`re.search(r"\d", json 值串)`）→ 强制 `sensitivity="high"`（分级阈值可配置的 v1 实现：config `extraction.numeric_high=true` 默认开）；
    4. 每个 fact 的 `props` 各组过 `groups.validate`：`unmanaged` 保留并计警告；`version_mismatch`/`invalid` → 该事实**强制 high 进提案**（低敏感自动入典不收校验失败项）；
    5. high facts → `proposals.create("extract_facts", {chapter_id, facts})`；
    6. low facts → 单事务追加**单条** `auto_canonized` 事件（payload `{facts, source: {chapter_id, hash}, appeared}`）+ `projector.apply`（D1 批量控量）；
    7. 返回 `{"chapter_id", "proposal_id": str | None, "auto_event_seq": int | None, "warnings": [str], "appeared": [...]}`。

- [ ] **Step 1: 写失败测试**

```python
# tests/writeback/test_extract.py
import json
from tests.conftest import FakeBackend
from snowel_core.writeback import mirror

EXTRACT_OK = json.dumps({
    "facts": [
        {"sensitivity": "low", "fact": {
            "fact": "node", "id": "n-rule", "types": ["Mechanism"],
            "name": "积分兑换", "props": {"mechanism": {"规则": "一积分换一命"}}}},
        {"sensitivity": "high", "fact": {
            "fact": "node", "id": "n-level", "types": ["Mechanism"],
            "name": "等级提升", "props": {"core": {"level": 3}}}},
        {"sensitivity": "low", "fact": {   # 修辞陷阱：必须被确定性后校转 high（数字）
            "fact": "node", "id": "n-metaphor", "types": ["Concept"],
            "name": "怒吼如高炮弹", "props": {"core": {"分贝": 120}}}},
    ],
    "appeared": ["hero"],
}, ensure_ascii=False)


def _prepare(api, tmp_path):
    from snowel_core.storage import db, events, projector
    with db.transaction(api._conn):
        events.append_event(api._conn, "proposal_confirmed", {
            "artifact_type": "t", "facts": [
                {"fact": "node", "id": "hero", "types": ["Character"],
                 "name": "林晚", "props": {}}]})
        projector.apply(api._conn)
    mirror.write_prose(api._conn, tmp_path, "ch1", "林晚攒积分。")


def test_extract_splits_sensitivity(api, tmp_path):  # TC-WB-06 / TC-PR-10 / D1
    _prepare(api, tmp_path)
    fake = FakeBackend([EXTRACT_OK])
    r = api.extract_and_writeback("ch1", backend=fake)
    # low（规则，无数字）→ 单条 auto_canonized 批量事件
    assert r["auto_event_seq"] is not None
    ev = api._conn.execute(
        "SELECT payload FROM events WHERE kind='auto_canonized'").fetchone()
    p = json.loads(ev["payload"])
    assert [f["id"] for f in p["facts"]] == ["n-rule"]
    assert p["source"] == {"chapter_id": "ch1", "hash": p["source"]["hash"]}
    assert p["appeared"] == ["hero"]
    # high（显式 high + 数字后校转 high）→ 提案队列，不自动入典
    assert r["proposal_id"] is not None
    prop = [dict(x) for x in api.proposals.list("pending")][0]
    ids = [f["id"] for f in json.loads(prop["payload"])["facts"]]
    assert ids == ["n-level", "n-metaphor"]
    # 提示词忽略修辞判据在场
    assert "修辞" in fake.calls[0]["prompt"]


def test_extract_requires_mirror(api, tmp_path):
    import pytest
    with pytest.raises(ValueError, match="镜像"):
        api.extract_and_writeback("ch1", backend=FakeBackend([]))


def test_extract_unmanaged_group_warns(api, tmp_path):  # TC-ON-03 消费面 + L1 接线
    _prepare(api, tmp_path)
    resp = json.dumps({"facts": [
        {"sensitivity": "low", "fact": {
            "fact": "node", "id": "n-x", "types": ["Concept"], "name": "x",
            "props": {"foo": {"any": "thing"}, "_schema_bad": "demo@x"}}}],
        "appeared": []}, ensure_ascii=False)
    r = api.extract_and_writeback("ch1", backend=FakeBackend([resp]))
    assert any("unmanaged" in w for w in r["warnings"])
```

- [ ] **Step 2: 跑测试确认失败**

- [ ] **Step 3: 最小实现**

```python
# src/snowel_core/writeback/extract.py
import json
import re
import sqlite3

from ..llm.backend import GenerationBackend
from ..ontology import groups
from ..storage import config, events, projector
from ..storage.db import transaction

_PROMPT = """你是小说设定抽取器。从下方章节正文中抽取事实。
判据：比喻、夸张、通感等修辞不构成事实，一律忽略（忽略修辞判据）。
只抽取文本明确陈述的内容。返回 JSON：
{{"facts": [{{"sensitivity": "high"|"low", "fact": {{"fact": "node"|"edge", ...}}}}],
 "appeared": ["登场实体已有节点 id，仅正文名词出场，图谱引用不算"]}}
高敏感 = 数字、人名变更、规则、角色生死；低敏感 = 描述性细节。

章节正文：
{prose}"""


def _has_number(fact: dict) -> bool:
    return bool(re.search(r"\d", json.dumps(
        fact.get("props", {}), ensure_ascii=False)))


def _validate_groups(fact: dict) -> list[str]:
    warns = []
    for gname, gval in fact.get("props", {}).items():
        if not isinstance(gval, dict):
            continue
        status, warn = groups.validate(gname, gval)
        if status == "unmanaged":
            warns.append(f"unmanaged 组 {gname} 照存（不参与护栏/级联）")
        elif status != "ok":
            warns.append(warn)
            return warns + ["__FORCE_HIGH__"]
    return warns


def extract_and_writeback(api, chapter_id: str, backend: GenerationBackend,
                          model: str | None = None) -> dict:
    """三口之一（E3）：抽取 → 确认分级（§5.3）→ 提案 / auto 单事件批量入典。"""
    conn: sqlite3.Connection = api._conn
    row = conn.execute(
        "SELECT prose, hash FROM chapter_prose WHERE chapter_id=?",
        (chapter_id,)).fetchone()
    if row is None or not row["prose"]:
        raise ValueError(f"章节 {chapter_id} 无镜像全文，先对账（reconcile）")
    resp = backend.generate(_PROMPT.format(prose=row["prose"]), model=model)
    parsed = json.loads(resp)
    numeric_high = config.get(conn, "extraction.numeric_high", True)

    high, low, warnings, appeared = [], [], list(), parsed.get("appeared", [])
    for item in parsed["facts"]:
        fact = item["fact"]
        sens = item.get("sensitivity", "low")
        gw = _validate_groups(fact)
        if numeric_high and _has_number(fact):
            sens = "high"  # 确定性后校：数字事实强制高敏感（阈值可配置）
        if any(w == "__FORCE_HIGH__" for w in gw):
            sens = "high"  # 校验失败项不自动入典
        warnings.extend(w for w in gw if w != "__FORCE_HIGH__")
        (high if sens == "high" else low).append(fact)

    proposal_id = None
    if high:
        proposal_id = api.proposals.create("extract_facts", {
            "chapter_id": chapter_id, "facts": high})
    auto_seq = None
    if low:
        with transaction(conn):
            auto_seq = events.append_event(conn, "auto_canonized", {
                "facts": low, "source": {"chapter_id": chapter_id,
                                         "hash": row["hash"]},
                "appeared": appeared})
            projector.apply(conn)
    return {"chapter_id": chapter_id, "proposal_id": proposal_id,
            "auto_event_seq": auto_seq, "warnings": warnings,
            "appeared": appeared}
```

```python
# api.py 门面追加（铁律 1：三端唯一入口）
    def extract_and_writeback(self, chapter_id: str, backend, model=None):
        from .llm.ports import extract_and_writeback as _port
        return _port(self, chapter_id, backend, model=model)
```

`llm/ports.py` 中 `extract_and_writeback = re-export`（实现住 writeback/extract.py，口签名住 llm/ports.py，与 design §7 表对齐——ports 内 `from ..writeback.extract import extract_and_writeback`）。

- [ ] **Step 4: 跑测试通过**：`pytest tests/writeback -v`
- [ ] **Step 5: 提交**：`git commit -m "feat(writeback): extraction pipeline with sensitivity split, rhetoric filter and group validation (5.3/D1/L1-wired)"`

---

### Task 9: 确认即写文件编排（C1）

**Files:**
- Modify: `src/snowel_core/api.py`（open/init 存项目根、+confirm_prose）、`src/snowel_core/proposal/queue.py`（+get 公开）
- Test: `tests/writeback/test_confirm_prose.py`

**Interfaces:**
- Consumes: Task 3 `mirror.write_prose`；`ProposalQueue.confirm`。
- Produces:
  - `SnowelAPI.__init__`/`open`/`init_project` 记录 `self._root: Path`（写文件 IO 需要）。
  - `api.confirm(proposal_id: str, exclude: list[str] | None = None) -> int`（统一确认入口，扩展自 proposals.confirm，exclude 见 Task 14）：`proposals` kind == `"prose"` 时，confirm 事务成功后调 `mirror.write_prose(conn, root, payload["chapter_id"], payload["content"])`（C1：核心代写文件+登记哈希），返回事件 seq。
  - `ProposalQueue.get(proposal_id) -> sqlite3.Row`（公开只读）。

- [ ] **Step 1: 写失败测试**

```python
# tests/writeback/test_confirm_prose.py
import json


def test_confirm_prose_writes_file_and_registers_hash(api, tmp_path):  # TC-WB-01
    pid = api.proposals.create("prose", {
        "chapter_id": "ch1", "content": "第一章：雨夜。"})
    seq = api.confirm(pid)
    assert seq > 0
    f = tmp_path / "chapters" / "ch1.md"
    assert f.read_text(encoding="utf-8") == "第一章：雨夜。"
    kinds = [r["kind"] for r in api._conn.execute(
        "SELECT kind FROM events ORDER BY seq")]
    assert kinds == ["proposal_confirmed", "prose_hash_registered"]
    row = api._conn.execute(
        "SELECT status FROM proposals WHERE id=?", (pid,)).fetchone()
    assert row["status"] == "confirmed"


def test_registered_write_shortcircuits_hook(api, tmp_path):  # TC-WB-02
    pid = api.proposals.create("prose", {
        "chapter_id": "ch1", "content": "第一章：雨夜。"})
    api.confirm(pid)
    from snowel_core.writeback import mirror
    assert mirror.reconcile(api._conn, tmp_path) == []  # 已登记写入不视为外部改动
    n = api._conn.execute(
        "SELECT count(*) c FROM events WHERE kind='prose_external_change'"
    ).fetchone()["c"]
    assert n == 0


def test_confirm_non_prose_unchanged(api):  # 回归：非正文提案路径不变
    pid = api.proposals.create("scene", {"facts": [
        {"fact": "node", "id": "sc9", "types": ["Scene"],
         "name": "s", "props": {}}]})
    seq = api.confirm(pid)
    assert seq > 0
    assert api.get_node("sc9") is not None
```

- [ ] **Step 2: 跑测试确认失败**

- [ ] **Step 3: 最小实现**

```python
# api.py
    def __init__(self, conn, root: Path | None = None):
        self._conn = conn
        self._root = root          # 项目根（写文件 IO 用，C1）
        self.proposals = ProposalQueue(conn)

    @classmethod
    def init_project(cls, path) -> "SnowelAPI":
        p = Path(path); p.mkdir(parents=True, exist_ok=True)
        conn = db.connect(p / "snowel.db"); db.migrate(conn)
        return cls(conn, root=p)

    @classmethod
    def open(cls, path) -> "SnowelAPI":
        db_path = Path(path) / "snowel.db"
        if not db_path.exists():
            raise ProjectNotFoundError(f"未找到项目库：{db_path}")
        return cls(db.connect(db_path), root=Path(path))

    def confirm(self, proposal_id: str, exclude: list[str] | None = None) -> int:
        """统一确认入口：正文类提案确认即代写文件并登记哈希（C1）。"""
        p = self.proposals.get(proposal_id)
        seq = self.proposals.confirm(proposal_id, exclude=exclude)
        if p["kind"] == "prose":
            payload = json.loads(p["payload"])
            from .writeback import mirror
            mirror.write_prose(self._conn, self._root,
                               payload["chapter_id"], payload["content"])
        return seq
```

```python
# proposal/queue.py
    def get(self, pid) -> sqlite3.Row:
        return self._get(pid)          # _get 更名公开（api 编排需要）

    def confirm(self, proposal_id: str, exclude: list[str] | None = None) -> int:
        self._transition(proposal_id, "confirmed")
        p = self._get(proposal_id)
        payload = json.loads(p["payload"])
        facts = payload.get("facts", [])
        if exclude:                     # TC-PR-09：整组确认可剔除
            facts = [f for f in facts if f.get("id") not in set(exclude)]
        with transaction(self.conn):
            seq = events.append_event(self.conn, "proposal_confirmed", {
                "proposal_id": proposal_id, "artifact_type": p["kind"],
                "facts": facts})
            projector.apply(self.conn)
            self.conn.execute(
                "UPDATE proposals SET status='confirmed' WHERE id=?", (proposal_id,))
        return seq
```

（本任务先落 exclude 参数与过滤逻辑，Task 14 的微节拍组消费它；现有调用面 `confirm(pid)` 不受影响。）

- [ ] **Step 4: 跑测试通过**：`pytest tests/writeback tests/proposal -v`（proposal 回归确认签名兼容）
- [ ] **Step 5: 提交**：`git commit -m "feat(writeback): confirm-prose writes chapter file and registers hash (C1)"`

---

### Task 10: hook 轮询调度器（三模式，P4）

**Files:**
- Create: `src/snowel_core/writeback/hook.py`
- Modify: `src/snowel_core/api.py`（+reconcile_prose/trigger_extract 门面）
- Test: `tests/writeback/test_hook.py`

**Interfaces:**
- Consumes: Task 3 `mirror.reconcile`、Task 8 `extract_and_writeback`、Task 2 `config`。
- Produces:
  - `writeback.hook.HookScheduler(api, backend, mode: str, interval: float)`：mode ∈ `{"auto", "manual", "timer"}`。`tick() -> list[dict]`（确定性单步：reconcile；auto 模式下对每个 `external_change` 章节调 `api.extract_and_writeback(chapter_id, backend)`，结果并入返回）；`start()/stop()`（daemon 线程按 interval 循环 tick，manual 不启线程）。线程模型同 lease 心跳。
  - `api.reconcile_prose() -> list[dict]`（三模式通用对账门面）；`api.trigger_extract(chapter_id, backend, model=None)`（手动模式显式抽取，§3.3）。
  - 配置键：`hook.mode`（默认 `"manual"`）、`hook.interval`（auto 默认 2.0s、timer 由配置给定）。

- [ ] **Step 1: 写失败测试**

```python
# tests/writeback/test_hook.py
import json
from tests.conftest import FakeBackend
from snowel_core.writeback import hook, mirror

EXTRACT = json.dumps({"facts": [], "appeared": []}, ensure_ascii=False)


def _write_chapter(api, tmp_path, content="正文"):
    mirror.write_prose(api._conn, tmp_path, "ch1", content)


def test_auto_mode_extracts_on_external_change(api, tmp_path):  # TC-WB-03
    _write_chapter(api, tmp_path)
    (tmp_path / "chapters" / "ch1.md").write_text("改后的正文", encoding="utf-8")
    fake = FakeBackend([EXTRACT])
    sch = hook.HookScheduler(api, fake, mode="auto", interval=1.0)
    results = sch.tick()
    assert results == [{
        "chapter_id": "ch1", "status": "external_change",
        "extract": {"chapter_id": "ch1", "proposal_id": None,
                    "auto_event_seq": None}}]
    assert "改后的正文" in fake.calls[0]["prompt"]    # 抽取吃的是新镜像


def test_manual_mode_registers_but_not_extracts(api, tmp_path):  # TC-WB-04 前半
    _write_chapter(api, tmp_path)
    (tmp_path / "chapters" / "ch1.md").write_text("手改", encoding="utf-8")
    fake = FakeBackend([])
    results = hook.HookScheduler(api, fake, "manual", 1.0).tick()
    assert results == [{"chapter_id": "ch1", "status": "external_change"}]
    assert fake.calls == []                          # 不立即抽取
    api.trigger_extract("ch1", backend=fake)         # 作者点击 → 显式抽取
    assert len(fake.calls) == 1


def test_timer_mode_no_thread_until_started(api):
    sch = hook.HookScheduler(api, FakeBackend([]), "timer", 60.0)
    assert sch._renewer is None                      # 未 start 不占线程
    sch.start(); sch.stop()


def test_scheduler_from_config(api):
    from snowel_core.storage import config
    config.set(api._conn, "hook.mode", "auto")
    sch = hook.HookScheduler.from_config(api, FakeBackend([]))
    assert sch.mode == "auto"
```

- [ ] **Step 2: 跑测试确认失败**

- [ ] **Step 3: 最小实现**

```python
# src/snowel_core/writeback/hook.py
import threading

from ..storage import config
from ..writeback import mirror

MODES = ("auto", "manual", "timer")


class HookScheduler:
    """正文同步 hook（§3.3，P4 轮询对账）：auto=改动即抽取（短周期轮询）、
    manual=只登记不抽取（作者显式触发）、timer=按周期抽取。"""

    def __init__(self, api, backend, mode: str, interval: float):
        if mode not in MODES:
            raise ValueError(f"未知 hook 模式：{mode}（可用：{'/'.join(MODES)}）")
        self.api, self.backend, self.mode, self.interval = api, backend, mode, interval
        self._stop = threading.Event()
        self._renewer: threading.Thread | None = None

    @classmethod
    def from_config(cls, api, backend) -> "HookScheduler":
        mode = config.get(api._conn, "hook.mode", "manual")
        default_iv = {"auto": 2.0, "timer": 300.0, "manual": 0.0}[mode]
        return cls(api, backend, mode,
                   config.get(api._conn, "hook.interval", default_iv))

    def tick(self) -> list[dict]:
        out = []
        for ch in mirror.reconcile(self.api._conn, self.api._root):
            if ch["status"] == "external_change" and self.mode in ("auto", "timer"):
                ch["extract"] = self.api.extract_and_writeback(
                    ch["chapter_id"], backend=self.backend)
            out.append(ch)
        return out

    def start(self) -> None:
        if self._renewer is not None or self.interval <= 0:
            return
        def _loop():
            while not self._stop.wait(self.interval):
                self.tick()
        self._renewer = threading.Thread(target=_loop, daemon=True)
        self._renewer.start()

    def stop(self) -> None:
        self._stop.set()
        if self._renewer is not None:
            self._renewer.join(timeout=5)
```

```python
# api.py 门面追加
    def reconcile_prose(self) -> list:
        from .writeback import mirror
        return mirror.reconcile(self._conn, self._root)

    def trigger_extract(self, chapter_id: str, backend, model=None):
        return self.extract_and_writeback(chapter_id, backend, model=model)
```

- [ ] **Step 4: 跑测试通过**：`pytest tests/writeback -v`
- [ ] **Step 5: 提交**：`git commit -m "feat(writeback): polling hook scheduler with auto/manual/timer modes (3.3/P4)"`

---

### Task 11: active 判定 + 偏离报告（D5/L2 接线 + C12）

**Files:**
- Modify: `src/snowel_core/storage/projector.py`（appeared 物化）、`src/snowel_core/writeback/extract.py`（组入 deviation）、Create: `src/snowel_core/writeback/deviation.py`
- Test: `tests/writeback/test_active_and_deviation.py`

**Interfaces:**
- Consumes: Task 8 的 `auto_canonized`/`proposal_confirmed` payload（`appeared` 字段）、镜像 prose。
- Produces:
  - 投影器 `_facts_event` 后追加登场物化（P7）：payload 里 `appeared` 中的节点，若当前 `completeness == "profiled"` → `UPDATE nodes SET completeness='active'`（draft 不跳级）。
  - `writeback.deviation.report(conn, chapter_id: str) -> dict`：`{"microbeat": {"done": n, "total": m}, "missing_elements": [str]}`（P6 判据）。微节拍 = `props.chapter == chapter_id` 的 MicroBeat 节点，`props.keywords`（列表）全部出现在镜像 prose 中计 done；场景卡 `props.required_elements` 同法检缺失。无微节拍/场景卡 → 对应字段为空值 `{"microbeat": None, "missing_elements": []}`。
  - `api.extract_and_writeback` 返回 dict 增加 `"deviation"` 字段（deviation.report 结果），并新增 `api.deviation(chapter_id)` 显式查询。

- [ ] **Step 1: 写失败测试**

```python
# tests/writeback/test_active_and_deviation.py
import json
from tests.conftest import FakeBackend
from snowel_core.storage import db, events, projector
from snowel_core.writeback import deviation, mirror


def _profiled_hero(api):
    with db.transaction(api._conn):
        events.append_event(api._conn, "proposal_confirmed", {
            "artifact_type": "t", "facts": [
                {"fact": "node", "id": "hero", "types": ["Character"],
                 "name": "林晚", "completeness": "profiled",
                 "props": {"core": {"motivation": "a", "lie": "b",
                                    "fear": "c", "arc": "d"}}}]})
        projector.apply(api._conn)


def test_appeared_activates_profiled_only(api):  # TC-ON-06 / P7
    _profiled_hero(api)
    with db.transaction(api._conn):
        events.append_event(api._conn, "auto_canonized", {
            "facts": [], "source": {"chapter_id": "ch1", "hash": "h"},
            "appeared": ["hero"]})
        projector.apply(api._conn)
    assert api.get_node("hero")["completeness"] == "active"


def test_appeared_does_not_skip_draft(api):  # D5 链式：draft 登场仍是 draft
    with db.transaction(api._conn):
        events.append_event(api._conn, "proposal_confirmed", {
            "artifact_type": "t", "facts": [
                {"fact": "node", "id": "hero", "types": ["Character"],
                 "name": "林晚", "props": {}}]})
        events.append_event(api._conn, "auto_canonized", {
            "facts": [], "source": {}, "appeared": ["hero"]})
        projector.apply(api._conn)
    assert api.get_node("hero")["completeness"] == "draft"


def test_deviation_report(api, tmp_path):  # TC-FL-05：4/6 + 缺"雨夜"
    with db.transaction(api._conn):
        events.append_event(api._conn, "proposal_confirmed", {
            "artifact_type": "t", "facts": [
                {"fact": "node", "id": "sc1", "types": ["Scene"], "name": "场景",
                 "props": {"chapter": "ch1", "required_elements": ["雨夜", "电话亭"]}},
                *[{"fact": "node", "id": f"mb{i}", "types": ["MicroBeat"],
                   "name": f"节拍{i}",
                   "props": {"chapter": "ch1",
                             "keywords": ["关键词A"] if i < 4 else ["关键词B"]}}
                  for i in range(6)]})
        projector.apply(api._conn)
    mirror.write_prose(api._conn, tmp_path, "ch1", "关键词A反复出现。")
    r = deviation.report(api._conn, "ch1")
    assert r == {"microbeat": {"done": 4, "total": 6},
                 "missing_elements": ["雨夜", "电话亭"]}


def test_extract_returns_deviation(api, tmp_path):
    _profiled_hero(api)
    mirror.write_prose(api._conn, tmp_path, "ch1", "正文")
    resp = json.dumps({"facts": [], "appeared": ["hero"]}, ensure_ascii=False)
    r = api.extract_and_writeback("ch1", backend=FakeBackend([resp]))
    assert "deviation" in r and r["deviation"]["microbeat"] is None
```

- [ ] **Step 2: 跑测试确认失败**

- [ ] **Step 3: 最小实现**

```python
# projector.py：_facts_event 末尾追加（proposal_confirmed / auto_canonized 共用）
def _facts_event(tx, payload: dict, seq: int):
    for f in payload["facts"]:
        (_upsert_node if f["fact"] == "node" else _upsert_edge)(tx, f, seq)
    for nid in payload.get("appeared", []):  # P7：登场 → active（不跳级）
        row = tx.execute("SELECT completeness FROM nodes WHERE id=?",
                         (nid,)).fetchone()
        if row is not None and row["completeness"] == "profiled":
            tx.execute("UPDATE nodes SET completeness='active' WHERE id=?", (nid,))
```

```python
# src/snowel_core/writeback/deviation.py
import json
import sqlite3


def report(conn: sqlite3.Connection, chapter_id: str) -> dict:
    """C12 轻量偏离报告：确定性比对，零 LLM（P6 判据）。"""
    row = conn.execute("SELECT prose FROM chapter_prose WHERE chapter_id=?",
                       (chapter_id,)).fetchone()
    prose = row["prose"] if row else ""
    beats, scene = [], None
    for r in conn.execute("SELECT * FROM nodes WHERE active=1"):
        props = json.loads(r["props"])
        if props.get("chapter") != chapter_id:
            continue
        if "MicroBeat" in json.loads(r["types"]):
            beats.append(props)
        if "Scene" in json.loads(r["types"]) and scene is None:
            scene = props
    done = sum(1 for b in beats
               if all(k in prose for k in b.get("keywords", [])))
    missing = [e for e in (scene or {}).get("required_elements", [])
               if e not in prose]
    return {"microbeat": {"done": done, "total": len(beats)} if beats else None,
            "missing_elements": missing}
```

`extract.py` 返回 dict 增加 `"deviation": deviation.report(conn, chapter_id)`；`api.py` 增加 `deviation(chapter_id)` 门面。

- [ ] **Step 4: 跑测试通过**：`pytest tests/writeback tests/storage -v`
- [ ] **Step 5: 提交**：`git commit -m "feat(writeback): appeared-activates-profiled projection (D5/L2) and deviation report (C12)"`

---

### Task 12: auto 条目事后否决 + 轻量反查（C2/C11）

**Files:**
- Create: `src/snowel_core/writeback/review.py`
- Modify: `src/snowel_core/api.py`（+list_auto/reject_auto 门面）
- Test: `tests/writeback/test_review.py`

**Interfaces:**
- Consumes: 事件 `auto_canonized`（枚举事实）、`retraction`（handler 已存在）、Task 4 `fts.search`（prose 反查）。
- Produces:
  - `writeback.review.list_auto(conn) -> list[dict]`：遍历 `auto_canonized` 事件 payload，展开 facts 为 `[{event_seq, fact_id, kind: "node"|"edge", name_or_id, source_chapter}]`；已被 retraction 的目标（nodes.active=0 / edges.valid_until=-1）标 `"retracted": true`。
  - `writeback.review.reject_auto(conn, entries: list[tuple[str, str]], reason: str | None = None) -> dict`：entries = `(target, target_id)` 列表（target ∈ node/edge）；单事务逐条追加 `retraction` 事件 `{target, target_id, reason, source: "auto_review"}` + apply；返回 `{"retracted": n, "referencing_paragraphs": [...]}`。
  - **轻量反查**（TC-WB-07）：对每条被否目标按节点 name 做 `fts.search(conn, name)`，收集 `paragraphs` 作为"哪些正文段落引用过它"提示——不自动改正文；**不受冻结线约束**（C11：auto 否决=纠正抽取错误；封卷机制在级联检查计划，当前天然无约束，函数 docstring 注明该语义）。
  - `api.list_auto()` / `api.reject_auto(entries, reason=None)` 门面。

- [ ] **Step 1: 写失败测试**

```python
# tests/writeback/test_review.py
import json
from snowel_core.storage import db, events, projector
from snowel_core.writeback import mirror, review


def _auto_rule(api, tmp_path):
    with db.transaction(api._conn):
        events.append_event(api._conn, "auto_canonized", {
            "facts": [{"fact": "node", "id": "n-rule", "types": ["Mechanism"],
                       "name": "一命换积分", "props": {}}],
            "source": {"chapter_id": "ch1", "hash": "h"}, "appeared": []})
        projector.apply(api._conn)
    mirror.write_prose(api._conn, tmp_path, "ch1",
                       "规则很简单。\n\n林晚想起点数：一命换积分。")
    api._conn.execute("UPDATE chapter_prose SET prose=? WHERE chapter_id='ch1'",
                      ("规则很简单。\n\n林晚想起点数：一命换积分。",))
    from snowel_core.storage import fts
    fts.refresh(api._conn)


def test_list_auto_marks_retracted(api, tmp_path):  # TC-WB-07 前置
    _auto_rule(api, tmp_path)
    items = review.list_auto(api._conn)
    assert items == [{"event_seq": 1, "fact_id": "n-rule", "kind": "node",
                      "name_or_id": "一命换积分", "source_chapter": "ch1",
                      "retracted": False}]
    review.reject_auto(api._conn, [("node", "n-rule")], reason="抽取错了")
    items = review.list_auto(api._conn)
    assert items[0]["retracted"] is True


def test_reject_auto_retracts_and_reports_references(api, tmp_path):  # TC-WB-07
    _auto_rule(api, tmp_path)
    r = review.reject_auto(api._conn, [("node", "n-rule")])
    assert r["retracted"] == 1
    assert api.get_node("n-rule")["active"] == 0          # 物化图立即失效（C2）
    ev = api._conn.execute(
        "SELECT payload FROM events WHERE kind='retraction'").fetchone()
    p = json.loads(ev["payload"])
    assert p["target"] == "node" and p["target_id"] == "n-rule"
    assert p["reason"] == "抽取错了"
    assert r["referencing_paragraphs"] and \
        r["referencing_paragraphs"][0]["chapter_id"] == "ch1"  # 引用提示，不改文
```

- [ ] **Step 2: 跑测试确认失败**

- [ ] **Step 3: 最小实现**

```python
# src/snowel_core/writeback/review.py
import json
import sqlite3

from ..storage import events, fts, projector
from ..storage.db import transaction


def list_auto(conn: sqlite3.Connection) -> list[dict]:
    out = []
    for ev in conn.execute(
            "SELECT seq, payload FROM events WHERE kind='auto_canonized' "
            "ORDER BY seq"):
        p = json.loads(ev["payload"])
        for f in p["facts"]:
            if f["fact"] == "node":
                row = conn.execute(
                    "SELECT name, active FROM nodes WHERE id=?",
                    (f["id"],)).fetchone()
                retracted = row is None or row["active"] == 0
                name_or_id = row["name"] if row else f["id"]
            else:
                row = conn.execute(
                    "SELECT valid_until FROM edges WHERE id=?", (f["id"],)).fetchone()
                retracted = row is None or row["valid_until"] == -1
                name_or_id = f["id"]
            out.append({"event_seq": ev["seq"], "fact_id": f["id"],
                        "kind": f["fact"], "name_or_id": name_or_id,
                        "source_chapter": p.get("source", {}).get("chapter_id"),
                        "retracted": retracted})
    return out


def reject_auto(conn: sqlite3.Connection, entries: list[tuple[str, str]],
                reason: str | None = None) -> dict:
    """auto 否决 = 纠正抽取错误（C11）：不受封卷冻结线约束，任何时候可否决；
    轻量反查只提示引用段落，不自动改正文（C2）。全量级联由级联检查计划承接。"""
    paragraphs = []
    with transaction(conn):
        for target, target_id in entries:
            events.append_event(conn, "retraction", {
                "target": target, "target_id": target_id,
                "reason": reason, "source": "auto_review"})
            if target == "node":
                row = conn.execute("SELECT name FROM nodes WHERE id=?",
                                   (target_id,)).fetchone()
                if row is not None:
                    paragraphs += fts.search(conn, row["name"])["paragraphs"]
        projector.apply(conn)
    return {"retracted": len(entries), "referencing_paragraphs": paragraphs}
```

- [ ] **Step 4: 跑测试通过**：`pytest tests/writeback -v`
- [ ] **Step 5: 提交**：`git commit -m "feat(writeback): auto-entry review with batch retraction and fts reference hints (C2/C11)"`

---

### Task 13: flow 状态模型 + status 接线（TC-FL-03）

**Files:**
- Create: `src/snowel_core/flow/__init__.py`、`src/snowel_core/flow/state.py`
- Modify: `src/snowel_core/api.py`（+flow_state）、`shell/src/snowel/mcp_server.py`（status.flow）、`shell/src/snowel/cli.py`（status 流程行）
- Test: `tests/flow/test_state.py`

**Interfaces:**
- Consumes: `proposals.list`、nodes 表（Volume/Chapter 结构）。
- Produces:
  - `flow.state.flow_state(conn) -> dict`：`{"layers": {<layer>: "done"|"todo"}, "current_layer": str, "volumes": [{"id", "name", "chapters": [{"id", "name"}]}]}`。层序 = `["premise", "synopsis", "summary", "beat_sheet", "characters", "scenes", "prose"]`；done 判定 = 存在该 `artifact_type` 的 confirmed 提案；current_layer = 第一个 todo 层。卷章树 = types 含 Volume/Chapter 的 active 节点（Chapter 挂 `props.volume`）。未展开卷的场景卡不存在也不报缺（TC-FL-03：只报存在物）。
  - `api.flow_state()`；MCP `snowel_status` 的 `"flow"` 从 `_not_wired` 换为 `ctx.api.flow_state()`；CLI status 末行改 `流程：{current_layer}（{done_n}/7 层完成）`。
  - `queries.graph_stats` 增加 `"active_nodes"` 键（active=1 计数，随行小项：生效图分列）。

- [ ] **Step 1: 写失败测试**

```python
# tests/flow/test_state.py
from snowel_core.flow import state


def test_flow_state_layers_and_tree(api):
    api.proposals.create("premise", {"draft": "x"})
    pid = api.proposals.list("pending")[0]["id"]
    api.confirm(pid)                                     # premise done
    from snowel_core.storage import db, events, projector
    with db.transaction(api._conn):
        events.append_event(api._conn, "proposal_confirmed", {
            "artifact_type": "structure", "facts": [
                {"fact": "node", "id": "v1", "types": ["Volume"],
                 "name": "卷一", "props": {}},
                {"fact": "node", "id": "c1", "types": ["Chapter"],
                 "name": "第1章", "props": {"volume": "v1"}}]})
        projector.apply(api._conn)
    s = state.flow_state(api._conn)
    assert s["layers"]["premise"] == "done"
    assert s["layers"]["synopsis"] == "todo"
    assert s["current_layer"] == "synopsis"
    assert s["volumes"] == [{"id": "v1", "name": "卷一",
                             "chapters": [{"id": "c1", "name": "第1章"}]}]
    assert api.graph_stats()["active_nodes"] == 2
```

```python
# tests/shell/test_mcp_server.py 追加（async 测试沿 _connected/_call 既有构造）
async def test_status_reports_flow(project):
    api = SnowelAPI.open(project)
    pid = api.proposals.create("premise", {"draft": "x"})
    api.proposals.confirm(pid)
    api.close()
    async with _connected(project) as (ctx, client):
        d = await _call(client, "snowel_status", {})
        assert d["flow"]["layers"]["premise"] == "done"
        assert d["flow"]["current_layer"] == "synopsis"
```

**既有测试改造（本任务内）**：`test_status_reports_graph_and_proposals` 末尾 `_assert_not_wired(d["flow"], "flow")` 改为 `assert d["flow"]["layers"]`；`tests/shell/test_cli.py::test_status_reports_counts` 无流程断言不受影响，CLI 末行断言在该测试追加 `assert "流程" in res.output`。

- [ ] **Step 2: 跑测试确认失败**

- [ ] **Step 3: 最小实现**

```python
# src/snowel_core/flow/state.py
import json
import sqlite3

LAYERS = ["premise", "synopsis", "summary", "beat_sheet",
          "characters", "scenes", "prose"]


def flow_state(conn: sqlite3.Connection) -> dict:
    done_kinds = {r["kind"] for r in conn.execute(
        "SELECT DISTINCT p.kind FROM proposals p WHERE p.status='confirmed'")}
    layers = {k: ("done" if k in done_kinds else "todo") for k in LAYERS}
    volumes = []
    for v in conn.execute(
            "SELECT id, name, props FROM nodes WHERE active=1"):
        types = json.loads(v["types"])
        if "Volume" in types:
            volumes.append({"id": v["id"], "name": v["name"], "chapters": []})
    for c in conn.execute(
            "SELECT id, name, props FROM nodes WHERE active=1"):
        props = json.loads(c["props"])
        if "Chapter" not in json.loads(c["types"]):
            continue
        for v in volumes:
            if v["id"] == props.get("volume"):
                v["chapters"].append({"id": c["id"], "name": c["name"]})
    current = next((k for k in LAYERS if layers[k] == "todo"), None)
    return {"layers": layers, "current_layer": current, "volumes": volumes}
```

`queries.graph_stats` 返回加 `"active_nodes": conn.execute("SELECT count(*) c FROM nodes WHERE active=1").fetchone()["c"]`；MCP `snowel_status` 的 `"flow": ctx.api.flow_state()`；CLI status 末行替换为 `typer.echo(f"流程：{s['current_layer'] or '全部完成'}（{done}/7 层完成）")`。

- [ ] **Step 4: 跑测试通过**：`pytest tests/flow tests/shell -v`
- [ ] **Step 5: 提交**：`git commit -m "feat(flow): flow state model wired into mcp/cli status (FL-03) + active graph stats"`

---

### Task 14: ai_generate 生成环（E3 编排 / D7 注入 / 微节拍组）

**Files:**
- Create: `src/snowel_core/flow/registry.py`、`src/snowel_core/flow/generate.py`
- Modify: `src/snowel_core/api.py`（+ai_generate）
- Test: `tests/flow/test_generate.py`

**Interfaces:**
- Consumes: Task 6 `compose_context`、Task 7 `GenerationBackend`、Task 9 `confirm(exclude)`。
- Produces:
  - `flow.registry.ARTIFACTS: dict[str, dict]`：每型 `{"layer": int, "strategy": "prose"|"character"|"generic", "template": str}`。v1 注册：`premise/synopsis/summary/beat_sheet/characters/scene/prose/microbeat_group/chapter_intent/volume_theme/volume_acts`。模板统一要求返回 JSON `{"draft": str, "facts": [...], "appeared": [...]}`（结构产物 facts 必填；prose 型 facts 空、draft=正文）。
  - `flow.generate.ai_generate(api, artifact_type: str, locate: dict | None = None, extra: dict | None = None, backend=None) -> str`（返回 proposal_id，E3 铁律：产出永不直接落正典）：
    1. `spec = ARTIFACTS[artifact_type]`（未知型 ValueError）；
    2. 内部固定第一步 `compose_context(conn, spec["strategy"], locate)`（E3，审计自动全覆盖）；
    3. 提示词 = 模板 + 上下文 sections 文本 + **D7 注入**（`rejected_digest(api)`：近 10 条 rejected 提案的 kind+draft 截断 80 字，防重复提案）+ extra.notes；
    4. `backend.generate(..., model=extra.get("model"))`（per-call 小模型路由，§6.3）；
    5. 解析 JSON → `proposals.create(artifact_type, {locate, draft, facts, appeared})` → 返回 pid。pending 入库（TC-PR-01 面向已有队列复用）。
  - `api.ai_generate(artifact_type, locate=None, extra=None, backend=None)` 门面。**门面与壳不暴露任何直接返回生成文本的路径**（TC-RT-04：无裸生成）。
  - 微节拍组确认（TC-PR-09）：`kind == "microbeat_group"` 提案 `api.confirm(pid, exclude=[...])`（Task 9 已支持 exclude）；壳层在 writeback/generate 面板返回 `{"proposal_id", "exclude_hint": "confirm 可传 exclude 剔除若干微节拍"}`。

- [ ] **Step 1: 写失败测试**

```python
# tests/flow/test_generate.py
import json
from tests.conftest import FakeBackend
from snowel_core.flow import generate


def _gen_resp(facts=None, draft="生成稿"):
    return json.dumps({"draft": draft, "facts": facts or [],
                       "appeared": []}, ensure_ascii=False)


def test_ai_generate_composes_audits_and_proposes(api):  # E3 / TC-RT-04
    fake = FakeBackend([_gen_resp()])
    pid = api.ai_generate("premise", extra={"notes": "无限流"},
                          backend=fake)
    assert api.proposals.get(pid)["status"] == "pending"   # 永不直接落正典
    from snowel_core.retrieval import audit
    assert audit.recent(api._conn)[0]["strategy"] == "generic"  # 内部第一步可观察
    assert "无限流" in fake.calls[0]["prompt"]


def test_ai_generate_rejects_unknown_type(api):
    import pytest
    with pytest.raises(ValueError, match="premise"):
        api.ai_generate("nope", backend=FakeBackend([]))


def test_rejected_digest_injected(api):  # TC-PR-08 / D7
    p1 = api.proposals.create("premise", {"draft": "角色A习得技能S"})
    api.proposals.reject(p1, reason="重复")
    fake = FakeBackend([_gen_resp()])
    api.ai_generate("premise", backend=fake)
    assert "角色A习得技能S" in fake.calls[0]["prompt"]   # 近期被否摘要进提示词


def test_microbeat_group_confirm_with_exclude(api):  # TC-PR-09 / C3
    facts = [{"fact": "node", "id": f"mb{i}", "types": ["MicroBeat"],
              "name": f"拍{i}", "props": {"chapter": "ch1",
                                          "keywords": [f"k{i}"]}}
             for i in range(3)]
    fake = FakeBackend([_gen_resp(facts)])
    pid = api.ai_generate("microbeat_group",
                          locate={"chapter": "ch1"}, backend=fake)
    api.confirm(pid, exclude=["mb1"])                     # 整组确认，剔除 mb1
    ids = {r["id"] for r in api._conn.execute("SELECT id FROM nodes")}
    assert ids == {"mb0", "mb2"}
```

- [ ] **Step 2: 跑测试确认失败**

- [ ] **Step 3: 最小实现**

```python
# src/snowel_core/flow/registry.py
ARTIFACTS = {
    "premise":        {"layer": 1, "strategy": "generic",   "template": "写一句话灵感前提。"},
    "synopsis":       {"layer": 1, "strategy": "generic",   "template": "扩展为一段梗概。"},
    "summary":        {"layer": 2, "strategy": "generic",   "template": "写摘要页。"},
    "beat_sheet":     {"layer": 3, "strategy": "generic",   "template": "写节拍表。"},
    "characters":     {"layer": 4, "strategy": "character", "template": "生成角色档案。"},
    "scene":          {"layer": 4, "strategy": "generic",   "template": "生成场景卡（含 required_elements、characters）。"},
    "prose":          {"layer": 5, "strategy": "prose",     "template": "写本章正文。"},
    "microbeat_group": {"layer": 5, "strategy": "prose",    "template": "产本章 3-6 个微节拍（props 含 keywords）。"},
    "chapter_intent": {"layer": 5, "strategy": "prose",     "template": "一句话本章意图。"},
    "volume_theme":   {"layer": 0, "strategy": "generic",   "template": "卷级主题。"},
    "volume_acts":    {"layer": 0, "strategy": "generic",   "template": "卷级三幕。"},
}
```

```python
# src/snowel_core/flow/generate.py
import json

from ..retrieval.context import compose_context
from .registry import ARTIFACTS

RETURN_CONTRACT = (
    '返回 JSON：{"draft": str, "facts": [节点/边事实数组], "appeared": [id]}')


def rejected_digest(conn, limit: int = 10) -> str:  # D7：被否提案防重复注入
    rows = conn.execute(
        "SELECT kind, payload FROM proposals WHERE status='rejected' "
        "ORDER BY created_ts DESC LIMIT ?", (limit,)).fetchall()
    if not rows:
        return "（无近期被否提案）"
    return "\n".join(
        f"- [{r['kind']}] {json.loads(r['payload']).get('draft', '')[:80]}"
        for r in rows)


def ai_generate(api, artifact_type: str, locate: dict | None = None,
                extra: dict | None = None, backend=None) -> str:
    """三口之一（E3）：内部固定第一步 compose_context；产出必进提案队列。"""
    if artifact_type not in ARTIFACTS:
        raise ValueError(f"未知产物类型 {artifact_type}（可用：{sorted(ARTIFACTS)}）")
    extra = extra or {}
    backend = backend or _default_backend(api._conn)
    spec = ARTIFACTS[artifact_type]
    bundle = compose_context(api._conn, spec["strategy"], locate)  # 审计自动覆盖
    prompt = "\n".join([
        spec["template"], RETURN_CONTRACT,
        "=== 上下文 ===",
        "\n".join(s["text"] for s in bundle["sections"]),
        "=== 近期被否提案（勿重复提出） ===", rejected_digest(api._conn),
        *( [f"=== 作者附言 ===\n{extra['notes']}"] if extra.get("notes") else [] ),
    ])
    resp = backend.generate(prompt, model=extra.get("model"))
    parsed = json.loads(resp)
    return api.proposals.create(artifact_type, {
        "locate": locate or {}, "draft": parsed.get("draft", ""),
        "facts": parsed.get("facts", []),
        "appeared": parsed.get("appeared", [])})


def _default_backend(conn):
    from ..llm.backend import LitellmBackend
    return LitellmBackend.for_conn(conn)
```

（api 门面 `ai_generate(artifact_type, locate=None, extra=None, backend=None)` 代理，显式收 `backend` 参数供壳与测试注入。）

- [ ] **Step 4: 跑测试通过**：`pytest tests/flow -v`
- [ ] **Step 5: 提交**：`git commit -m "feat(flow): ai_generate port with internal compose, rejected-digest injection and microbeat-group confirm (E3/D7/C3)"`

---

### Task 15: 小雪花章级展开（TC-FL-04 + 偏离挂点）

**Files:**
- Create: `src/snowel_core/flow/snowflake.py`
- Modify: `src/snowel_core/api.py`（+expand_chapter/+deviation）
- Test: `tests/flow/test_snowflake.py`

**Interfaces:**
- Consumes: Task 14 `ai_generate`、Task 11 `deviation.report`、Task 9 `confirm`。
- Produces:
  - `flow.snowflake.expand_chapter(api, chapter_id: str, backend, extra: dict | None = None) -> list[str]`：按序产三个提案（只产提案不自动确认，§5.1 受限展开）——`chapter_intent`（L1'）→ `microbeat_group`（L2'，locate 含 `{"chapter": chapter_id}`）→ `prose`（L5'，同一 locate）。**受限展开证据**：prose 的 compose 上下文 sections 已含既有角色档案（strategy=prose 拉取），模板不含"生成角色档案"指令——断言 prompt 含档案文本且不含"生成角色"字样（TC-FL-04）。
  - `api.deviation(chapter_id) -> dict`（偏离报告显式查询，附本章确认面板的数据源，C12）。
  - 编排返回 `[pid_intent, pid_microbeats, pid_prose]`。

- [ ] **Step 1: 写失败测试**

```python
# tests/flow/test_snowflake.py
import json
from tests.conftest import FakeBackend
from snowel_core.flow import snowflake
from snowel_core.storage import db, events, projector


def _seed_profiled_hero(api):
    with db.transaction(api._conn):
        events.append_event(api._conn, "proposal_confirmed", {
            "artifact_type": "characters", "facts": [
                {"fact": "node", "id": "hero", "types": ["Character"],
                 "name": "林晚", "completeness": "profiled",
                 "props": {"core": {"motivation": "活下来", "lie": "没人救",
                                    "fear": "深渊", "arc": "信任"}}},
                {"fact": "node", "id": "sc1", "types": ["Scene"], "name": "雨夜",
                 "props": {"chapter": "ch1", "characters": ["hero"],
                           "required_elements": ["雨夜"]}}]})
        projector.apply(api._conn)


def _resp(draft):
    return json.dumps({"draft": draft, "facts": [], "appeared": []},
                      ensure_ascii=False)


def test_expand_chapter_reuses_profile_facts(api):  # TC-FL-04：受限展开
    _seed_profiled_hero(api)
    fake = FakeBackend([_resp("意图"), _resp("微节拍组"), _resp("正文")])
    pids = api.expand_chapter("ch1", backend=fake)
    assert len(pids) == 3
    kinds = [api.proposals.get(p)["kind"] for p in pids]
    assert kinds == ["chapter_intent", "microbeat_group", "prose"]
    prose_prompt = fake.calls[2]["prompt"]
    assert "活下来" in prose_prompt            # 档案直接拉取复用（现成，不重新生成）
    assert "生成角色档案" not in prose_prompt


def test_deviation_attached_after_prose_confirm(api, tmp_path):  # C12 数据流闭环
    _seed_profiled_hero(api)
    facts = [{"fact": "node", "id": "mb0", "types": ["MicroBeat"],
              "name": "拍0", "props": {"chapter": "ch1", "keywords": ["雨夜"]}}]
    fake = FakeBackend([_resp("i"), json.dumps(
        {"draft": "组", "facts": facts, "appeared": []}, ensure_ascii=False),
        _resp("正文")])
    pids = api.expand_chapter("ch1", backend=fake)
    api.confirm(pids[1])                          # 微节拍组确认
    from snowel_core.writeback import mirror
    mirror.write_prose(api._conn, tmp_path, "ch1", "干燥的白天。")
    r = api.deviation("ch1")
    assert r == {"microbeat": {"done": 0, "total": 1},
                 "missing_elements": ["雨夜"]}
```

- [ ] **Step 2: 跑测试确认失败**

- [ ] **Step 3: 最小实现**

```python
# src/snowel_core/flow/snowflake.py
from .generate import ai_generate


def expand_chapter(api, chapter_id: str, backend, extra: dict | None = None):
    """小雪花 = 受限展开（§5.1）：档案现成直接拉取，只产提案不自动确认。"""
    locate = {"chapter": chapter_id}
    return [
        ai_generate(api, "chapter_intent", locate, extra, backend),
        ai_generate(api, "microbeat_group", locate, extra, backend),
        ai_generate(api, "prose", locate, extra, backend),
    ]
```

`api.py`：`expand_chapter` / `deviation(chapter_id)`（代理 `writeback.deviation.report`）。

- [ ] **Step 4: 跑测试通过**：`pytest tests/flow -v`
- [ ] **Step 5: 提交**：`git commit -m "feat(flow): small-snowflake chapter expansion reusing profile and deviation hookup (FL-04/C12)"`

---

### Task 16: 卷级展开与卷首世界状态重放（C8/C9）

**Files:**
- Modify: `src/snowel_core/flow/snowflake.py`（追加）、`src/snowel_core/api.py`（+volume_start_state/+expand_volume）
- Test: `tests/flow/test_volume.py`

**Interfaces:**
- Consumes: `queries.state_at`（C9 修正后视角）、Task 14 `ai_generate`。
- Produces:
  - `flow.snowflake.volume_start_state(conn, volume_id: str) -> dict`：上一卷末拍 = 该卷之前所有卷中 Chapter/MicroBeat 节点 story_order 最大值（无前卷 → 0）；`state_at(end)` 派生 `{"story_order": end, "alive": [name...], "dead": [name...], "mechanisms": [{name, level}], "open_foreshadows": [name...]}`（机制等级取扁平 `mechanism_level`/`core_level` 字段当前生效版；未回收伏笔 = Foreshadow 节点无 `payoff_beat` 或 payoff > end）。**不落快照**（C8：实时重放推导）。
  - `flow.snowflake.expand_volume(api, volume_id: str, backend, extra=None) -> list[str]`：`volume_theme` → `volume_acts` 两提案（locate 带 `volume_start_state` 结果，供卷级上下文；场景卡滚动展开按章由 expand_chapter 承担，不在本函数循环）。

- [ ] **Step 1: 写失败测试**

```python
# tests/flow/test_volume.py
import json
from tests.conftest import FakeBackend
from snowel_core.flow import snowflake
from snowel_core.storage import db, events, projector


def _seed_v1(api):
    """卷一：英雄存活升级、队友死亡、伏笔未回收。"""
    facts = [
        {"fact": "node", "id": "v1", "types": ["Volume"], "name": "卷一",
         "props": {}},
        {"fact": "node", "id": "v2", "types": ["Volume"], "name": "卷二",
         "props": {}},
        {"fact": "node", "id": "hero", "types": ["Character"], "name": "林晚",
         "props": {"core": {"level": 1}}},
        {"fact": "node", "id": "mate", "types": ["Character"], "name": "旧队友",
         "props": {"core": {"death_beat": "mb9"}}},
        {"fact": "node", "id": "mb9", "types": ["MicroBeat"], "name": "终拍",
         "props": {"address": {"volume": 1, "chapter": 9, "scene": 1, "beat": 1}}},
        {"fact": "node", "id": "mech", "types": ["Mechanism"], "name": "积分兑换",
         "props": {"mechanism": {"level": 1}}},
        {"fact": "node", "id": "fs1", "types": ["Foreshadow"], "name": "怀表",
         "props": {}},
    ]
    with db.transaction(api._conn):
        events.append_event(api._conn, "proposal_confirmed", {
            "artifact_type": "t", "facts": facts})
        events.append_event(api._conn, "proposal_confirmed", {
            "artifact_type": "retcon", "facts": [   # C9：等级 retcon 到 9
                {"fact": "node", "id": "mech", "types": ["Mechanism"],
                 "name": "积分兑换", "props": {"mechanism": {"level": 9}}}]})
        projector.apply(api._conn)


def test_volume_start_state_replays(api):  # TC-FL-01 / TC-FL-02 / C8 / C9
    _seed_v1(api)
    s = api.volume_start_state("v2")
    assert "林晚" in s["alive"] and "旧队友" in s["dead"]   # 死者不在场
    assert s["mechanisms"] == [{"name": "积分兑换", "level": 9}]  # 取升级后（修正版）
    assert s["open_foreshadows"] == ["怀表"]


def test_expand_volume_feeds_start_state(api):  # 卷首状态进卷级上下文
    _seed_v1(api)
    fake = FakeBackend([json.dumps({"draft": "主题", "facts": [], "appeared": []}),
                        json.dumps({"draft": "三幕", "facts": [], "appeared": []})])
    pids = api.expand_volume("v2", backend=fake)
    assert [api.proposals.get(p)["kind"] for p in pids] == ["volume_theme",
                                                            "volume_acts"]
    assert "积分兑换" in fake.calls[0]["prompt"]     # 世界状态注入卷级生成
    assert "旧队友" not in fake.calls[0]["prompt"] or "dead" in fake.calls[0]["prompt"]
```

- [ ] **Step 2: 跑测试确认失败**

- [ ] **Step 3: 最小实现**

```python
# snowflake.py 追加
def volume_start_state(conn, volume_id: str) -> dict:
    """C8：卷首世界状态实时重放（不落快照）；C9：事实取当前生效版。"""
    import json as _json
    from ..storage import queries
    end = 0
    for r in conn.execute("SELECT id, props, types FROM nodes WHERE active=1"):
        if "MicroBeat" in _json.loads(r["types"]):
            end = max(end, r["story_order"] or 0)
    s = queries.state_at(conn, end)
    alive, mechs, foreshadows = [], [], []
    for n in s["nodes"]:  # state_at 已滤死亡角色：alive/mechanism/伏笔取当前生效集
        types = _json.loads(n["types"])
        if "Character" in types:
            alive.append(n["name"])
        if "Mechanism" in types:
            mechs.append({"name": n["name"],
                          "level": n.get("mechanism_level",
                                         n.get("core_level"))})
        if "Foreshadow" in types:
            foreshadows.append(n["name"])
    dead = []  # 死亡名单：state_at 过滤掉的人，从全量图按 death_beat 单独推导
    for r in conn.execute("SELECT name, props FROM nodes WHERE active=1"):
        props = _json.loads(r["props"])
        death = props.get("core", {}).get("death_beat")
        if death is None:
            continue
        d = queries.get_node(conn, death)
        if d is not None and d["story_order"] is not None \
                and d["story_order"] <= end:
            dead.append(r["name"])
    return {"story_order": end, "alive": alive, "dead": dead,
            "mechanisms": mechs, "open_foreshadows": foreshadows}


def expand_volume(api, volume_id: str, backend, extra: dict | None = None):
    start = volume_start_state(api._conn, volume_id)
    locate = {"volume": volume_id, "start_state": start}
    return [ai_generate(api, "volume_theme", locate, extra, backend),
            ai_generate(api, "volume_acts", locate, extra, backend)]
```

注意 `state_at` 已按 C9 取当前生效版（flatten 键 `core_level`/`<组>_level`，见 core ledger Task 6 裁决）；`volume_theme`/`volume_acts` 的 strategy 为 generic，卷首世界状态经 `locate.start_state` 注入提示词（`ai_generate` 的模板+上下文不含 start_state 序列化——执行时在 `ai_generate` prompt 组装中追加 `=== 卷首世界状态 ===\n{json(locate['start_state'])}` 分支，当 locate 含该键时）。

- [ ] **Step 4: 跑测试通过**：`pytest tests/flow -v`
- [ ] **Step 5: 提交**：`git commit -m "feat(flow): volume start-state replay and volume expansion (C8/C9/FL-01/02)"`

---

### Task 17: 统一 revision 流程 + 提案改写（TC-FL-06 / D7 rewrite）

**Files:**
- Create: `src/snowel_core/flow/revision.py`
- Modify: `src/snowel_core/api.py`（+propose_revision/+rewrite_proposal）
- Test: `tests/flow/test_revision.py`

**Interfaces:**
- Consumes: `proposals.create/confirm`、事件 `revision_applied`（物化已有：move + recompute_story_order）、Task 14 backend。
- Produces:
  - `flow.revision.propose_revision(api, node_id: str, new_address: dict, reason: str = "") -> str`：`kind="revision"` 提案，payload `{node_id, structure_changes: [{"op": "move", "node_id", "address"}], reason}`。
  - `api.confirm` 对 `kind == "revision"`：confirm 后结果附 `"cascade": {"wired": False, "planned_in": "级联检查计划"}`（级联影响分析位空挂点，§5.2 流程占位；级联引擎 E5 归级联检查计划）。`revision_applied` 事件在 confirm 事务内追加（payload 即 structure_changes + `affected_range` 省略——派生序区间由 recompute 全量维护，事件记结构变更本身）。
  - **C5 stale 自动触发（revision 面）**：revision 确认事务后，将全部 pending 提案 `mark_stale(pid, hint="上游 revision：{node_id} 结构变更")`（v1 保守全标——"受影响"的依赖图分析归级联检查计划，豁免登记）；retcon 触发面同样留级联计划。
  - `flow.revision.rewrite_proposal(api, proposal_id: str, instruction: str, backend) -> str`：取原提案 payload，提示词 = 原草稿 + 修改指示 → 新提案（kind 同源、payload 标 `rewritten_from`），原提案留队不动（作者自行否决旧的）。
  - 三层（书/卷/章）同一入口：new_address 结构地址即层间移动表达（§5.2 一次实现三层复用）。

- [ ] **Step 1: 写失败测试**

```python
# tests/flow/test_revision.py
import json
from tests.conftest import FakeBackend
from snowel_core.flow import revision
from snowel_core.storage import db, events, projector


def _seed_two_volumes(api):
    with db.transaction(api._conn):
        events.append_event(api._conn, "proposal_confirmed", {
            "artifact_type": "structure", "facts": [
                {"fact": "node", "id": "v1", "types": ["Volume"], "name": "卷一",
                 "props": {}},
                {"fact": "node", "id": "v2", "types": ["Volume"], "name": "卷二",
                 "props": {}},
                {"fact": "node", "id": "c5", "types": ["Chapter"], "name": "第5章",
                 "props": {"volume": "v2",
                           "address": {"volume": 2, "chapter": 1,
                                       "scene": 0, "beat": 0}}},
                {"fact": "node", "id": "c9", "types": ["Chapter"], "name": "第9章",
                 "props": {"volume": "v2",
                           "address": {"volume": 2, "chapter": 2,
                                       "scene": 0, "beat": 0}}}]})
        projector.apply(api._conn)


def test_revision_unified_flow(api):  # TC-FL-06：章改卷走统一提案→确认
    _seed_two_volumes(api)
    pid = api.propose_revision("c5", {"volume": 1, "chapter": 9,
                                      "scene": 0, "beat": 0}, reason="章改卷")
    assert api.proposals.get(pid)["kind"] == "revision"
    seq = api.confirm(pid)
    ev = api._conn.execute(
        "SELECT payload FROM events WHERE kind='revision_applied'").fetchone()
    p = json.loads(ev["payload"])
    assert p["structure_changes"][0]["node_id"] == "c5"
    assert api.get_node("c5")["story_order"] < api.get_node("c9")["story_order"]


def test_revision_marks_pending_stale(api):  # C5（revision 面）
    _seed_two_volumes(api)
    other = api.proposals.create("scene", {"draft": "x"})   # 无关 pending
    pid = api.propose_revision("c5", {"volume": 1, "chapter": 9,
                                      "scene": 0, "beat": 0})
    api.confirm(pid)
    row = api.proposals.get(other)
    assert row["status"] == "stale"
    assert "revision" in row["stale_hint"]


def test_rewrite_proposal_keeps_original(api):
    p1 = api.proposals.create("premise", {"draft": "原稿"})
    fake = FakeBackend([json.dumps({"draft": "改写稿", "facts": [],
                                     "appeared": []}, ensure_ascii=False)])
    p2 = api.rewrite_proposal(p1, "更黑暗一点", backend=fake)
    assert api.proposals.get(p2)["status"] == "pending"
    assert json.loads(api.proposals.get(p2)["payload"])["rewritten_from"] == p1
    assert api.proposals.get(p1)["status"] == "pending"   # 原提案不动
```

- [ ] **Step 2: 跑测试确认失败**

- [ ] **Step 3: 最小实现**

```python
# src/snowel_core/flow/revision.py
import json


def propose_revision(api, node_id: str, new_address: dict, reason: str = "") -> str:
    """统一 revision（§5.2）：提案 → （级联影响分析位）→ 确认，三层复用。"""
    return api.proposals.create("revision", {
        "node_id": node_id, "reason": reason,
        "structure_changes": [{"op": "move", "node_id": node_id,
                               "address": new_address}]})


def rewrite_proposal(api, proposal_id: str, instruction: str, backend) -> str:
    """提案改写（壳 proposal.rewrite 的 core 面）：新提案标 rewritten_from。"""
    p = api.proposals.get(proposal_id)
    payload = json.loads(p["payload"])
    resp = backend.generate(
        f"按指示改写以下草稿，返回 JSON（draft/facts/appeared）。\n"
        f"指示：{instruction}\n\n原草稿：{payload.get('draft', '')}")
    parsed = json.loads(resp)
    return api.proposals.create(p["kind"], {
        **payload, "draft": parsed.get("draft", ""),
        "rewritten_from": proposal_id})
```

`api.confirm` 追加分支：`kind == "revision"` 时在 confirm 事务后追加 `revision_applied`（payload 取 `structure_changes`）+ apply，返回 `{"event_seq": seq, "cascade": {"wired": False, "planned_in": "级联检查计划"}}`；门面 `propose_revision` / `rewrite_proposal` 代理。

- [ ] **Step 4: 跑测试通过**：`pytest tests/flow -v`
- [ ] **Step 5: 提交**：`git commit -m "feat(flow): unified revision flow with cascade placeholder and proposal rewrite (5.2/FL-06)"`

---

### Task 18: 壳接线收口（MCP generate/writeback/search/audit + CLI export）

**Files:**
- Modify: `shell/src/snowel/mcp_server.py`、`shell/src/snowel/cli.py`、`tests/README.md`
- Test: `tests/shell/test_mcp_server.py`、`tests/shell/test_cli.py`（追加）

**Interfaces:**
- Consumes: Task 8/10/12（writeback 面）、Task 5/6（search/audit）、Task 14/17（generate/rewrite）、Task 9（backend 默认 LitellmBackend.for_conn）。
- Produces（壳零编排，一比一映射）：
  - `snowel_generate(artifact_type, locate, extra)`：`ctx.require_write()` → `ctx.api.ai_generate(...)`（backend 缺省 Litellm）→ `{"proposal_id", "audit_hint"}`。`_NOT_WIRED_PLANNED` 删 `"generate"`。
  - `snowel_writeback(action, params)`：`trigger`（require_write + `extract_and_writeback`）/ `result`（`deviation` + 最近 extract 提案）/ `list_auto` / `reject_auto`（require_write）/ `reconcile`。`_NOT_WIRED_PLANNED` 删 `"writeback"`。
  - `snowel_query` `action="search"`：`{"result": api.search(params["q"], mode=params.get("mode", "hybrid"))}`（api 门面 + `retrieval.hybrid.search` 代理）。`_NOT_WIRED_PLANNED` 删 `"query.search"`。
  - `snowel_proposal` `action="rewrite"`：`ctx.require_write()` + `ctx.api.rewrite_proposal(pid, instruction, backend)`。`_NOT_WIRED_PLANNED` 删 `"proposal.rewrite"`。
  - `snowel_advanced` `op="audit"`：`{"result": api.audit_recent(limit)}`（api 门面 + `retrieval.audit.recent` 代理）；ADVANCED_CATALOG `"audit"` → `{"wired": True, ...}`。`"flow"` 从 `_NOT_WIRED_PLANNED` 删（Task 13 已接）。
  - CLI `export --format md|txt`：从镜像逐章写 `<out>/<chapter_id>.md|.txt`（TC-SH-07 剩余面：产物含全部章节正文）；`PLANNED_IN` 删 `"export"`。
  - `tests/README.md` §1 追加四行：`llm/`、`retrieval/`、`writeback/`、`flow/`（含黑盒用例反向索引）。
  - 顺带（随行小项）：`snowel_status` readonly 时 `lease_holder` 报 `api.current_lease_holder()`（core lease 只读门面：读 lease 表 holder，无则 None）。

- [ ] **Step 1: 写失败测试**

```python
# tests/shell/test_mcp_server.py 追加（generate 测试注入 backend：_connected 加 backend=None 透传 build_mcp）
async def test_generate_and_search_wired(project):
    async with _connected(project, backend=FakeBackend([
            json.dumps({"draft": "灵感", "facts": [], "appeared": []})]
    )) as (ctx, client):
        g = await _call(client, "snowel_generate",
                        {"artifact_type": "premise"})
        assert "proposal_id" in g                     # 不再 not_wired
        s = await _call(client, "snowel_query",
                        {"action": "search", "params": {"q": "林晚"}})
        assert "result" in s


async def test_writeback_actions_wired(project, tmp_path):
    api = SnowelAPI.open(project)
    from snowel_core.writeback import mirror
    mirror.write_prose(api._conn, tmp_path, "ch1", "正文")
    api.close()
    async with _connected(project, backend=FakeBackend([
            json.dumps({"facts": [], "appeared": []})])) as (ctx, client):
        w = await _call(client, "snowel_writeback", {"action": "reconcile"})
        assert w == {"result": []}
        la = await _call(client, "snowel_writeback", {"action": "list_auto"})
        assert "result" in la


async def test_advanced_audit_wired(project):
    async with _connected(project) as (ctx, client):
        a = await _call(client, "snowel_advanced", {"op": "audit"})
        assert a["result"] == []                       # 空 audit 表
        cat = await _call(client, "snowel_advanced", {})
        assert cat["operations"]["audit"]["wired"] is True
```

**既有测试改造（本任务内，not_wired 断言随接线翻转）**：
- `_connected` 签名改 `(project, backend=None, **kw)`，内部 `build_mcp(ctx, backend=backend)`（backend 透传给 generate/writeback 注入）；
- `test_generate_writeback_not_wired` → 删除（由上方三条接线测试替代）；
- `test_query_routes_graph_actions` 末尾 search 的 `_assert_not_wired(searched, "query.search")` 改为 `assert "result" in searched`；
- `test_advanced_catalog_and_rebuild` 的 `all(not v["wired"] ...)` 收窄为 `all(not v["wired"] for k, v in ops.items() if k not in ("rebuild", "audit"))`；
- `tests/shell/test_cli.py::test_export_seal_not_wired_exit_2` 拆分：export 部分由下方导出测试替代，seal 保留 exit 2 断言。

```python
# tests/shell/test_cli.py 追加
def test_export_writes_all_chapters(tmp_path):
    SnowelAPI.init_project(tmp_path)
    api = SnowelAPI.open(tmp_path)
    pid = api.proposals.create("prose", {"chapter_id": "ch1",
                                         "content": "第一章：雨夜。"})
    api.confirm(pid)
    api.close()
    out = tmp_path / "export"
    res = runner.invoke(app, ["export", "--project", str(tmp_path),
                              "--out", str(out)])
    assert res.exit_code == 0
    assert (out / "ch1.md").read_text(encoding="utf-8") == "第一章：雨夜。"

def test_seal_still_not_wired(tmp_path):
    SnowelAPI.init_project(tmp_path)
    res = runner.invoke(app, ["seal", "--project", str(tmp_path)])
    assert res.exit_code == 2
```

（MCP 侧 generate 测试注入 backend：`build_mcp(ctx, backend=fake)` 增加可选参——测试专用注入点，生产缺省 Litellm；CLI export 走镜像不涉 LLM。）

- [ ] **Step 2: 跑测试确认失败**

- [ ] **Step 3: 实现**（壳一比一映射，模式与既有 action 分发一致；`build_mcp(ctx, backend=None)` 透传）

关键片段：

```python
# mcp_server.py
def build_mcp(ctx: ProjectContext, backend=None) -> FastMCP:
    ...
    @mcp.tool()
    def snowel_generate(artifact_type: str, locate: dict | None = None,
                        extra: dict | None = None) -> dict:
        ctx.require_write()
        pid = ctx.api.ai_generate(artifact_type, locate, extra, backend=backend)
        return {"proposal_id": pid}
```

CLI export：

```python
@app.command()
def export(project: ProjectOpt = None,
           out: Annotated[Optional[Path], typer.Option("--out", "-o")] = None,
           fmt: Annotated[str, typer.Option("--format", "-f",
             help="md | txt")] = "md") -> None:
    """导出全部章节正文（从库内镜像，D8）。"""
    ctx = _open_or_exit(project, want_write=False)
    try:
        out = out or ctx.project_path / "export"
        out.mkdir(parents=True, exist_ok=True)
        rows = ctx.api._conn.execute(
            "SELECT chapter_id, prose FROM chapter_prose ORDER BY chapter_id"
        ).fetchall()
        for r in rows:
            f = out / f"{r['chapter_id']}.{fmt}"
            f.write_text(r["prose"], encoding="utf-8")
        typer.echo(f"已导出 {len(rows)} 章至 {out}")
    finally:
        ctx.close()
```

（壳读镜像经 `api.export_prose()` 门面更合规——实现时在 api 加 `export_prose() -> list[dict]` 代理，CLI 不直接摸 `_conn`。）

- [ ] **Step 4: 全量回归**：`pytest`（全绿；含既有 69 例回归 + 新增用例）
- [ ] **Step 5: 提交**：`git commit -m "feat(shell): wire generate/writeback/search/audit/rewrite and cli export; register test dirs"`

---

## 覆盖矩阵（用例 ↔ 任务）

| 黑盒用例 | 任务 | 备注 |
|---|---|---|
| TC-WB-01 | 9 | 确认代写+登记+镜像 |
| TC-WB-02 | 9 | 短路（reconcile 层） |
| TC-WB-03 | 3+10 | 事件+自动抽取 |
| TC-WB-04 | 10 | manual/timer 模式 |
| TC-WB-05 | 3 | 文件为准重灌 |
| TC-WB-06 | 8 | 忽略修辞+分级 |
| TC-WB-07 | 12 | retraction+轻量反查 |
| TC-WB-08 | 12 | 前半覆盖；封卷拦截面留级联检查计划（豁免登记） |
| TC-RT-01 | 6 | prose 策略四类+兜底+TODO 排除 |
| TC-RT-02 | 6 | 审计含 dry_run 标注 |
| TC-RT-03 | 6 | 死亡过滤+兜底标记 |
| TC-RT-04 | 14 | 无裸生成路径 |
| TC-RT-05 | 8+14 | 小模型 per-call 路由；**多章批量抽取豁免（挂账下一计划）** |
| TC-RT-06 | 5 | per-project 切换重建 |
| TC-PR-02 | 17 | revision 面覆盖（pending 全标 stale）；retcon 触发面豁免（级联检查计划承接依赖分析） |
| TC-FL-01/02 | 16 | 卷首重放（C8/C9） |
| TC-FL-03 | 13 | status 流程 |
| TC-FL-04 | 15 | 受限展开 |
| TC-FL-05 | 11 | 偏离报告 |
| TC-FL-06 | 17 | revision 统一流程 |
| TC-PR-08 | 14 | D7 注入 |
| TC-PR-09 | 14 | 微节拍整组+exclude |
| TC-PR-10 | 8 | 分级落点 |
| TC-ON-05/06 | 1+11 | L2 补测+active 接线 |
| TC-SH-07（export 面） | 18 | 镜像导出 |
| TC-SH-02（audit 面） | 18 | advanced 目录 |

**豁免登记**：TC-CC-* 全域（级联检查计划）；TC-WB-08 后半（封卷拦截）；TC-EX-*（扩展包机制未排期）；rewrite_query 启用行为（testcases §11.3 既有豁免）；Web 面用例（第四步）。

## 执行注意

1. Task 2 装新依赖后先 `pip install -e . -e ./shell` 再跑全量（litellm/jieba/sqlite-vec 入 core 依赖）。
2. `sqlite-vec` 在 Windows 需确认 wheel 可用（0.1.6+ 有 win_amd64 wheel）；执行受阻时控制器裁决降级 Task 5 为 vec 接口桩 + 挂账。
3. `conftest.FakeBackend` 是全部 LLM 面测试的确定性生成端；任何测试不得 import litellm 真调用。
4. 计划缺陷执行期发现：控制器 Ruling 落 ledger 后按裁决继续，不停摆。


