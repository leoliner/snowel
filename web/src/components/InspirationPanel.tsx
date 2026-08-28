// 右栏提案 tab 灵感面板（TC-SH-09 / R4）：textarea 保存原话 → POST /api/inspirations，
// 列表渲染（序号 + text，created_event 稳定序）。挂 GenerateForm 之上——derive 联动
// 由 GenerateForm 自取同端点数据（灵感多选 chips → body.derive_from），本面板保存成功
// 后经 onSaved 触发 App refreshKey 递增，两侧列表同步重拉（ProposalPanel onMutated 同款流）。
import { useState } from 'react'
import { api, useApi } from '../api'
import type { InspirationItem } from '../types'
import { INSPIRATION_LABELS } from './labels'

interface InspirationPanelProps {
  readonly: boolean
  // App 全局刷新键：变化经 useApi 依赖重拉列表（保存成功后 App 递增）
  refreshKey: number
  // 保存成功回调（App 递增 refreshKey → 面板列表 + GenerateForm chips 同步刷新）
  onSaved: () => void
}

export default function InspirationPanel({
  readonly,
  refreshKey,
  onSaved,
}: InspirationPanelProps) {
  const { data } = useApi<InspirationItem[]>('/api/inspirations', refreshKey)
  const items = Array.isArray(data) ? data : []
  const [text, setText] = useState('')
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const doSave = async () => {
    if (readonly || saving || text.trim() === '') return
    setSaving(true)
    setError(null)
    try {
      await api.post<{ inspiration_id: string }>('/api/inspirations', { text })
      setText('')
      onSaved()
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    } finally {
      setSaving(false)
    }
  }

  return (
    <div
      data-testid="inspiration-panel"
      className="flex flex-col gap-2 rounded-card border border-border bg-raised/40 p-3"
    >
      <div className="text-xs font-medium text-muted">{INSPIRATION_LABELS.panelTitle}</div>
      <label htmlFor="inspiration-text" className="text-xs text-muted">
        {INSPIRATION_LABELS.input}
      </label>
      <textarea
        id="inspiration-text"
        value={text}
        disabled={readonly || saving}
        onChange={(e) => setText(e.target.value)}
        placeholder="随手记一句灵感原话…"
        className="min-h-10 resize-y rounded-input border border-border bg-raised px-2 py-1 text-sm text-primary placeholder:text-muted focus:border-accent disabled:opacity-40"
      />
      <div className="flex justify-end">
        <button
          type="button"
          disabled={readonly || saving || text.trim() === ''}
          onClick={() => void doSave()}
          className="rounded-btn bg-accent px-3 py-1 text-sm text-base hover:brightness-110 disabled:cursor-not-allowed disabled:opacity-40"
        >
          {saving ? '保存中…' : INSPIRATION_LABELS.save}
        </button>
      </div>
      {error && (
        <div
          role="alert"
          className="rounded-input bg-danger/15 px-2 py-1 text-xs text-danger"
        >
          {error}
        </div>
      )}
      {items.length > 0 && (
        <ul className="flex flex-col gap-1 border-t border-border pt-2">
          {items.map((item, i) => (
            <li
              key={item.id}
              data-testid="inspiration-item"
              className="flex min-w-0 items-baseline gap-1.5 text-xs"
            >
              <span className="shrink-0 text-muted">{i + 1}.</span>
              <span className="min-w-0 flex-1 truncate text-primary" title={item.text}>
                {item.text}
              </span>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
