// 后端 API 薄封装（web_server.py 面）：JSON 解析，非 2xx 抛 Error（取响应 detail）
import { useEffect, useState } from 'react'

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(path, init)
  if (!res.ok) {
    let detail = ''
    try {
      const body = await res.json()
      detail = body?.detail ?? ''
    } catch {
      // 非 JSON 错误体，回落状态文本
    }
    throw new Error(detail || `请求失败（${res.status} ${res.statusText}）`)
  }
  return res.json() as Promise<T>
}

export const api = {
  get<T>(path: string): Promise<T> {
    return request<T>(path)
  },
  post<T>(path: string, body?: unknown): Promise<T> {
    return request<T>(path, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: body === undefined ? undefined : JSON.stringify(body),
    })
  },
}

export interface UseApiResult<T> {
  data: T | null
  loading: boolean
  error: string | null
}

// 简易数据获取 hook（ui-design-01 §5.1）：loading 骨架屏态 / error 态
export function useApi<T = unknown>(path: string): UseApiResult<T> {
  const [data, setData] = useState<T | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    setError(null)
    api.get<T>(path).then(
      (res) => {
        if (cancelled) return
        setData(res)
        setLoading(false)
      },
      (err: unknown) => {
        if (cancelled) return
        setError(err instanceof Error ? err.message : String(err))
        setLoading(false)
      },
    )
    return () => {
      cancelled = true
    }
  }, [path])

  return { data, loading, error }
}
