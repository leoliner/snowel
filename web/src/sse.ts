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
    let detail = ''
    try {
      const json = await res.json()
      detail = typeof json?.detail === 'string' ? json.detail : ''
    } catch {
      // 非 JSON 错误体，回落响应文本
    }
    const text = detail || (await res.text().catch(() => ''))
    throw new Error(text || `请求失败（${res.status} ${res.statusText}）`)
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
