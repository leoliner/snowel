# SDD ledger — plan: docs/v1.0.0/plans/2026-08-24-mcp-cli-shell/plan.md

> 2026-08-24 执行完毕归档。live ledger 原位于 worktree `.superpowers/sdd/plan/progress.md`（git 忽略），收尾时迁移为本文件随 git 提交。

## 执行总览

- 分支 feat/mcp-cli-shell（worktree 隔离，已合并清理），9 提交 f4e9879..593aa9b + merge commit 70b1b35，6 任务 + 终审修复波，合并后全量 69/69 通过（core 37 + shell 32）。
- 任务评审：Task 1/2/3/6 一次通过；Task 4/5 各 1 轮修环（各 1 个 Important，均 ADDRESSED 复审闭环）。终审（全分支）判 With fixes：1 Important（main() 不释放租约）+ 1 个 fix-before-merge 测试缺口，修复波 593aa9b 一次解决，定向复审 2/2 ADDRESSED。
- 交付：`shell/` 发行单元（包名 snowel，入口 `snowel` CLI + `snowel-mcp` MCP server）、core 三处最小扩展（L3 修复 + graph_stats/backup 门面）、跨壳租约集成测试、tests/README 登记。

## Ruling 裁决记录（决策—理由—若错的成本）

- Ruling: workspace 目录以脚本口径 `.superpowers/sdd/plan/` 为准（手动建的按日期目录已迁并删除）——若错成本：断点续传脚本找不到 ledger，可人工从 git log 恢复。
- Ruling: graph_stats 不带 active=1 过滤（plan-mandated）——status 面板语义取物理图全量计数，"生效图"语义由 state_at 承担；若错成本：status 计数含失活节点，展示层面可接受，回写环计划接线 status 细化时可再分列。
- Ruling: backup exists() 与 VACUUM INTO 间 TOCTOU（plan-mandated）——单用户+单写者租约模型下无并发覆盖触发面，维持现状；若错成本：极端时序下覆盖已有备份（拒覆盖检查先行的常规路径不受影响）。
- Ruling: 计划缺陷修正——holder 串 `snowel@{host}:{pid}` 同进程不唯一，core.lease.acquire 同 holder 幂等重入致同进程双 ctx 错拿写权；最小修正 `:{next(itertools.count())}` 序号后缀（评审核验：原子、release/renew 定向语义无副作用）——若错成本：holder 串展示变化，接口不变。
- Ruling: mcp 2.0.0 移除 FastMCP，批准跨任务单行修复 shell/pyproject.toml `mcp>=1.2,<2`——若错成本：锁 1.x，mcp 2 迁移留给后续显式计划。
- Ruling: brief 代码直接返回 sqlite3.Row 被 pydantic 序列化为字符串（计划缺陷），最小修正 `_rows()` 工具边界转换（评审核验：无残留 Row 泄漏路径，测试零改动）——若错成本：无，行为改善。
- Ruling: 测试输出 1 条 pydantic_settings IncompleteFieldDefinitionWarning——mcp SDK 1.29 内部 lifespan 前向引用，控制器核实非我方代码，接受为第三方噪音不修；若错成本：测试输出非 pristine，已知可解释。
- Ruling: 计划缺陷——CLI 实现把 --project 只放 callback 而 brief 测试全部后置（click 组级选项不允许后置），以测试为契约修正为命令级共享别名 ProjectOpt 重复声明（前置用法兼容）——若错成本：选项声明重复一次，行为符合用户契约。
- Ruling: status 文案"只读（另一进程持有写租约）"在 want_write=False 下恒假（plan-mandated，评审核实），批准中性文案"只读（CLI 不抢写租约）"单行修正——若错成本：无，诊断诚实性改善。
- Ruling: 终审发现 main() 绕过 ctx.close()（计划缺陷忠实落地）+ 启动 ProjectError 裸 traceback，批准 try/finally + 单行 stderr 转译修复——若错成本：无，消除优雅停机后约 30s 写锁残留窗口。

## Parked（挂账，下游计划 preflight 必须携带）

| # | 问题 | 位置 | 承接计划 | 处理要求 |
|---|---|---|---|---|
| L1 | `groups.validate` 对畸形 `_schema` 版本串抛 ValueError，违背 D3 降级 | ontology/groups.py | 回写环/级联检查计划（继承未变） | 补 try/except，畸形串归入 version_mismatch 警告 |
| L2 | `completeness.derive(props)` 无测试且签名漂移 | ontology/completeness.py | 接线 completeness 的计划（继承未变） | 先补测试统一签名再接线 |
| L4 | `descendants` 不做边时效过滤；kinds 参数未消费 | storage/queries.py | 级联检查计划（继承未变） | 依赖反查时按需补 |
| **L5（新）** | 心跳失租后 `ctx.readonly` 不翻转：A 端心跳线程停摆超 stale_after 且租约被 B 抢走后，A 的 require_write 仍放行，写直接落库（双写窗口） | shell/src/snowel/project.py | 回写环计划（多端并发接线时） | 写路径加租约校验或 readonly 状态回写；v1 单用户触发面极窄 |
| L3 | ~~api.open() 不校验库存在~~ | api.py | **本计划已修复关闭**（1262afb） | — |

## 随行小项（下游 preflight 参考，不强制）

- MCP：`snowel_status` 的 lease_holder 只报自己（readonly 时 None），不报当前持有者——需 core 只读门面，回写环计划可顺带。
- MCP：mcp_server 未知 action 错误信息可达性（缺 proposal_id 时先报参数错）；文件首行路径注释（仓库既有约定，保留）。
- CLI：export/seal 接受 --project 但不消费（not_wired 桩必要行为，接线时消解）；backup 秒级时间戳同秒重跑撞拒覆盖；init() 丢弃 init_project 返回的 api 未 close（一次性进程无实害）。
- core：graph_stats 生效图分列（active 过滤）待回写环接线 status 时定；backup 不建父目录、失败可能残留半写文件。
- 测试：edges/descendants 的 `_rows` 转换无回归用例（级联检查计划接线 descendants 时必补）；test_heartbeat 墙钟余量 3 续租周期（CI 抖动再放宽）；test_lease_integration 失败路径句柄在 finally 外。
- 发布债：shell 单独 `pip install ./shell` 需 snowel-core 已在索引（纯名依赖）——发布时 core 与壳需同步发包；mcp 锁 `<2`，2.x 迁移是显式计划。
- 文档债：根 README 无安装节（分支前已如此）；plan §3 "README.md" 与 Task 6 权威清单 tests/README.md 的口径差异属计划缺陷，已按后者执行。

## 终审修复波（593aa9b）

- Important：mcp_server.main() 优雅停机不释放租约（客户端断开后租约残留至 stale_after，约 30s 写锁窗口）+ 启动 ProjectError 裸 traceback——修复：open 包第一段 try（ProjectError → 单行 stderr + SystemExit(1)），build_mcp + mcp.run 包第二段 try/finally ctx.close()。
- fix-before-merge：CLI `--project` 解析链（前置用法 / -p 别名 / SNOWEL_PROJECT）无自动化测试——修复：test_cli.py 补三条正向用例（回归时 resolve 落 cwd → exit 1，断言必失败）。
- 定向复审：2/2 ADDRESSED，无新破坏。
