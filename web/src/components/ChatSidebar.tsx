// 聊天侧栏（ui-design-01 §5.7/§5.8 + W6）：消息气泡（user 右 accent / assistant 左），
// Enter 发送 / Shift+Enter 换行；SSE 事件到达即渲染——tool_call 卡片 + spinner、
// tool_result 就地更新成败、reply 打字机 20ms/字渐显（纯前端，W6）；done 后
// proposal_ids>0 → accent 链接"已入队 N 个提案 → 去确认"（onGoProposals 回调）；
// error 事件/网络失败 → 红条 + 重试；流进行中"中断"按钮（abort，Esc 同效）。
import { useEffect, useRef, useState } from 'react'
import { streamSSE } from '../sse'
import type { ChatEvent } from '../types'

// 对话历史条目（与后端 _validate_history 形状一致）
interface ChatMessage {
  role: 'user' | 'assistant'
  text: string
}

// 当轮流的工具卡片（tool_result 就地更新 ok/summary）
interface LiveTool {
  key: number
  tool: string
  ok: boolean | null
  summary: string | null
}

interface LiveState {
  tools: LiveTool[]
  reply: string
  visible: number
}

const EMPTY_LIVE: LiveState = { tools: [], reply: '', visible: 0 }
const TYPE_SPEED_MS = 20 // 打字机 20ms/字（ui-design-01 §2.3/§5.8）

interface ChatSidebarProps {
  readonly?: boolean
  onGoProposals?: () => void
}

export default function ChatSidebar({ readonly = false, onGoProposals }: ChatSidebarProps) {
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [input, setInput] = useState('')
  const [live, setLive] = useState<LiveState>(EMPTY_LIVE)
  const [streaming, setStreaming] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [queuedIds, setQueuedIds] = useState<string[]>([])
  const abortRef = useRef<AbortController | null>(null)
  // 流结束回调（then/catch）读取最终 reply 与失败标记，绕开闭包旧值
  const replyRef = useRef('')
  const failedRef = useRef(false)

  // 打字机渐显（W6 纯前端）：reply 全量到达后 20ms/字揭示；卸载/流变化即停
  useEffect(() => {
    if (live.reply.length === 0) return
    const timer = setInterval(() => {
      setLive((l) => {
        if (l.visible >= l.reply.length) {
          clearInterval(timer)
          return l
        }
        return { ...l, visible: l.visible + 1 }
      })
    }, TYPE_SPEED_MS)
    return () => clearInterval(timer)
  }, [live.reply])

  // Esc 中断聊天流（ui-design-01 §5.7）
  useEffect(() => {
    if (!streaming) return
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') abortRef.current?.abort()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [streaming])

  const handleEvent = (ev: ChatEvent) => {
    switch (ev.type) {
      case 'tool_call':
        setLive((l) => ({
          ...l,
          tools: [...l.tools, { key: l.tools.length, tool: ev.tool, ok: null, summary: null }],
        }))
        break
      case 'tool_result':
        // 就地更新：匹配同工具名最近一条未决卡片
        setLive((l) => {
          let matched = false
          return {
            ...l,
            tools: l.tools.map((t) => {
              if (!matched && t.tool === ev.tool && t.ok === null) {
                matched = true
                return { ...t, ok: ev.ok, summary: ev.summary }
              }
              return t
            }),
          }
        })
        break
      case 'reply':
        replyRef.current += ev.text
        setLive((l) => ({ ...l, reply: l.reply + ev.text }))
        break
      case 'done':
        setQueuedIds(ev.proposal_ids ?? [])
        break
      case 'error':
        failedRef.current = true
        setError(ev.text)
        break
    }
  }

  // 流正常收束：reply 非空才入历史（error 回合不追加部分内容）
  const finalize = () => {
    setStreaming(false)
    abortRef.current = null
    // 先取值再清空：setMessages 的 updater 惰性执行，不可在回调里读可变 ref
    const text = replyRef.current
    if (!failedRef.current && text) {
      setMessages((m) => [...m, { role: 'assistant', text }])
    }
    failedRef.current = false
    replyRef.current = ''
    setLive(EMPTY_LIVE)
  }

  const fail = (err: unknown) => {
    setStreaming(false)
    abortRef.current = null
    failedRef.current = false
    replyRef.current = ''
    setLive(EMPTY_LIVE)
    if ((err as Error)?.name === 'AbortError') return // 用户中断：静默收束，保留现场
    setError(err instanceof Error ? err.message : String(err))
  }

  const run = (text: string, history: ChatMessage[]) => {
    setError(null)
    setStreaming(true)
    setLive(EMPTY_LIVE)
    setQueuedIds([])
    replyRef.current = ''
    failedRef.current = false
    const controller = new AbortController()
    abortRef.current = controller
    streamSSE('/api/chat/stream', { message: text, history }, handleEvent, controller.signal)
      .then(finalize)
      .catch(fail)
  }

  const send = () => {
    const text = input.trim()
    if (!text || streaming) return
    setMessages((m) => [...m, { role: 'user', text }])
    setInput('')
    // 闭包里的 messages 尚不含本条消息——正是此前轮次的历史
    run(text, messages)
  }

  const retry = () => {
    const last = messages[messages.length - 1]
    if (!last || last.role !== 'user') return
    // 重试同一消息：历史去掉尾部已入列的那条 user 消息
    run(last.text, messages.slice(0, -1))
  }

  const abort = () => abortRef.current?.abort()

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    // 中文输入法组合态（isComposing）下 Enter 是确认候选词，不得触发发送
    if (e.key === 'Enter' && !e.shiftKey && !e.nativeEvent.isComposing) {
      e.preventDefault()
      send()
    }
  }

  return (
    <div data-testid="chat-sidebar" className="flex h-full flex-col">
      {/* 消息流（§2.1：user 右 accent / assistant 左） */}
      <div className="min-h-0 flex-1 overflow-y-auto p-3">
        <div className="flex flex-col gap-2">
          {messages.map((m, i) => (
            <div
              key={i}
              className={`max-w-[85%] whitespace-pre-wrap rounded-input px-2 py-1.5 text-sm leading-relaxed ${
                m.role === 'user'
                  ? 'self-end bg-accent text-base'
                  : 'self-start border border-border bg-raised text-primary'
              }`}
            >
              {m.text}
            </div>
          ))}

          {/* 流进行中：tool 卡片（spinner → 就地成败）+ reply 打字机 */}
          {streaming && (
            <div className="flex flex-col gap-1">
              {live.tools.map((t) => (
                <div
                  key={t.key}
                  className="max-w-[85%] self-start rounded-input border border-border bg-raised px-2 py-1.5 text-xs leading-relaxed"
                >
                  {t.ok === null ? (
                    <span className="flex items-center gap-2 text-muted">
                      <span
                        data-testid="chat-spinner"
                        aria-hidden
                        className="inline-block h-3 w-3 animate-spin rounded-full border border-border border-t-accent"
                      />
                      调用 {t.tool}…
                    </span>
                  ) : t.ok ? (
                    <span className="text-ok">调用 {t.tool} 成功：{t.summary}</span>
                  ) : (
                    <span className="text-danger">调用 {t.tool} 失败：{t.summary}</span>
                  )}
                </div>
              ))}
              {live.reply && (
                <div className="max-w-[85%] self-start whitespace-pre-wrap rounded-input border border-border bg-raised px-2 py-1.5 text-sm leading-relaxed text-primary">
                  {live.reply.slice(0, live.visible)}
                </div>
              )}
            </div>
          )}

          {/* done 后入队提案链接（§5.8） */}
          {queuedIds.length > 0 && (
            <button
              type="button"
              onClick={onGoProposals}
              className="self-start rounded-chip bg-accent/15 px-2 py-1 text-sm text-accent hover:brightness-110"
            >
              已入队 {queuedIds.length} 个提案 → 去确认
            </button>
          )}
        </div>
      </div>

      {/* 错误红条 + 重试（§5.3） */}
      {error && (
        <div
          role="alert"
          className="mx-3 mb-1 flex items-center justify-between gap-2 rounded-input bg-danger/15 px-2 py-1 text-xs text-danger"
        >
          <span className="min-w-0 truncate">{error}</span>
          <span className="flex shrink-0 items-center gap-1">
            <button
              type="button"
              onClick={retry}
              className="rounded px-1 hover:bg-danger/10"
            >
              重试
            </button>
            <button
              type="button"
              aria-label="关闭错误"
              onClick={() => setError(null)}
              className="rounded px-1 hover:bg-danger/10"
            >
              ×
            </button>
          </span>
        </div>
      )}

      {/* 输入区（§5.7：Enter 发送 / Shift+Enter 换行） */}
      <div className="shrink-0 border-t border-border p-2">
        <textarea
          aria-label="聊天消息"
          value={input}
          disabled={readonly || streaming}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="说出你的想法…（Enter 发送，Shift+Enter 换行）"
          rows={2}
          className="w-full resize-none rounded-input border border-border bg-raised px-2 py-1 text-sm text-primary placeholder:text-muted focus:border-accent disabled:opacity-40"
        />
        <div className="mt-1 flex items-center justify-between">
          <span className="text-xs text-muted">Shift+Enter 换行</span>
          {streaming ? (
            <button
              type="button"
              onClick={abort}
              className="rounded-btn border border-warn px-3 py-1 text-sm text-warn hover:bg-warn/10"
            >
              中断
            </button>
          ) : (
            <button
              type="button"
              disabled={readonly || input.trim() === ''}
              onClick={send}
              className="rounded-btn bg-accent px-3 py-1 text-sm text-base hover:brightness-110 disabled:cursor-not-allowed disabled:opacity-40"
            >
              发送
            </button>
          )}
        </div>
      </div>
    </div>
  )
}
