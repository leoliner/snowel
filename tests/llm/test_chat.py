# tests/llm/test_chat.py
import json

from snowel_core.llm import chat

from tests.conftest import FakeBackend


def _seed(api):
    api.proposals.create("t", {"facts": [
        {"fact": "node", "id": "m1", "types": ["Mechanism"],
         "name": "积分兑换", "props": {"mechanism": {"level": 3}}}]})
    # 直接确认种子（绕过级联面，聚焦代理协议）


def test_chat_tool_loop_and_reply(api):
    _seed(api)
    fake = FakeBackend([
        json.dumps({"tool": "generate", "args": {
            "artifact_type": "premise",
            "extra": {"idea": "无限流轮回游戏"}}}, ensure_ascii=False),
        json.dumps({"draft": "无限流轮回游戏：主角在循环中觉醒。",
                    "facts": [], "appeared": []}, ensure_ascii=False),  # 内部生成响应
        json.dumps({"reply": "已为你生成前提提案，请在右侧面板查看确认。"},
                   ensure_ascii=False),
    ])
    out = api.chat("帮我想个无限流前提", backend=fake)
    kinds = [e["type"] for e in out["events"]]
    assert kinds == ["tool_call", "tool_result", "reply"]
    assert out["events"][0]["tool"] == "generate"
    assert out["events"][1]["ok"] is True
    assert len(out["proposal_ids"]) == 1                  # 提案入队，未确认
    assert api.proposals.get(out["proposal_ids"][0])["status"] == "pending"
    # 流式版：逐事件产出，末事件 done 携带 proposal_ids（W6）
    events = list(api.chat_stream("再想一个", backend=FakeBackend([
        json.dumps({"reply": "好的。"}, ensure_ascii=False)])))
    assert events[-1]["type"] == "done"
    assert events[-1]["proposal_ids"] == []


def test_chat_query_tool_and_turn_cap(api):
    _seed(api)
    # 队列恰好 8 条（7 合法 + 1 非法）：若上限回归为 9 轮、或非法 JSON 不计轮，
    # 第 9 次 generate 会撞空队列（IndexError）→ 红
    fake = FakeBackend([
        json.dumps({"tool": "query", "args": {
            "kind": "find", "types": ["Mechanism"]}}, ensure_ascii=False),
        "这不是合法JSON",                                   # 非法 → 错误观察回注
    ] + ['{"tool": "query", "args": {"kind": "find"}}'] * 6)
    out = api.chat("查一下机制", backend=fake, max_turns=8)
    assert out["events"][-1]["type"] == "reply"            # 轮次耗尽强制收束
    assert len(fake.calls) == 8                            # 恰 8 轮（非法 JSON 计一轮）
    # 7 次工具轮 + 1 次非法轮 = 8 轮；非法轮不产 tool_call 事件
    assert sum(1 for e in out["events"] if e["type"] == "tool_call") == 7
    assert all(e["type"] != "tool_call" or e["tool"] != "confirm"
               for e in out["events"])                     # 确认类永不在白名单
