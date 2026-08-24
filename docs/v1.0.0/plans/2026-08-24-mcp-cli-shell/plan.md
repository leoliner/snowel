# Snowel MCP + CLI 薄壳实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: 用 dev-workflow skill（`~/.agents/skills/dev-workflow/`）执行本计划；其内默认的 subagent-driven / executing-plans 两种模式均可。步骤用 checkbox（`- [ ]`）跟踪。

**Goal:** 为 snowel-core 建立单包双入口薄壳——CLI（`snowel`）与 MCP Server（`snowel-mcp`）——六工具/命令面一次立全，未接线能力返回结构化 not_wired 响应；承接挂账 L3，落地项目绑定（C4）与租约降级（C10）的壳侧行为。

**Architecture:** 新发行单元 `shell/`（包名 `snowel`，hatchling），只 import `snowel_core.api`（design §10 一比一映射、无编排逻辑）。core 侧仅三处最小扩展：`api.open()` 库存在校验（L3）、`graph_stats()` 与 `backup()` 两个只读门面方法。MCP 用官方 SDK FastMCP（stdio）；CLI 用 typer；共享项目绑定/租约上下文模块。

**Tech Stack:** Python 3.12+、mcp（官方 SDK，FastMCP）、typer>=0.12、sqlite3（标准库）。

**Spec:** `docs/v1.0.0/requirements.md`（§2 铁律、§7.2/§7.3、§8、§9）；`docs/v1.0.0/design.md`（§5 模块划分、§10 外壳约束、§12.2）；`docs/v1.0.0/testcases.md`（TC-SH-01–07）；`docs/v1.0.0/plans/2026-08-23-snowel-core/ledger.md`（挂账 L3）。

---

## 1. 全局约束

- **core 纯净**：`pyproject.toml`（snowel-core）不动；mcp/typer 依赖只进 `shell/pyproject.toml`；core 代码不得 import 壳。
- **壳只走门面**：壳代码只 `import snowel_core.api`（design §10）；出现 SQL 直查 `ctx.api._conn`、拼装多步领域流程等一律视为缺陷（铁律 1）。
- **工具面冻结**：MCP 恰好 6 个工具（TC-SH-01），名字与需求 §7.2 表逐字一致；新长尾能力只进 `snowel_advanced`。
- **not_wired 统一结构**：`{"wired": False, "capability": <str>, "planned_in": <str>, "message": <str>}`；MCP 以正常响应返回（AI 客户端可读字段），CLI 以 stderr 提示 + exit code 2 表达。
- **项目绑定优先级**（C4/TC-SH-06）：显式参数 `--project` > 环境变量 `SNOWEL_PROJECT` > cwd；每进程恰绑定一个项目。
- **租约降级**（C10/TC-SH-04/05）：获取失败 → readonly=True，写操作被拒并给可读提示，读操作全部正常；心跳缺失经 `stale_after` 过期后他端可抢（无永久锁死）。
- **Python 3.12+**；提交信息沿用 conventional commits（`feat(shell)`/`fix(core)`/`test(shell)`）。
- 开发安装：`pip install -e . -e ./shell`（两个包都要装，pytest 从仓库根收集 `tests/`）。

## 2. Preflight 裁决与范围边界

### 2.1 挂账处置（来自 2026-08-23-snowel-core ledger）

| # | 处置 | 说明 |
|---|---|---|
| L1 | 关闭不携带 | `groups.validate` 畸形版本串 → 回写环/级联检查计划 |
| L2 | 关闭不携带 | `completeness.derive` 测试与签名 → 接线 completeness 的计划 |
| L3 | **本计划承接** | `api.open()` 不校验库存在 → Task 1：core 侧抛 `ProjectNotFoundError`（防 sqlite 静默建空库），壳侧转译可读错误 |
| L4 | 关闭不携带 | `descendants` 边时效过滤 → 级联检查计划 |

### 2.2 用户裁决（2026-08-24）

- **占位策略**：工具/命令面全注册；未接线操作返回 not_wired（结构化），后续计划接通时壳零改动。
- **包结构**：单包双入口——`shell/` 发行单元（包名 `snowel`），console_scripts 两个入口；core 保持独立纯净包。

### 2.3 豁免清单（黑盒用例边界）

| 用例 | 本计划状态 |
|---|---|
| TC-SH-01 六工具枚举 | ✅ 全达成 |
| TC-SH-02 advanced 目录 | ✅ 达成（目录含 wired 标志；子操作仅 rebuild 真接线） |
| TC-SH-03 三端视图一致 | 部分：以 MCP+CLI 共库验证子集（提案经 MCP 确认后 CLI 可见）；Web 侧归阶段四 |
| TC-SH-04/05 租约 | ✅ 壳层达成（核心层已有 tests/storage/test_lease.py） |
| TC-SH-06 项目绑定 | ✅ 达成 |
| TC-SH-07 status/export/backup | status、backup 达成；**export 正文部分豁免**（依赖阶段三章节镜像，本计划 not_wired） |
| TC-SH-08 Web 界面 | 豁免（阶段四） |

not_wired 能力与归属：`generate`（阶段三生成环 llm/flow/retrieval）、`writeback`（阶段三回写环）、`query.search`（阶段三混合检索）、`proposal.rewrite`（生成环）、`flow` 进度（阶段三 flow）、`export`（回写环镜像）、`seal`（级联检查计划 volume_sealed）、advanced 目录中除 rebuild 外全部子操作。

## 3. 文件结构总览

```
shell/                              # 新发行单元：包名 snowel
  pyproject.toml                    # deps: snowel-core/mcp/typer；scripts: snowel、snowel-mcp
  src/snowel/
    __init__.py                     # __version__
    project.py                      # 项目绑定（C4）+ 租约上下文与心跳（C10）+ 可读错误
    mcp_server.py                   # FastMCP 六工具（TC-SH-01/02）
    cli.py                          # typer 命令面（TC-SH-06/07）
src/snowel_core/
  api.py                            # Modify：L3 校验 + graph_stats/backup 门面
  storage/queries.py                # Modify：graph_stats 查询
  storage/db.py                     # Modify：backup（VACUUM INTO）
tests/
  api/test_open.py                  # Create：L3
  api/test_api.py                   # Modify：backup 门面
  storage/test_queries.py           # Modify：graph_stats
  shell/test_project.py             # Create：绑定/租约上下文/心跳
  shell/test_mcp_server.py          # Create：六工具（in-memory session）
  shell/test_cli.py                 # Create：CliRunner
  shell/test_lease_integration.py   # Create：跨壳租约（TC-SH-04/05 壳层）
  README.md                         # Modify：登记 shell 行
```

tests 子目录沿用现状：无 `__init__.py`，测试文件名全局唯一。

---

## 4. 任务分解

### Task 1: core `api.open()` 库存在校验（L3 承接）

**Files:**
- Modify: `src/snowel_core/api.py`
- Test: `tests/api/test_open.py`（Create）

**Interfaces:**
- Consumes: `SnowelAPI.open(path)`（现状：sqlite 静默建空库）
- Produces: `class ProjectNotFoundError(Exception)`（模块 `snowel_core.api`）；`open()` 对缺 `snowel.db` 的目录抛出，且不产生新文件。Task 3 的壳依赖此异常做转译。

- [ ] **Step 1: 写失败测试**

```python
# tests/api/test_open.py
import pytest

from snowel_core.api import ProjectNotFoundError, SnowelAPI


def test_open_missing_project_raises(tmp_path):
    with pytest.raises(ProjectNotFoundError, match="snowel.db"):
        SnowelAPI.open(tmp_path)


def test_open_missing_does_not_create_db(tmp_path):
    with pytest.raises(ProjectNotFoundError):
        SnowelAPI.open(tmp_path)
    assert not (tmp_path / "snowel.db").exists()  # 不得静默建空库


def test_open_existing_project(tmp_path):
    SnowelAPI.init_project(tmp_path)
    api = SnowelAPI.open(tmp_path)
    try:
        assert api.find_nodes() == []
    finally:
        api.close()
```

- [ ] **Step 2: 跑测试确认失败**

Run: `pytest tests/api/test_open.py -v`
Expected: FAIL（ImportError: ProjectNotFoundError）

- [ ] **Step 3: 最小实现**

`src/snowel_core/api.py` 顶部（`from .storage...` 之后）加异常类，并改写 `open`：

```python
class ProjectNotFoundError(Exception):
    """open() 目标目录缺少 snowel.db（L3：不静默新建空库）"""
```

```python
    @classmethod
    def open(cls, path) -> "SnowelAPI":
        db_path = Path(path) / "snowel.db"
        if not db_path.exists():
            raise ProjectNotFoundError(f"未找到项目库：{db_path}")
        return cls(db.connect(db_path))
```

- [ ] **Step 4: 跑测试确认通过**

Run: `pytest tests/api/test_open.py tests/api -v`
Expected: PASS（不影响 test_api.py 既有用例）

- [ ] **Step 5: 提交**

```bash
git add src/snowel_core/api.py tests/api/test_open.py
git commit -m "fix(core): validate db existence in api.open (L3)"
```

### Task 2: core 只读门面扩展：graph_stats / backup

**Files:**
- Modify: `src/snowel_core/storage/queries.py`、`src/snowel_core/storage/db.py`、`src/snowel_core/api.py`
- Test: `tests/storage/test_queries.py`（Modify，追加）、`tests/api/test_api.py`（Modify，追加）

**Interfaces:**
- Consumes: 无新依赖。
- Produces: `SnowelAPI.graph_stats() -> {"nodes": int, "edges": int, "nodes_by_type": dict[str, int]}`；`SnowelAPI.backup(out_path: str | Path) -> None`（目标已存在抛 `FileExistsError`）。Task 4（MCP status）、Task 5（CLI status/backup）消费。

- [ ] **Step 1: 写 graph_stats 失败测试**（追加到 `tests/storage/test_queries.py`；沿用该文件现有建库 fixture 风格，若 fixture 名不同以现场为准）

```python
FACTS = [{"fact": "node", "id": "n1", "types": ["Character"],
          "name": "林晚", "props": {}}]


def test_graph_stats_counts_and_types(conn):
    from snowel_core.storage import db, events, projector
    from snowel_core.storage.queries import graph_stats
    with db.transaction(conn):
        events.append_event(conn, "proposal_confirmed",
                            {"facts": FACTS})
        projector.apply(conn)
    stats = graph_stats(conn)
    assert stats["nodes"] == 1
    assert stats["edges"] == 0
    assert stats["nodes_by_type"] == {"Character": 1}
```

> 执行注意：若 `tests/storage/test_queries.py` 现有 fixture 不叫 `conn`，复用其建库 fixture（`db.connect` + `db.migrate`）即可，断言不变。

- [ ] **Step 2: 跑测试确认失败**

Run: `pytest tests/storage/test_queries.py -v`
Expected: FAIL（ImportError: graph_stats）

- [ ] **Step 3: 实现 graph_stats**

`src/snowel_core/storage/queries.py` 追加：

```python
def graph_stats(conn: sqlite3.Connection) -> dict:
    nodes = conn.execute("SELECT count(*) c FROM nodes").fetchone()["c"]
    edges = conn.execute("SELECT count(*) c FROM edges").fetchone()["c"]
    by_type = {r["type"]: r["n"] for r in conn.execute(
        "SELECT je.value AS type, count(*) AS n "
        "FROM nodes, json_each(nodes.types) je "
        "GROUP BY je.value ORDER BY n DESC")}
    return {"nodes": nodes, "edges": edges, "nodes_by_type": by_type}
```

- [ ] **Step 4: 跑测试确认通过**

Run: `pytest tests/storage/test_queries.py -v`
Expected: PASS

- [ ] **Step 5: 写 backup 失败测试**（追加到 `tests/api/test_api.py`，走门面黑盒）

```python
import shutil


def test_backup_roundtrip_equivalent(tmp_path):
    api = SnowelAPI.init_project(tmp_path)
    pid = api.proposals.create("scene", {"facts": [
        {"fact": "node", "id": "n1", "types": ["Character"],
         "name": "林晚", "props": {}}]})
    api.proposals.confirm(pid)
    out = tmp_path / "b.db"
    api.backup(out)
    restore = tmp_path / "restore"
    restore.mkdir()
    shutil.copy(out, restore / "snowel.db")
    api2 = SnowelAPI.open(restore)
    try:
        assert api2.graph_stats() == api.graph_stats()
        assert [r["status"] for r in api2.proposals.list()] == ["confirmed"]
    finally:
        api2.close()
    api.close()


def test_backup_refuses_overwrite(tmp_path):
    api = SnowelAPI.init_project(tmp_path)
    out = tmp_path / "b.db"
    out.write_bytes(b"x")
    with pytest.raises(FileExistsError):
        api.backup(out)
    api.close()
```

- [ ] **Step 6: 跑测试确认失败**

Run: `pytest tests/api/test_api.py -v`
Expected: FAIL（AttributeError: backup）

- [ ] **Step 7: 实现 backup**

`src/snowel_core/storage/db.py` 追加：

```python
def backup(conn: sqlite3.Connection, out_path) -> None:
    out = Path(out_path)
    if out.exists():
        raise FileExistsError(f"备份文件已存在：{out}")
    conn.execute("VACUUM INTO ?", (str(out),))
```

`src/snowel_core/api.py` 追加两个门面方法（`graph_stats` 代理 queries、`backup` 代理 db）：

```python
    def graph_stats(self) -> dict:
        return queries.graph_stats(self._conn)

    def backup(self, out_path) -> None:
        db.backup(self._conn, out_path)
```

- [ ] **Step 8: 全量回归 + 提交**

Run: `pytest -v`
Expected: 全 PASS（core 37 例 + 新增）

```bash
git add src/snowel_core tests/storage/test_queries.py tests/api/test_api.py
git commit -m "feat(core): graph_stats and backup facade for shells"
```

### Task 3: 壳包骨架 + 项目绑定与租约上下文

**Files:**
- Create: `shell/pyproject.toml`、`shell/src/snowel/__init__.py`、`shell/src/snowel/project.py`
- Test: `tests/shell/test_project.py`

**Interfaces:**
- Consumes: `snowel_core.api.SnowelAPI`（init_project/open/acquire_lease/renew_lease/release_lease）、`ProjectNotFoundError`（Task 1）。
- Produces（Task 4/5/6 消费）:
  - `resolve_project_path(explicit: str | Path | None = None) -> Path`（优先级 explicit > `SNOWEL_PROJECT` > cwd）
  - `class ProjectError(Exception)`（壳层可读错误）
  - `class ProjectContext`：`.api`、`.readonly: bool`、`.holder: str | None`、`.project_path: Path`、`.require_write()`（readonly 抛 ProjectError）、`.close()`（停心跳 + 定向 release + 关连接）
  - `open_project(path, want_write=True, stale_after=30.0, heartbeat=True) -> ProjectContext`（缺库抛 ProjectError；抢租约失败 → readonly=True；heartbeat=True 时后台 daemon 线程按 `stale_after/3` 续租）

- [ ] **Step 1: 建包与安装**

`shell/pyproject.toml`：

```toml
[project]
name = "snowel"
version = "0.1.0"
description = "Snowel 薄壳：CLI（snowel）与 MCP Server（snowel-mcp）"
requires-python = ">=3.12"
dependencies = ["snowel-core", "mcp>=1.2", "typer>=0.12"]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project.scripts]
snowel = "snowel.cli:main"
snowel-mcp = "snowel.mcp_server:main"

[tool.hatch.build.targets.wheel]
packages = ["src/snowel"]
```

`shell/src/snowel/__init__.py`：

```python
__version__ = "0.1.0"
```

Run: `pip install -e . -e ./shell && python -c "import snowel; print(snowel.__version__)"`
Expected: `0.1.0`（console_scripts 引用的 cli/mcp_server 模块属 Task 4/5，安装时入口不校验，不报错）

- [ ] **Step 2: 写失败测试**

```python
# tests/shell/test_project.py
import time

import pytest

from snowel_core.api import SnowelAPI
from snowel.project import ProjectError, open_project, resolve_project_path


@pytest.fixture
def project(tmp_path):
    SnowelAPI.init_project(tmp_path)
    return tmp_path


def test_resolve_priority_explicit_env_cwd(tmp_path, monkeypatch):
    (tmp_path / "a").mkdir()
    (tmp_path / "b").mkdir()
    monkeypatch.setenv("SNOWEL_PROJECT", str(tmp_path / "a"))
    assert resolve_project_path(str(tmp_path / "b")) == tmp_path / "b"
    assert resolve_project_path(None) == tmp_path / "a"
    monkeypatch.delenv("SNOWEL_PROJECT")
    monkeypatch.chdir(tmp_path / "b")
    assert resolve_project_path(None) == tmp_path / "b"


def test_open_missing_project_readable_error(tmp_path):
    with pytest.raises(ProjectError, match="snowel init"):
        open_project(tmp_path)


def test_open_holds_lease(project):
    ctx = open_project(project, heartbeat=False)
    try:
        assert ctx.readonly is False
        assert ctx.holder
    finally:
        ctx.close()


def test_second_instance_readonly_and_reads_ok(project):
    a = open_project(project, heartbeat=False)
    b = open_project(project, heartbeat=False)
    try:
        assert b.readonly is True
        with pytest.raises(ProjectError, match="只读"):
            b.require_write()
        assert b.api.find_nodes() == []  # 读操作不受影响（TC-SH-04）
    finally:
        b.close()
        a.close()


def test_release_then_next_can_write(project):
    a = open_project(project, heartbeat=False)
    a.close()
    b = open_project(project, heartbeat=False)
    try:
        assert b.readonly is False
    finally:
        b.close()


def test_heartbeat_keeps_lease_alive(project):
    a = open_project(project, stale_after=0.6, heartbeat=True)
    time.sleep(0.9)  # 超过 stale_after，但心跳在续
    b = open_project(project, heartbeat=False)
    try:
        assert b.readonly is True
    finally:
        b.close()
    a.close()
```

> 执行注意：`test_resolve_priority_explicit_env_cwd` 里删除 `monkeymonkey` 占位行——上面为笔误示例，实际写入时只保留三个断言。

- [ ] **Step 3: 跑测试确认失败**

Run: `pytest tests/shell/test_project.py -v`
Expected: FAIL（ModuleNotFoundError: snowel.project）

- [ ] **Step 4: 实现 project.py**

```python
# shell/src/snowel/project.py
"""项目绑定（C4）与单写者租约的壳侧上下文（C10）。

每进程绑定一个项目；租约获取失败降级只读。心跳线程用独立连接
renew（sqlite 连接不跨线程共用），进程死亡 = 心跳停止，
租约经 stale_after 过期后他端可抢（无永久锁死）。
"""
from __future__ import annotations

import os
import socket
import threading
from pathlib import Path

from snowel_core.api import ProjectNotFoundError, SnowelAPI


class ProjectError(Exception):
    """壳层可读错误：项目无效、只读越权等。"""


def resolve_project_path(explicit: str | Path | None = None) -> Path:
    """项目定位优先级（C4）：显式参数 > 环境变量 SNOWEL_PROJECT > cwd。"""
    if explicit is not None:
        return Path(explicit).resolve()
    env = os.environ.get("SNOWEL_PROJECT")
    if env:
        return Path(env).resolve()
    return Path.cwd()


class ProjectContext:
    def __init__(self, api: SnowelAPI, readonly: bool, holder: str | None,
                 project_path: Path):
        self.api = api
        self.readonly = readonly
        self.holder = holder
        self.project_path = project_path
        self._stop = threading.Event()
        self._renewer: threading.Thread | None = None

    def require_write(self) -> None:
        if self.readonly:
            raise ProjectError(
                "另一进程持有写租约，当前只读；写操作被拒绝"
                "（租约释放或过期后自动恢复）")

    def start_heartbeat(self, interval: float) -> None:
        def _loop() -> None:
            try:
                api2 = SnowelAPI.open(self.project_path)
            except ProjectNotFoundError:
                return
            try:
                while not self._stop.wait(interval):
                    if not api2.renew_lease(self.holder):
                        break  # 租约已被他端夺走，停止续期
            finally:
                api2.close()

        self._renewer = threading.Thread(target=_loop, daemon=True)
        self._renewer.start()

    def close(self) -> None:
        self._stop.set()
        if self._renewer is not None:
            self._renewer.join(timeout=5)
        if not self.readonly and self.holder:
            self.api.release_lease(self.holder)  # 按 holder 定向，失租后为 no-op
        self.api.close()


def open_project(path: str | Path, want_write: bool = True,
                 stale_after: float = 30.0, heartbeat: bool = True,
                 ) -> ProjectContext:
    p = Path(path)
    try:
        api = SnowelAPI.open(p)
    except ProjectNotFoundError as e:
        raise ProjectError(
            f"目录不是 Snowel 项目（未找到 {p / 'snowel.db'}）；"
            f"请先运行 snowel init，或用 --project / SNOWEL_PROJECT 指定正确目录"
        ) from e
    holder = f"snowel@{socket.gethostname()}:{os.getpid()}"
    got = api.acquire_lease(holder, stale_after=stale_after) if want_write else False
    ctx = ProjectContext(api, readonly=not got,
                         holder=holder if got else None, project_path=p)
    if got and heartbeat:
        ctx.start_heartbeat(interval=max(stale_after / 3, 0.05))
    return ctx
```

- [ ] **Step 5: 跑测试确认通过**

Run: `pytest tests/shell/test_project.py -v`
Expected: 6 PASS

- [ ] **Step 6: 提交**

```bash
git add shell/pyproject.toml shell/src/snowel tests/shell/test_project.py
git commit -m "feat(shell): package skeleton, project binding and lease context"
```

### Task 4: MCP Server 六工具

**Files:**
- Create: `shell/src/snowel/mcp_server.py`
- Test: `tests/shell/test_mcp_server.py`

**Interfaces:**
- Consumes: `open_project`/`ProjectContext`（Task 3）、`graph_stats`/`proposals`/查询门面（Task 2 与 core 现有）。
- Produces: `build_mcp(ctx: ProjectContext) -> FastMCP`（工厂，工具闭包捕获 ctx）；`main() -> None`（stdio 启动入口）。Task 6 消费 `build_mcp`。

- [ ] **Step 1: 写失败测试**

```python
# tests/shell/test_mcp_server.py
import json
from contextlib import asynccontextmanager

import pytest
from mcp.shared.memory import create_connected_server_and_client_session

from snowel.mcp_server import build_mcp
from snowel.project import open_project
from snowel_core.api import SnowelAPI

pytestmark = pytest.mark.anyio


@pytest.fixture
def anyio_backend():
    return "asyncio"


FACTS = [{"fact": "node", "id": "n1", "types": ["Character"],
          "name": "林晚", "props": {}}]


@pytest.fixture
def project(tmp_path):
    SnowelAPI.init_project(tmp_path)
    return tmp_path


@asynccontextmanager
async def _connected(project, **kw):
    ctx = open_project(project, **kw)
    try:
        mcp = build_mcp(ctx)
        async with create_connected_server_and_client_session(
                mcp._mcp_server) as client:
            yield ctx, client
    finally:
        ctx.close()


async def _call(client, name, args):
    res = await client.call_tool(name, args)
    assert not res.isError
    return json.loads(res.content[0].text)


def _assert_not_wired(d, capability):
    assert d["wired"] is False
    assert d["capability"] == capability
    assert d["planned_in"]
    assert d["message"]


async def test_exactly_six_tools(project):  # TC-SH-01
    async with _connected(project) as (ctx, client):
        tools = await client.list_tools()
        assert {t.name for t in tools.tools} == {
            "snowel_status", "snowel_generate", "snowel_query",
            "snowel_proposal", "snowel_writeback", "snowel_advanced"}


async def test_status_reports_graph_and_proposals(project):
    api = SnowelAPI.open(project)
    api.proposals.create("premise", {"facts": FACTS})
    api.close()
    async with _connected(project) as (ctx, client):
        d = await _call(client, "snowel_status", {})
        assert d["readonly"] is False
        assert d["proposals"] == {"pending": 1}
        assert d["graph"]["nodes"] == 0
        _assert_not_wired(d["flow"], "flow")


async def test_proposal_end_to_end(project):
    api = SnowelAPI.open(project)
    pid = api.proposals.create("scene", {"facts": FACTS})
    api.close()
    async with _connected(project) as (ctx, client):
        listed = await _call(client, "snowel_proposal", {"action": "list"})
        assert listed["result"][0]["id"] == pid
        done = await _call(client, "snowel_proposal",
                           {"action": "confirm", "proposal_id": pid})
        assert done["event_seq"] >= 1
    api = SnowelAPI.open(project)
    try:
        assert [r["status"] for r in api.proposals.list()] == ["confirmed"]
        assert api.graph_stats()["nodes"] == 1
    finally:
        api.close()


async def test_query_routes_graph_actions(project):
    api = SnowelAPI.open(project)
    pid = api.proposals.create("scene", {"facts": FACTS})
    api.proposals.confirm(pid)
    api.close()
    async with _connected(project) as (ctx, client):
        found = await _call(client, "snowel_query",
                            {"action": "find", "params": {"name": "林晚"}})
        assert found["result"][0]["id"] == "n1"
        node = await _call(client, "snowel_query",
                           {"action": "node", "params": {"node_id": "n1"}})
        assert node["result"]["name"] == "林晚"
        st = await _call(client, "snowel_query",
                         {"action": "state_at", "params": {"story_order": 100}})
        assert isinstance(st["result"], dict)
        searched = await _call(client, "snowel_query",
                               {"action": "search", "params": {"q": "林晚"}})
        _assert_not_wired(searched, "query.search")


async def test_generate_writeback_not_wired(project):
    async with _connected(project) as (ctx, client):
        g = await _call(client, "snowel_generate",
                        {"artifact_type": "premise"})
        _assert_not_wired(g, "generate")
        w = await _call(client, "snowel_writeback", {"action": "run"})
        _assert_not_wired(w, "writeback")
        r = await _call(client, "snowel_proposal",
                        {"action": "rewrite", "proposal_id": "x"})
        _assert_not_wired(r, "proposal.rewrite")


async def test_advanced_catalog_and_rebuild(project):  # TC-SH-02
    api = SnowelAPI.open(project)
    pid = api.proposals.create("scene", {"facts": FACTS})
    api.proposals.confirm(pid)
    api.close()
    async with _connected(project) as (ctx, client):
        cat = await _call(client, "snowel_advanced", {})
        ops = cat["operations"]
        assert set(ops) >= {"rebuild", "setting_gap", "foreshadow_register",
                            "seal", "retcon", "extension_packs", "audit"}
        assert ops["rebuild"]["wired"] is True
        assert all(not v["wired"] for k, v in ops.items() if k != "rebuild")
        done = await _call(client, "snowel_advanced", {"op": "rebuild"})
        assert done == {"rebuilt": True}
        miss = await _call(client, "snowel_advanced", {"op": "seal"})
        _assert_not_wired(miss, "seal")


async def test_write_rejected_when_readonly(project):  # TC-SH-04 壳层
    api = SnowelAPI.open(project)
    pid = api.proposals.create("scene", {"facts": FACTS})
    api.close()
    blocker = open_project(project, heartbeat=False)
    try:
        async with _connected(project) as (ctx, client):
            assert ctx.readonly is True
            res = await client.call_tool(
                "snowel_proposal",
                {"action": "confirm", "proposal_id": pid})
            assert res.isError  # require_write 拒绝 → MCP 错误响应
    finally:
        blocker.close()
```

> 执行注意：FastMCP 底层 server 属性以所装 mcp SDK 为准（`_mcp_server`；个别版本暴露为 `.server`）——仅此属性名可按实际调整，断言不变。

- [ ] **Step 2: 跑测试确认失败**

Run: `pytest tests/shell/test_mcp_server.py -v`
Expected: FAIL（ModuleNotFoundError: snowel.mcp_server）

- [ ] **Step 3: 实现 mcp_server.py**

```python
# shell/src/snowel/mcp_server.py
"""Snowel MCP Server（stdio 薄壳）。

一个 server 进程绑定一个项目（C4）；六工具一比一映射 api 门面
（design §10，无编排逻辑）；未接线能力返回结构化 not_wired 响应
（用户裁决 2026-08-24：接通后工具签名不变，壳零改动）。
"""
from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from .project import ProjectContext, open_project, resolve_project_path

_NOT_WIRED_PLANNED = {
    "generate": "阶段三 生成环（llm/flow/retrieval，E3 三口）",
    "writeback": "阶段三 回写环（writeback 模块 + 正文镜像 D8）",
    "query.search": "阶段三 混合检索（FTS5 / sqlite-vec）",
    "proposal.rewrite": "生成环接线后的提案改写",
    "flow": "阶段三 flow 模块（雪花流程编排）",
}

ADVANCED_CATALOG: dict[str, dict] = {
    "rebuild": {"wired": True, "desc": "从事件日志全量重建物化图（损坏恢复）"},
    "setting_gap": {"wired": False, "planned_in": "设定库纵向轨道（flow）"},
    "mechanism_detail": {"wired": False, "planned_in": "属性组接线（挂账 L1）"},
    "foreshadow_register": {"wired": False, "planned_in": "本体语义门面（级联检查计划）"},
    "seal": {"wired": False, "planned_in": "级联检查计划（volume_sealed 事件）"},
    "retcon": {"wired": False, "planned_in": "级联检查计划（consistency 模块）"},
    "extension_packs": {"wired": False, "planned_in": "E4 目录式发现"},
    "audit": {"wired": False, "planned_in": "阶段三 retrieval_audit"},
}


def _not_wired(capability: str, planned_in: str | None = None) -> dict:
    return {
        "wired": False,
        "capability": capability,
        "planned_in": planned_in or _NOT_WIRED_PLANNED[capability],
        "message": "底层模块尚未实现，当前为占位响应；接通后本工具签名不变。",
    }


def build_mcp(ctx: ProjectContext) -> FastMCP:
    mcp = FastMCP("snowel")

    @mcp.tool()
    def snowel_status() -> dict:
        """项目状态：租约、待确认提案、图谱统计、流程进度。"""
        counts: dict[str, int] = {}
        for row in ctx.api.proposals.list():
            counts[row["status"]] = counts.get(row["status"], 0) + 1
        return {
            "project": str(ctx.project_path),
            "readonly": ctx.readonly,
            "lease_holder": ctx.holder,
            "proposals": counts,
            "graph": ctx.api.graph_stats(),
            "flow": _not_wired("flow"),
        }

    @mcp.tool()
    def snowel_generate(artifact_type: str,
                        locate: dict | None = None,
                        extra: dict | None = None) -> dict:
        """创作主力：按产物类型路由对应层 ai_generate（未接线）。"""
        return _not_wired("generate")

    @mcp.tool()
    def snowel_query(action: str, params: dict | None = None) -> dict:
        """图谱查询：find / node / edges / descendants / state_at；search 未接线。"""
        p = params or {}
        if action == "find":
            return {"result": ctx.api.find_nodes(name=p.get("name"),
                                                 type=p.get("type"))}
        if action == "node":
            return {"result": ctx.api.get_node(p["node_id"])}
        if action == "edges":
            return {"result": ctx.api.edges_of(
                p["node_id"], direction=p.get("direction", "both"))}
        if action == "descendants":
            return {"result": ctx.api.descendants(
                p["node_id"], kinds=p.get("kinds"),
                max_depth=p.get("max_depth", 10))}
        if action == "state_at":
            return {"result": ctx.api.state_at(p["story_order"])}
        if action == "search":
            return _not_wired("query.search")
        raise ValueError(
            f"未知 query action：{action}"
            "（可用：find/node/edges/descendants/state_at/search）")

    @mcp.tool()
    def snowel_proposal(action: str, proposal_id: str | None = None,
                        status: str | None = None,
                        reason: str | None = None) -> dict:
        """提案队列：list / confirm / reject / void；rewrite 未接线。"""
        if action == "list":
            return {"result": ctx.api.proposals.list(status)}
        if action == "rewrite":
            return _not_wired("proposal.rewrite")
        if not proposal_id:
            raise ValueError(f"{action} 需要 proposal_id")
        ctx.require_write()
        if action == "confirm":
            seq = ctx.api.proposals.confirm(proposal_id)
            return {"confirmed": proposal_id, "event_seq": seq}
        if action == "reject":
            ctx.api.proposals.reject(proposal_id, reason)
            return {"rejected": proposal_id}
        if action == "void":
            ctx.api.proposals.void(proposal_id)
            return {"voided": proposal_id}
        raise ValueError(
            f"未知 proposal action：{action}（可用：list/confirm/reject/void/rewrite）")

    @mcp.tool()
    def snowel_writeback(action: str | None = None,
                         params: dict | None = None) -> dict:
        """回写环：手动触发抽取、查抽取结果、否决 auto 条目（未接线）。"""
        return _not_wired("writeback")

    @mcp.tool()
    def snowel_advanced(op: str | None = None) -> dict:
        """长尾入口：无参返回操作目录；已接线子操作直接路由。"""
        if op is None:
            return {"operations": ADVANCED_CATALOG}
        if op == "rebuild":
            ctx.require_write()
            ctx.api.rebuild()
            return {"rebuilt": True}
        if op in ADVANCED_CATALOG:
            return _not_wired(op, ADVANCED_CATALOG[op]["planned_in"])
        raise ValueError(f"未知 advanced op：{op}")

    return mcp


def main() -> None:
    ctx = open_project(resolve_project_path(None))  # env SNOWEL_PROJECT 或 cwd
    mcp = build_mcp(ctx)
    mcp.run("stdio")
```

- [ ] **Step 4: 跑测试确认通过**

Run: `pytest tests/shell/test_mcp_server.py -v`
Expected: 7 PASS

- [ ] **Step 5: 提交**

```bash
git add shell/src/snowel/mcp_server.py tests/shell/test_mcp_server.py
git commit -m "feat(shell): MCP server with six tools"
```

### Task 5: CLI 命令面

**Files:**
- Create: `shell/src/snowel/cli.py`
- Test: `tests/shell/test_cli.py`

**Interfaces:**
- Consumes: `resolve_project_path`/`open_project`/`ProjectError`（Task 3）、`SnowelAPI.init_project`、`graph_stats`/`backup`（Task 2）。
- Produces: `app`（typer.Typer）、`main() -> None`（console_scripts 入口）。命令：`init` / `status` / `backup` / `export`（not_wired，exit 2）/ `seal`（not_wired，exit 2）；全局选项 `--project/-p`。

设计说明（写给评审）：CLI 命令全部只读或初始化，不抢写租约（`want_write=False`）；`seal` 等真写命令接线时再启用 `require_write` 路径（Task 3 已测）。`export` 正文依赖阶段三镜像，本计划 not_wired（豁免见 §2.3）。

- [ ] **Step 1: 写失败测试**

```python
# tests/shell/test_cli.py
import shutil

from typer.testing import CliRunner

from snowel.cli import app
from snowel_core.api import SnowelAPI

runner = CliRunner()

FACTS = [{"fact": "node", "id": "n1", "types": ["Character"],
          "name": "林晚", "props": {}}]


def test_init_creates_db(tmp_path):
    res = runner.invoke(app, ["init", "--project", str(tmp_path)])
    assert res.exit_code == 0
    assert (tmp_path / "snowel.db").exists()


def test_init_existing_project_hints(tmp_path):
    runner.invoke(app, ["init", "--project", str(tmp_path)])
    res = runner.invoke(app, ["init", "--project", str(tmp_path)])
    assert res.exit_code == 0
    assert "已存在" in res.output


def test_status_missing_project_exits_1(tmp_path):
    res = runner.invoke(app, ["status", "--project", str(tmp_path)])
    assert res.exit_code == 1
    assert "snowel init" in res.output


def test_status_reports_counts(tmp_path):
    SnowelAPI.init_project(tmp_path)
    api = SnowelAPI.open(tmp_path)
    api.proposals.create("scene", {"facts": FACTS})
    pid = api.proposals.create("scene", {"facts": FACTS})
    api.proposals.confirm(pid)
    api.close()
    res = runner.invoke(app, ["status", "--project", str(tmp_path)])
    assert res.exit_code == 0
    assert "pending 1" in res.output
    assert "confirmed 1" in res.output
    assert "节点 1" in res.output
    assert "Character 1" in res.output


def test_backup_roundtrip_and_overwrite_guard(tmp_path):
    SnowelAPI.init_project(tmp_path)
    api = SnowelAPI.open(tmp_path)
    pid = api.proposals.create("scene", {"facts": FACTS})
    api.proposals.confirm(pid)
    api.close()
    out = tmp_path / "b.db"
    res = runner.invoke(app, ["backup", "--project", str(tmp_path),
                              "--out", str(out)])
    assert res.exit_code == 0 and out.exists()
    res2 = runner.invoke(app, ["backup", "--project", str(tmp_path),
                               "--out", str(out)])
    assert res2.exit_code == 1 and "拒绝覆盖" in res2.output
    restore = tmp_path / "r"
    restore.mkdir()
    shutil.copy(out, restore / "snowel.db")
    api2 = SnowelAPI.open(restore)
    assert api2.graph_stats()["nodes"] == 1
    api2.close()


def test_export_seal_not_wired_exit_2(tmp_path):
    SnowelAPI.init_project(tmp_path)
    for cmd in (["export", "--project", str(tmp_path)],
                ["seal", "--project", str(tmp_path)]):
        res = runner.invoke(app, cmd)
        assert res.exit_code == 2
        assert "未接线" in res.output


def test_project_option_overrides_cwd(tmp_path, monkeypatch):
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    monkeypatch.delenv("SNOWEL_PROJECT", raising=False)
    monkeypatch.chdir(elsewhere)
    SnowelAPI.init_project(tmp_path / "proj")
    res = runner.invoke(app, ["status", "--project", str(tmp_path / "proj")])
    assert res.exit_code == 0
```

- [ ] **Step 2: 跑测试确认失败**

Run: `pytest tests/shell/test_cli.py -v`
Expected: FAIL（ModuleNotFoundError: snowel.cli）

- [ ] **Step 3: 实现 cli.py**

```python
# shell/src/snowel/cli.py
"""Snowel CLI（typer 薄壳）：本地管理动作，不做交互式创作（需求 §7.3）。"""
from __future__ import annotations

import datetime as _dt
from pathlib import Path
from typing import Annotated, Optional

import typer

from .project import ProjectError, open_project, resolve_project_path

app = typer.Typer(help="Snowel 本地管理（薄壳：只调用 snowel-core 门面）")

_project: Optional[Path] = None

PLANNED_IN = {
    "export": "阶段三 回写环（章节正文镜像，D8）",
    "seal": "级联检查计划（volume_sealed 事件）",
}


def _not_wired(capability: str) -> None:
    typer.secho(
        f"未接线：{capability} 依赖尚未实现的底层能力"
        f"（{PLANNED_IN[capability]}）。",
        err=True, fg=typer.colors.YELLOW)
    raise typer.Exit(code=2)


def _open_or_exit(want_write: bool = False):
    try:
        return open_project(resolve_project_path(_project),
                            want_write=want_write, heartbeat=False)
    except ProjectError as e:
        typer.secho(str(e), err=True, fg=typer.colors.RED)
        raise typer.Exit(code=1) from e


@app.callback()
def _callback(
    project: Annotated[
        Optional[Path], typer.Option(
            "--project", "-p",
            help="项目目录（默认 cwd，或环境变量 SNOWEL_PROJECT）")] = None,
) -> None:
    global _project
    _project = project


@app.command()
def init() -> None:
    """初始化 Snowel 项目（建 snowel.db 并迁移 schema）。"""
    from snowel_core.api import SnowelAPI

    p = resolve_project_path(_project)
    if (p / "snowel.db").exists():
        typer.secho(f"项目已存在：{p / 'snowel.db'}（迁移幂等）",
                    fg=typer.colors.YELLOW)
    SnowelAPI.init_project(p)
    typer.echo(f"已初始化项目：{p}")


@app.command()
def status() -> None:
    """显示项目状态：租约模式、提案队列、图谱统计。"""
    ctx = _open_or_exit(want_write=False)
    try:
        counts: dict[str, int] = {}
        for row in ctx.api.proposals.list():
            counts[row["status"]] = counts.get(row["status"], 0) + 1
        stats = ctx.api.graph_stats()
        mode = "只读（另一进程持有写租约）" if ctx.readonly else "可写"
        typer.echo(f"项目：{ctx.project_path}（{mode}）")
        typer.echo("提案：" + " / ".join(
            f"{k} {counts.get(k, 0)}"
            for k in ("pending", "stale", "confirmed", "rejected", "voided")))
        typer.echo(
            f"图谱：节点 {stats['nodes']}（" + " / ".join(
                f"{t} {n}" for t, n in stats["nodes_by_type"].items())
            + f"）· 边 {stats['edges']}")
        typer.echo("流程：未接线（阶段三 flow 模块）")
    finally:
        ctx.close()


@app.command()
def backup(
    out: Annotated[
        Optional[Path], typer.Option(
            "--out", "-o", help="备份文件路径（默认项目目录内带时间戳）")] = None,
) -> None:
    """SQLite 一致性备份（VACUUM INTO，可恢复出等价项目库）。"""
    ctx = _open_or_exit(want_write=False)
    try:
        out = out or ctx.project_path / (
            f"snowel-backup-{_dt.datetime.now():%Y%m%d-%H%M%S}.db")
        try:
            ctx.api.backup(out)
        except FileExistsError as e:
            typer.secho(f"备份文件已存在，拒绝覆盖：{out}",
                        err=True, fg=typer.colors.RED)
            raise typer.Exit(code=1) from e
        typer.echo(f"已备份：{out}")
    finally:
        ctx.close()


@app.command()
def export() -> None:
    """导出项目（Markdown/txt）——未接线。"""
    _not_wired("export")


@app.command()
def seal() -> None:
    """封卷（冻结线）——未接线。"""
    _not_wired("seal")


def main() -> None:
    app()
```

- [ ] **Step 4: 跑测试确认通过**

Run: `pytest tests/shell/test_cli.py -v`
Expected: 7 PASS

- [ ] **Step 5: 提交**

```bash
git add shell/src/snowel/cli.py tests/shell/test_cli.py
git commit -m "feat(shell): CLI management commands"
```

### Task 6: 跨壳租约集成 + 测试索引收尾

**Files:**
- Test: `tests/shell/test_lease_integration.py`（Create）
- Modify: `tests/README.md`

**Interfaces:**
- Consumes: `open_project`（Task 3）、`build_mcp`（Task 4）。
- Produces: 无（验收性任务）。

- [ ] **Step 1: 写集成测试（TC-SH-04/05 壳层完整版）**

```python
# tests/shell/test_lease_integration.py
"""跨壳租约行为（TC-SH-04/05）：降级只读、崩溃恢复、心跳保活。"""
import time

import pytest

from snowel_core.api import SnowelAPI
from snowel.project import ProjectError, open_project

pytestmark = pytest.mark.anyio


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
def project(tmp_path):
    SnowelAPI.init_project(tmp_path)
    return tmp_path


def test_readonly_blocks_write_allows_read(project):  # TC-SH-04
    a = open_project(project, heartbeat=False)
    b = open_project(project, heartbeat=False)
    try:
        assert a.readonly is False and b.readonly is True
        with pytest.raises(ProjectError, match="只读"):
            b.require_write()
        assert b.api.graph_stats()["nodes"] == 0  # 读全部正常
    finally:
        b.close()
        a.close()


def test_lease_recoverable_after_crash(project):  # TC-SH-05：心跳停 = 进程死
    a = open_project(project, stale_after=0.5, heartbeat=False)
    assert a.readonly is False
    time.sleep(0.7)  # 无心跳 → 过期
    b = open_project(project, stale_after=0.5, heartbeat=False)
    try:
        assert b.readonly is False  # 可抢，无永久锁死
    finally:
        b.close()
    a.close()  # a 已失租：close 的 release 按 holder 定向，为 no-op


async def test_mcp_write_blocked_by_cli_holder(project):  # TC-SH-04 跨壳
    from mcp.shared.memory import create_connected_server_and_client_session

    from snowel.mcp_server import build_mcp

    blocker = open_project(project, heartbeat=False)  # CLI/他进程持租约
    ctx = open_project(project)  # MCP 实例：抢不到 → readonly
    try:
        assert ctx.readonly is True
        mcp = build_mcp(ctx)
        async with create_connected_server_and_client_session(
                mcp._mcp_server) as client:
            res = await client.call_tool(
                "snowel_advanced", {"op": "rebuild"})
            assert res.isError  # 写类操作被拒
            ok = await client.call_tool("snowel_status", {})
            assert not ok.isError  # 读操作正常
    finally:
        ctx.close()
        blocker.close()
```

- [ ] **Step 2: 跑测试确认通过（本任务为验收性测试，实现已在 Task 3/4 就位）**

Run: `pytest tests/shell/test_lease_integration.py -v`
Expected: 3 PASS

- [ ] **Step 3: 登记 tests/README.md**

§1 表追加一行：

```markdown
| `shell/`（test_project / test_mcp_server / test_cli / test_lease_integration） | 壳包 `snowel`（project.py/cli.py/mcp_server.py） | TC-SH-01/02/04/05/06、TC-SH-03 子集、TC-SH-07（status/backup；export 豁免） |
```

§2 运行节补充安装命令：`pip install -e . -e ./shell`。

- [ ] **Step 4: 全量回归**

Run: `pytest -v`
Expected: 全 PASS（core 37 + 壳新增约 23）

- [ ] **Step 5: 提交**

```bash
git add tests/shell/test_lease_integration.py tests/README.md
git commit -m "test(shell): cross-shell lease integration and test index"
```

---

## 5. 执行交接

计划批准后交 **dev-workflow** skill 执行：worktree 隔离 + feat 分支、ledger 两段制、控制器纪律、收尾清单（终审 → 修复波 → 合并 dev-1.0.0 → 归档 ledger 至本目录 → 更新 AGENTS.md 阶段指针 → 推送）。PR 时机仍为 v1.0.0 里程碑（用户发话）。

## 6. 执行结果（执行后由收尾流程回填）

- 待回填：提交范围、测试计数、终审发现、新挂账。
