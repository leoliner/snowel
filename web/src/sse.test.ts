import { afterEach, describe, expect, it, vi } from 'vitest'
import { streamSSE } from './sse'
import type { ChatEvent } from './types'

// SSE 帧编码（与后端 _sse 一致：`data: {json}\n\n` 每事件一行）
function sseFrame(event: unknown): string {
  return `data: ${JSON.stringify(event)}\n\n`
}

const toolCall: ChatEvent = { type: 'tool_call', tool: 'generate', args: { artifact_type: 'scene' } }
const reply: ChatEvent = { type: 'reply', text: '好的' }

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('streamSSE（fetch 流式 SSE 行解析，W6/T8）', () => {
  it('两帧按序解析为事件，POST 头与 body 正确', async () => {
    const fetchMock = vi.fn()
    const encoder = new TextEncoder()
    fetchMock.mockResolvedValue({
      ok: true,
      body: new ReadableStream<Uint8Array>({
        start(controller) {
          controller.enqueue(encoder.encode(sseFrame(toolCall) + sseFrame(reply)))
          controller.close()
        },
      }),
    })
    vi.stubGlobal('fetch', fetchMock)

    const events: ChatEvent[] = []
    await streamSSE('/api/chat/stream', { message: 'hi', history: [] }, (e) => events.push(e))

    expect(events).toEqual([toolCall, reply])
    expect(fetchMock).toHaveBeenCalledWith('/api/chat/stream', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message: 'hi', history: [] }),
    })
  })

  it('非 2xx → 读取响应 detail 抛错', async () => {
    const fetchMock = vi.fn()
    fetchMock.mockResolvedValue({
      ok: false,
      status: 409,
      statusText: 'Conflict',
      text: async () => JSON.stringify({ detail: '只读会话：写租约由 web:1 持有' }),
    })
    vi.stubGlobal('fetch', fetchMock)

    await expect(streamSSE('/api/chat/stream', {}, () => {})).rejects.toThrow(
      '只读会话：写租约由 web:1 持有')
  })

  it('非 2xx 非 JSON 错误体：错误消息含原始响应文本（L22#6）', async () => {
    const fetchMock = vi.fn()
    fetchMock.mockResolvedValue({
      ok: false,
      status: 500,
      statusText: 'Internal Server Error',
      text: async () => '内部错误：生成失败（无 JSON）',
    })
    vi.stubGlobal('fetch', fetchMock)

    await expect(streamSSE('/api/chat/stream', {}, () => {})).rejects.toThrow(
      '内部错误：生成失败（无 JSON）')
  })
})
