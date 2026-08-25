# src/snowel_core/llm/chat.py
import json
from typing import Iterator

from .ports import get_backend

_OBSERVATION_LIMIT = 4000  # 观察回注上限（W1：结果 JSON 串截断）


def _require(args: dict, key: str):
    """缺参给模型可自纠的错误信息（KeyError 的 repr 对模型不可读）。"""
    if args.get(key) is None:
        raise ValueError(f"缺少必需参数 {key}")
    return args[key]


def _generate(api, args, backend) -> dict:
    pid = api.ai_generate(args.get("artifact_type"), args.get("locate"),
                          args.get("extra"), backend)
    return {"proposal_id": pid}


def _expand_chapter(api, args, backend) -> dict:
    pids = api.expand_chapter(_require(args, "chapter_id"), backend,
                              args.get("extra"))
    return {"proposal_ids": pids}


def _expand_volume(api, args, backend) -> dict:
    pids = api.expand_volume(_require(args, "volume_id"), backend,
                             args.get("extra"))
    return {"proposal_ids": pids}


def _query(api, args, backend) -> dict:
    kind = _require(args, "kind")
    if kind == "search":
        return api.search(args.get("q", ""), mode=args.get("mode", "hybrid"))
    if kind == "find":
        return api.find_nodes(name=args.get("name"), type=args.get("type"))
    if kind == "state_at":
        return api.state_at(args.get("story_order", 0))
    if kind == "node":
        return api.get_node(_require(args, "node_id"))
    raise ValueError(f"未知 query kind：{kind}（可用：search/find/state_at/node）")


def _register_foreshadow(api, args, backend) -> dict:
    pid = api.register_foreshadow(
        _require(args, "name"), _require(args, "planted_at"),
        origin=args.get("origin", "author"),
        payoff_beat=args.get("payoff_beat"), note=args.get("note", ""))
    return {"proposal_id": pid}


# 注册表键即工具白名单（§7.1 红线）：confirm/reject/seal/confirm_retcon 等
# 确认类动作永不在列——代理只可产出提案，确认动作一律落在结构化面板。
TOOLS: dict = {
    "generate": _generate,
    "expand_chapter": _expand_chapter,
    "expand_volume": _expand_volume,
    "query": _query,
    "register_foreshadow": _register_foreshadow,
}

_TOOL_CATALOG = """- generate：生成某层产物提案（产出待作者确认）。args: {"artifact_type": "premise|synopsis|summary|beat_sheet|characters|scene|prose|chapter_intent|microbeat_group|volume_theme|volume_acts", "locate": {...}（可省）, "extra": {...}（可省）}
- expand_chapter：小雪花展开章节，按序产三条提案（意图/微节拍/正文，待作者确认）。args: {"chapter_id": "章节点id", "extra": {...}（可省）}
- expand_volume：卷级展开，产两条提案（待作者确认）。args: {"volume_id": "卷节点id", "extra": {...}（可省）}
- query：只读查询，不改数据。args: {"kind": "search|find|state_at|node", ...}：search: {"kind": "search", "q": "关键词", "mode": "hybrid"（可省）}；find: {"kind": "find", "name": "名称"（可省）, "type": "类型"（可省）}；state_at: {"kind": "state_at", "story_order": 整数}；node: {"kind": "node", "node_id": "节点id"}
- register_foreshadow：注册伏笔（产出待作者确认）。args: {"name": "伏笔名", "planted_at": "节点id", "origin": "author"（可省）, "payoff_beat": "节点id"（可省）, "note": "备注"（可省）}"""


def _system_prompt(api) -> str:
    """系统提示：flow_state 摘要 + 工具白名单描述 + 单 JSON 对象输出约束。"""
    return "\n".join([
        "你是 Snowel 小说创作助手，通过工具调用辅助作者推进雪花流程创作。",
        "每次回复必须只输出一个 JSON 对象，二选一：",
        '  {"tool": "<工具名>", "args": {...}}   # 调用工具',
        '  {"reply": "<文本>"}                    # 直接回答',
        "工具执行结果会在下一条消息中回注给你。你只能产出提案；确认/否决/封卷等",
        "动作由作者在结构化面板操作——工具清单中不存在此类工具，也不要尝试调用。",
        "=== 当前流程状态 ===",
        json.dumps(api.flow_state(), ensure_ascii=False),
        "=== 可用工具（白名单） ===",
        _TOOL_CATALOG,
        "=== 输出约束 ===",
        "只输出单个 JSON 对象；不要输出 JSON 以外的任何内容，不要用 Markdown 围栏。",
    ])


def _parse_response(resp: str) -> dict:
    """容忍 Markdown 围栏的指令响应解析（与 parse_llm_json 同壳，键协议不同）。"""
    text = resp
    if "```" in resp:
        seg = resp.split("```")[1] if resp.count("```") >= 2 else resp
        first, _, rest = seg.partition("\n")
        if "{" not in first:
            seg = rest
        text = seg.strip()
    parsed = json.loads(text)
    if not isinstance(parsed, dict):
        raise ValueError("JSON 顶层必须是对象")
    return parsed


def _truncate(text: str) -> str:
    if len(text) <= _OBSERVATION_LIMIT:
        return text
    return text[:_OBSERVATION_LIMIT] + "…"


def _collect_pids(result) -> list[str]:
    if isinstance(result, dict) and "proposal_ids" in result:
        return list(result["proposal_ids"])
    if isinstance(result, dict) and "proposal_id" in result:
        return [result["proposal_id"]]
    return []


def _summary(result) -> str:
    """tool_result 人读摘要：提案类报 pid，查询类报完成。"""
    if isinstance(result, dict) and "proposal_ids" in result:
        return f"已产出提案 {', '.join(result['proposal_ids'])}（待作者确认）"
    if isinstance(result, dict) and "proposal_id" in result:
        return f"已产出提案 {result['proposal_id']}（待作者确认）"
    return "查询完成"


def _render_prompt(history, messages) -> str:
    """系统提示之外的正文：历史 + 本回合对话，末条为当前消息。"""
    transcript = [*(history or []), *messages]
    parts = [f"{m['role']}: {m['text']}" for m in transcript[:-1]]
    parts.append(f"=== 当前消息 ===\n{transcript[-1]['text']}")
    return "\n".join(parts)


def run_stream(api, message: str, history: list[dict] | None = None,
               backend=None, max_turns: int = 8) -> Iterator[dict]:
    """聊天代理回合流（W1/W6）：同步生成器逐事件 yield。

    流程：系统提示（flow_state 摘要 + 工具白名单）→ LLM → 解析 {"tool"/"reply"}；
    tool 执行 → yield 事件 + 观察（结果 JSON 截断 4000 字符）回注下一轮；
    reply → yield 后以 done 收束；轮次耗尽 → 强制 reply 收束 + done；
    非法 JSON → 以错误文本为观察回注（计一轮）。
    """
    backend = backend or get_backend(api._conn)
    messages = [{"role": "user", "text": message}]
    proposal_ids: list[str] = []
    turns = 0
    while turns < max_turns:
        turns += 1
        resp = backend.generate(_render_prompt(history, messages),
                                system=_system_prompt(api))
        messages.append({"role": "assistant", "text": resp})
        try:
            parsed = _parse_response(resp)
        except (ValueError, json.JSONDecodeError) as e:
            messages.append({"role": "user", "text":
                             f"你的上一条输出不是合法 JSON（{e}），请只输出一个 JSON 对象。"})
            continue
        if "reply" in parsed:
            yield {"type": "reply", "text": parsed["reply"]}
            break
        tool = parsed.get("tool")
        args = parsed.get("args") or {}
        if tool not in TOOLS:
            summary = (f"未知工具 {tool}（可用：{', '.join(sorted(TOOLS))}）。"
                       "确认/否决/封卷等动作不在工具清单中，请在结构化面板操作。")
            yield {"type": "tool_call", "tool": tool, "args": args}
            yield {"type": "tool_result", "tool": tool, "ok": False,
                   "summary": summary}
            messages.append({"role": "user", "text": json.dumps(
                {"ok": False, "summary": summary}, ensure_ascii=False)})
            continue
        try:
            result = TOOLS[tool](api, args, backend)
            ok, summary = True, _summary(result)
            observation = _truncate(json.dumps(result, ensure_ascii=False,
                                               default=str))
        except Exception as e:
            ok, summary = False, str(e)
            observation = json.dumps({"ok": False, "summary": summary},
                                     ensure_ascii=False)
        yield {"type": "tool_call", "tool": tool, "args": args}
        yield {"type": "tool_result", "tool": tool, "ok": ok, "summary": summary}
        if ok:
            proposal_ids.extend(_collect_pids(result))
        messages.append({"role": "user", "text": observation})
    else:
        yield {"type": "reply",
               "text": f"已达本轮对话轮次上限（{max_turns} 轮），对话收束。"
                       "如有需要，请继续输入新消息。"}
    yield {"type": "done", "proposal_ids": proposal_ids}


def run(api, message: str, history: list[dict] | None = None,
        backend=None, max_turns: int = 8) -> dict:
    """聚合门面（W6 非流式兼容口）：收齐除 done 外全部事件 + proposal_ids。"""
    events = []
    proposal_ids = []
    for ev in run_stream(api, message, history, backend, max_turns):
        if ev["type"] == "done":
            proposal_ids = ev["proposal_ids"]
        else:
            events.append(ev)
    return {"events": events, "proposal_ids": proposal_ids}
