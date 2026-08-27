# v1.0.0 范围扩容 Step 2：扩展包机制（方案 C 事件化挂载 + CLI 管理）

> 日期：2026-08-27。来源：范围增补 `requirements-addendum.md` §3.1 / §8（Step 2 行）——8 step 链第 2 步。
> 性质：功能实现计划——挂载语义已在 addendum §3.1 定稿（方案 C 状态机、载荷契约 `{name, version, source_path, schema_digest}`、卸载校验、错误隔离、升级不跟随均勿重开），本计划做工程拆解与实现级裁决。
> 上游恢复：`plans/2026-08-27-core-debt/ledger.md`（Step 1 归档，L24 由本步承接关闭）。

## 1. 背景与范围

| 项 | 内容 |
|---|---|
| 发现 | 双位置扫 `<root>/extensions/`（优先）与全局 `~/.snowel/extensions/`，同名项目内覆盖（TC-EX-01）；schema.json 必选、hooks.py 可选 |
| 挂载 | `api.mount_extension(name)`：单事务 `extension_mounted` 事件（薄载荷不带 schema 全文）→ 投影扩展包状态表 → 进程态注册（属性组入 `groups.register`、hooks 规则入 `engine.register`）（TC-EX-02 中途挂载零回溯） |
| 卸载 | `api.unmount_extension(name)`：事务前校验——属性组被活跃节点引用 → 拒绝并列引用节点；通过 → `extension_unmounted` 事件，数据保留、组字段降级 unmanaged（TC-EX-03） |
| hooks | `def register(registry): ...`（design §8 定死协议）：import 与执行均隔离，错误丢该包规则、警告，核心照常（TC-EX-04 同引擎跑 Violation、TC-EX-05 隔离） |
| 启动重载 | `open()`/`init_project()` 尾部重载：读状态表定位磁盘包重新注册；目录被手删 → 孤儿警告降级不崩；全局包 digest 变化 → 不自动跟随，警告提示显式 re-mount |
| CLI 管理（裁决 6 仅 CLI） | `snowel ext list / mount <name> / unmount <name> / status` 四命令 |
| minor 分摊 | conftest fastapi 面依赖条件化（core-only 环境可跑全部非 Web 测试） |

不在范围：预制无限流包与制作规范 skill 双落（Step 3，本步合成最小 fixture 充当测试素材）；Web/MCP 面（裁决 6：不做）；`pydantic_settings` 警告（L27，本步 preflight 裁决不携带，见 §3）。

## 2. Global Constraints

- 事件 append-only：新增 `extension_mounted`/`extension_unmounted` 两种 kind，禁止改写历史事件；重复 mount 同名包 = 再追加一条事件，投影 last-write-wins（升级 re-mount 的机制载体）。
- 领域逻辑只在 snowel-core：`src/snowel_core/extensions/` 新子包承载发现/解析/注册编排；CLI 壳只接线（`_open_or_exit` 模板复用），不含逻辑。
- 载荷上限：属性组 + 级联规则两类（裁决 11 修订）——生成偏好、文风、角色模板不做；registry 面 v1.0.0 只暴露 `rule()`。
- 每任务 TDD：先写失败测试再实现；conventional commits，每任务一提交。
- 新测试落 `tests/extensions/`（镜像 src 惯例）；`tests/README.md` 反向索引同步——grep 实证，防虚登记。
- 全量基线：dev-1.0.0 @ e388269，后端 280 + 前端 vitest 74 + build 绿。

## 3. Preflight 挂账裁决（同版本已归档 ledger 全量双查）

| 挂账 | 内容 | 裁决 | 去向 |
|---|---|---|---|
| L16 | Windows python.org 扩展加载崩 + 同步发包 | 不携带（环境/发布债） | Step 8 |
| **L24** | **TC-EX-01~05 扩展包机制全域（E4）** | **携带——本计划主体，完成后关闭** | Task 1–3 |
| L25 | 壳端暴露部分（Web 灵感/拍操作、MCP advanced） | 不携带 | Step 4 |
| L26 | chat 召回 20 有意上限（记录性） | 不动（勿当 bug 修） | — |
| L27 | pydantic_settings `IncompleteFieldDefinitionWarning`（'lifespan' 前向引用） | **不携带**——本步实测定位：警告源自第三方 pydantic_settings 库内部处理 uvicorn 生态模型的路径（非本项目代码），非一行可修，涉及依赖版本交互排查；从"顺手修"降级为专门时机处理 | 开放，后续小计划或 Step 7 终核顺手再评估 |
| minor 池 | conftest fastapi 条件化（本步分摊项） | 携带 | Task 4 |

任务间共享文件/接口冲突扫描见 §5 附表。

## 4. 计划级设计裁决（预登记 Ruling，执行期可依证修订）

| # | 裁决 | 理由 | 若错的成本 |
|---|---|---|---|
| R1 | （**2026-08-27 用户修订版**）schema.json = 标准 JSON Schema 外壳：`{"name", "version", "groups": {"<组名>": <该组的 JSON Schema 片段>}}`；挂载时以 `jsonschema` 库校验各片段合法性（**依赖进 core pyproject dependencies**），合法片段经类型映射（string→str/integer→int/number→float/boolean→bool/array(string)→list[str]，连同 required/enum/pattern）`pydantic.create_model` 动态构组注册——复用 groups.validate 四态全链路，`_schema="name@N"` 数据内嵌约定不变；不支持的高级 keyword 片段合法但不入模型时给出跳过字段警告；digest = sha256(schema.json 原文字节)；manifest 非法（缺 name/version、JSON 坏、片段校验败）视同缺失包跳过警告 | 用户裁决放开依赖；标准 JSON Schema 对包作者零学习成本，Step 3 制作规范 skill 直教标准语法；下游校验链路零改动 | 映射遗漏某常用 keyword → 在 mapping 处纯增量补 |
| R2 | hooks 协议照 design §8 字面 `register(registry)`：registry 仅 `rule(name, fn, tiers=("full",))` 方法转发 `engine.register`；错误隔离以**包**为单位——import 或任一条 rule 注册抛异常则该包已注册规则整体回滚（engine 新增 `unregister` 支持撤档），警告不上崩核心；同包 rule 批量先暂存后生效 | TC-EX-05 隔离语义的干净单位是包而非条；半挂载状态比全无更难推理 | 若要条级隔离改 collection 为逐条提交，数行 |
| R3 | 启动重载挂 core `open()`/`init_project()` 尾部（进程态填充，不触库不发事件）：读 extensions 状态表 mounted 清单 → discovery 定位 → digest 一致才激活注册；目录缺失 = 孤儿（状态保持 mounted、警告降级 unmanaged）；digest 不一致 = 升级不跟随（警告"显式 re-mount"，本次不激活）；reload 全程 try/except 吞错转警告——open 永不被扩展拖垮。readonly 会话同样激活（组校验正确性依赖注册表，且此路径不写库，F2 守卫不适用） | extract 校验/写入面在全端都要正确判定 managed/unmanaged；挂在 core 层三壳共享一份逻辑，C1 项目根本就有读写先例（mirror） | 若要求重载由壳择机触发（recover_derived_from 模式），把调用点外移即可——函数位置不动 |
| R4 | 卸载引用校验口径 = **active=1** 节点的 props 含该包任一组键即拒绝（`json_extract(props,'$.<group>') IS NOT NULL`），拒绝文案列引用节点 id（封顶展示 10 个 + 总数 N）；已失效节点的历史引用不拦截（retcon 可清）——addendum 字面"活跃节点" | 与 merge_beats 既有 active 口径同款；放宽到全量会把历史数据变卸载死锁 | 若要全量拦截，去掉 WHERE 条件一处 |
| R5 | mount 流程顺序：manifest 解析+组模型构建全成功 → 落事件+投影 → 进程态注册；hooks 失败不阻断挂载（返回值带 warnings，CLI 黄色呈现）——即"schema 有效的包必可挂，规则丢失只降级" | TC-EX-05 只要求不拖垮核心；挂载被 hooks 连坐会让包修复路径更绕（挂了才有 status 可查） | 若要 hooks 必须健康才能挂，mount 前置 dry-load 一行 |

## 5. 文件结构总表

| 文件 | 动作 | 任务 |
|---|---|---|
| `src/snowel_core/extensions/__init__.py` | 新子包 | T1 |
| `src/snowel_core/extensions/discovery.py` | PackManifest 数据类 + `parse_manifest(dir)`（schema.json→manifest+digest，含 jsonschema 片段合法性校验）+ `discover(root)` 双位置扫描覆盖 + 警告收集 | T1 |
| `pyproject.toml`（core） | dependencies 增 `jsonschema` | T1 |
| `src/snowel_core/extensions/mounting.py` | `build_group_models(manifest)`（create_model）+ `load_hooks(dir)`（隔离加载 registry 暂存）+ `reload(api)`（启动重载）+ 注册/注销编排 | T2 / T3 |
| `src/snowel_core/storage/schema.sql` | 新表 `extensions(name PK, status, version, source_path, schema_digest, updated_at)` | T2 |
| `src/snowel_core/storage/projector.py` | `HANDLERS["extension_mounted"/"extension_unmounted"]` 两 handler（upsert last-write-wins）+ rebuild DELETE 清单登记 | T2 |
| `src/snowel_core/ontology/groups.py` | 新 `unregister(name)` | T2 |
| `src/snowel_core/consistency/engine.py` | 新 `unregister(name)`（连 TIERS 撤档；供包级回滚复用） | T2 |
| `src/snowel_core/api.py` | 四门面：`mount_extension` / `unmount_extension` / `list_extensions` / `extensions_status`；`open()`/`init_project()` 尾部 reload 接线 | T2 / T3 |
| `shell/src/snowel/cli.py` | `ext` 子 app 四命令（list/mount/unmount/status） | T3 |
| `tests/extensions/test_discovery.py` / `test_mounting.py` / `test_hooks.py` | 新域三件 | T1–T3 |
| `tests/conftest.py` | 第 13–25 行 create_app monkeypatch 块 try/except ImportError 条件化（心跳 fixture 本身空表 no-op 不动） | T4 |
| `tests/shell/test_web_server.py` | 顶部 `pytest.importorskip("snowel.web_server")` | T4 |
| `tests/README.md` | 新增 extensions 域行（反向索引 TC-EX-01–05） | T4 |

**共享文件冲突扫描**（顺序执行，后任务基于前任务提交）：

| 文件 | 触及任务 | 裁决 |
|---|---|---|
| `api.py` | T2（三门面写 + reload 接线）/T3（status/list 只读门面 + reload 补 hooks 分支） | 触及方法互不重叠；T3 在 T2 提交基础上补 hooks |
| `mounting.py` | T2（组注册/reload）/T3（load_hooks+回滚接线） | 同文件先后续写，无并行 |
| `projector.py`/`schema.sql`/`groups.py`/`engine.py` | 仅 T2 | 无冲突 |
| `conftest.py`/`test_web_server.py`/`README.md` | 仅 T4 | 无冲突 |
| `testcases.md` | **不改**——五例已在 §10、76 例口径不变、§11.1 E4 已锚 | 无文档动作（tests 反向索引足矣） |

## 6. 任务清单

### Task 1: 发现与解析（TC-EX-01 / TC-EX-05 schema 半）

**实现**（`discovery.py`）：
- `PackManifest`：`name, version, dir_path, scope("project"/"global"), schema_digest, raw(dict)`。
- `parse_manifest(dir) -> tuple[PackManifest, list[str]]`：schema.json 读出+json 解析+R1 校验（jsonschema 验片段合法性，合法者记录映射用关键字段）→ 合法返 manifest（digest 全程带上）；任何问题返 `(None, [警告...])`。
- `discover(root: Path | None) -> list[PackManifest]`：项目 `<root>/extensions/*` 与全局 `~/.snowel/extensions/*`（家目录展开），先扫全局后扫项目、同名后者覆盖前者；坏包剔除并汇入全局警告池。
- `~/.snowel/extensions/` 不存在时静默视为空（首次使用零摩擦，不算警告）。

**测试**（`tests/extensions/test_discovery.py`，fixture 用 tmp_path 现造合成包目录）：
```python
def test_discover_prefers_project_over_global(tmp_path, monkey_patch_home)  # TC-EX-01
    # 双位置同名 wuxia（version 不同）→ 恰一结果、scope=project
def test_parse_valid_manifest_roundtrip(...)      # 正常 manifest → name/version/digest 稳定
def test_missing_schema_skips_with_warning(...)   # TC-EX-05 schema 半：目录存在无 schema → 包剔除+警告
def test_invalid_manifest_variants_skip(...)      # JSON 坏 / 缺 version / 类型越表 → 各自跳过不崩
```

### Task 2: 事件面 + 投影 + 注册接线（TC-EX-02 / TC-EX-03 / 重载语义）

**实现**：
- `schema.sql` 增 `extensions` 表；projector 两 handler：`_extension_mounted`（upsert name→mounted 行，含 version/source_path/digest）、`_extension_unmounted`（upsert status=unmounted，字段保留终值）；rebuild DELETE 清单登记 `"extensions"`。
- `groups.unregister(name)`：`_registered.pop(name, None)`；`engine.unregister(name)`：`_RULES.pop` + TIERS 两档 discard。
- `build_group_models(manifest) -> dict[组名, type[BaseModel]]`：create_model（required 外字段全 Optional default None）。
- `api.mount_extension(name) -> dict{warnings}`（R5 顺序）：发现定位（找不到 ValueError）→ 建组模型成功 → `db.transaction` 内 append `extension_mounted {name, version, source_path(str), schema_digest}` + apply → 进程态注册组 + hooks（T2 阶段 hooks 恒空，T3 接线）→ 返回 warnings。
- `api.unmount_extension(name)`：状态表未 mounted → ValueError；事务前 R4 引用预查命中 → `ValueError("属性组 <g> 被 N 个活跃节点引用：<ids…>，先 retcon/迁移后卸载")`；通过 → 事务内 append `extension_unmounted {name}` + apply → groups.unregister 各组。
- `api.list_extensions()`：discover 全集 × 状态表 join → `{name, scope, mounted?, version, digest_matches?}`。
- `reload(api)`：状态表 mounted 清单逐包 → 磁盘定位 → 孤儿（目录无）/digest 异（R3）→ 警告不激活；正常 → 注册组（hooks 同 T3 接线）；整体 try/except 吞错。`open()`/`init_project()` 尾部各一行调用。

**测试**（`tests/extensions/test_mounting.py`）：
```python
def test_mount_midway_does_not_touch_existing_nodes(api)          # TC-EX-02
    # 先写节点（组字段走 unmanaged 警告照存）→ mount → 旧节点零变化、props 原样
    # 新写带组字段 → validate 四态 ok（managed 生效）
def test_unmount_blocked_by_active_reference(api)                 # TC-EX-03
    # mount → 写 active 节点含组字段 → unmount ValueError 且文案含节点 id；
    # events 总数不变（事务前拒绝）
def test_unmount_after_data_cleared_downgrades_to_unmanaged(api)
    # 引用节点 retcon/删后 unmount 成功：恰一条 extension_unmounted；
    # props 组字段原样保留；extract 校验回落 unmanaged 警告不再 invalid
def test_remount_updates_digest_last_write_wins(api)
    # mount → 篡改 schema.json → 再 mount → 状态表 digest 为新值、恰两条事件
def test_reload_orphan_warns_and_degrades(...)
    # mount → 手删目录 → 新 open() → 警告、组未注册、状态仍 mounted、核心可用
def test_reload_skips_upgraded_global_pack_until_remount(...)
    # 全局包装好后 mount → 替换内容(digest 变) → 新 open() → 不激活+提示 re-mount
def test_open_succeeds_with_broken_extensions_dir(...)
    # 项目 extensions/ 下塞坏包若干 → open() 不抛、内置功能如常（TC-EX-05 核心）
```

### Task 3: hooks 隔离加载 + CLI 四命令（TC-EX-04 / TC-EX-05 hooks 半）

**实现**：
- `Registry` 类：`rule(name, fn, tiers=("full",))` 暂存（暴露已存清单供回滚）；`load_hooks(dir) -> (list[(name,fn,tiers)], warnings)`：importlib 按路径加载 `hooks.py`（find_spec/sys.modules 防污染）→ 调 `register(registry)` → 返回暂存条目；import/exec 任一异常 → 空+警告。mount/reload 接线：暂存成功后逐条 `engine.register`（R2 包级回滚：中途败则先 `unregister` 已进引擎的同包条目再弃全部）。
- `api.extensions_status() -> list[{name, version, scope, healthy(bool), note}]`（挂载明细+孤儿/升版标注）。
- CLI `ext_app = typer.Typer(); app.add_typer(ext_app, name="ext")`：`list`（发现全集+挂载态+覆盖标记）、`mount NAME`/`unmount NAME`（want_write=True，warnings 黄色 secho）、`status`（挂载明细与健康标注）；全走 `_resolve`/`_open_or_exit` 模板，finally `ctx.close()`；错误 RED + Exit(1) 沿旧例。

**测试**：
```python
# tests/extensions/test_hooks.py
def test_hook_rule_runs_in_same_engine(...)                       # TC-EX-04
    # 合成包 hook 注册题材规则（如字段 A>0 则必须有字段 B）→ 写违规变更集
    # → analyze 出 Violation 带 rule 名；与内置规则混跑互不影响
def test_hooks_syntax_error_isolated(...)                         # TC-EX-05 hooks 半
    # hooks.py `raise RuntimeError` / 语法坏 → load 得空+警告；mount 仍成功（R5）
def test_rule_batch_rollback_on_partial_failure(...)
    # registry 注册第 2 条时抛 → 第 1 条也被撤（包级原子）
# tests/shell/（就近既有 cli 测试文件追加；无则新建 test_cli_ext.py）
def test_ext_list_shows_project_override_and_mount_state(...)     # TC-EX-01 出口可见
def test_ext_mount_unmount_lifecycle(...)                         # exit code 与输出断言
def test_ext_unmount_refusal_shows_reason(...)                   # TC-EX-03 呈现面
```

### Task 4: minor 包——conftest fastapi 条件化

| 子项 | 落点 | 修法 | 锚 |
|---|---|---|---|
| conftest create_app patch 条件化 | `tests/conftest.py:13-25` | 整块包 `try: import ... except ImportError:` 置 `_web_server_mod = None`，26 行 patch 同守卫 | 心跳线程清理 fixture 对空表天然 no-op，行为回归：全量测试不变绿→红 |
| test_web_server 收集跳过 | `tests/shell/test_web_server.py` 顶部 | `pytest.importorskip("snowel.web_server")` | core-only 环境 collect 报 skipped 非 error |
| core-only 验证 | 收尾动作 | 本机若无法低成本构造 fastapi 缺席态（当前 conda 全装），以"全量回归不变 + 代码评审守卫写法"代验证并在 ledger 如实记录 | — |

### 收尾（dev-workflow §7 全流程）

终审（全分支独立评审）→ 修复波 + 定向复审 → 合并 `dev-1.0.0`（合并结果主仓库全量重跑：pytest + vitest + `npm run build`；worktree 干活后先 editable 重装校正指向）→ 删 worktree/feat 分支 → ledger 归档 `plans/2026-08-27-ext-pack/ledger.md`（L24 关闭登记）→ 更新 AGENTS.md 阶段指针（Step 2 完成 → 下一步 Step 3；L24 移入已关闭清单）→ 推送 dev。

## 7. 执行参数

| 项 | 值 |
|---|---|
| 模式 | Subagent-Driven（4 任务，两席评审/任务；T1→T2→T3 串行依赖、T4 独立殿后；controller 不写码） |
| worktree | `D:\Code\snowel-ext-pack`（兄弟目录，从 dev-1.0.0 切） |
| 分支 | `feat/ext-pack` → merge --no-ff 回 `dev-1.0.0` |
| 测试基线 | 合并前 280/280 全绿为底（预计净增 ~18）+ 74/74 + build 绿；每任务聚焦跑，提交前全量 |
| 修环上限 | 5 轮（R1-3 原实现者，R4-5 换强模型新派） |
| Step 3 接口 | 本步合成 fixture 不迁移；预制包落地时 TC-EX fixture 主锚换 `extensions/infinite-flow/` 真包（addendum §3.2），另保留畸形最小 fixture |
