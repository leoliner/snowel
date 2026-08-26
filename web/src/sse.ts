// SSE 流式消费 util（W6/T8）：fetch POST + ReadableStream 逐块解码，
// 按 `\n\n` 切事件、剥 `data: ` 前缀 JSON.parse 逐条回调；
// 非 2xx 读响应 detail 抛 Error；signal 透传支持中断（AbortController）。
import type { ChatEvent } from './types'

export async function streamSSE(
  url: string,
  body: unknown,
  onEvent: (event: ChatEvent) => void,
  signal?: AbortSignal,
): Promise<void> {
  const res = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
    signal,
  })
  if (!res.ok) {
    // L22#6：先读全文再解析——res.json() 会消费 body，其后的 res.text() 必失败，
    // 原"回落响应文本"分支从未生效；detail 优先，非 JSON 错误体原样入错误消息
    const raw = await res.text().catch(() => '')
    let detail = ''
    try {
      const json: unknown = JSON.parse(raw)
      const d = (json as { detail?: unknown } | null)?.detail
      if (typeof d === 'string') detail = d
    } catch {
      // 非 JSON 错误体：raw 原样作为错误消息
    }
    throw new Error(detail || raw || `请求失败（${res.status} ${res.statusText}）`)
  }
  if (!res.body) throw new Error('响应无 body 流')
  const reader = res.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  for (;;) {
    const { done, value } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })
    let sep = buffer.indexOf('\n\n')
    while (sep !== -1) {
      const line = buffer.slice(0, sep).trim().replace(/^data:\s?/, '')
      buffer = buffer.slice(sep + 2)
      if (line) onEvent(JSON.parse(line) as ChatEvent)
      sep = buffer.indexOf('\n\n')
    }
  }
}
