// 右栏工作区生成表单（E3 生成环）：artifact_type 七选一 + locate/extra JSON 附加字段
// （解析失败内联报错不提交）→ POST /api/generate → onGenerated 回调新提案 pid。
import { useState } from 'react'
import { api } from '../api'
import type { GenerateResult } from '../types'
import { ARTIFACT_LABELS, LAYERS } from './labels'

interface GenerateFormProps {
  readonly?: boolean
  onGenerated: (proposalId: string) => void
}

export default function GenerateForm({ readonly = false, onGenerated }: GenerateFormProps) {
  const [artifactType, setArtifactType] = useState<string>(LAYERS[0])
  const [locate, setLocate] = useState('')
  const [extra, setExtra] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  const parseJson = (text: string, field: string): Record<string, unknown> | undefined => {
    if (text.trim() === '') return undefined
    try {
      const parsed = JSON.parse(text)
      if (typeof parsed !== 'object' || parsed === null || Array.isArray(parsed)) {
        throw new Error(`${field} 须为 JSON 对象`)
      }
      return parsed as Record<string, unknown>
    } catch (err) {
      setError(err instanceof Error ? `${field} 不是合法 JSON：${err.message}` : `${field} 不是合法 JSON`)
      return undefined
    }
  }

  const submit = async () => {
    setError(null)
    const locateObj = parseJson(locate, 'locate')
    if (locateObj === undefined && locate.trim() !== '') return
    const extraObj = parseJson(extra, 'extra')
    if (extraObj === undefined && extra.trim() !== '') return
    setBusy(true)
    try {
      const res = await api.post<GenerateResult>('/api/generate', {
        artifact_type: artifactType,
        ...(locateObj !== undefined ? { locate: locateObj } : {}),
        ...(extraObj !== undefined ? { extra: extraObj } : {}),
      })
      onGenerated(res.proposal_id)
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    } finally {
      setBusy(false)
    }
  }

  return (
    <div
      data-testid="generate-form"
      className="flex flex-col gap-2 rounded-card border border-border bg-raised/40 p-3"
    >
      <div className="text-xs font-medium text-muted">生成提案</div>
      <div className="flex items-center gap-2">
        <label htmlFor="generate-artifact" className="shrink-0 text-xs text-muted">
          生成类型
        </label>
        <select
          id="generate-artifact"
          value={artifactType}
          disabled={readonly || busy}
          onChange={(e) => setArtifactType(e.target.value)}
          className="min-w-0 flex-1 rounded-input border border-border bg-raised px-2 py-1 text-sm text-primary focus:border-accent disabled:opacity-40"
        >
          {LAYERS.map((l) => (
            <option key={l} value={l}>
              {ARTIFACT_LABELS[l]}
            </option>
          ))}
        </select>
        <button
          type="button"
          disabled={readonly || busy}
          onClick={() => void submit()}
          className="shrink-0 rounded-btn bg-accent px-3 py-1 text-sm text-base hover:brightness-110 disabled:cursor-not-allowed disabled:opacity-40"
        >
          {busy ? '生成中…' : '生成提案'}
        </button>
      </div>
      <label htmlFor="generate-locate" className="text-xs text-muted">
        locate（JSON，可选——定位上下文）
      </label>
      <textarea
        id="generate-locate"
        value={locate}
        disabled={readonly || busy}
        onChange={(e) => setLocate(e.target.value)}
        placeholder='{"chapter": "ch1"}'
        className="min-h-10 resize-y rounded-input border border-border bg-raised px-2 py-1 font-mono text-xs text-primary placeholder:text-muted focus:border-accent disabled:opacity-40"
      />
      <label htmlFor="generate-extra" className="text-xs text-muted">
        extra（JSON，可选——附加要求）
      </label>
      <textarea
        id="generate-extra"
        value={extra}
        disabled={readonly || busy}
        onChange={(e) => setExtra(e.target.value)}
        placeholder='{"tone": "dark"}'
        className="min-h-10 resize-y rounded-input border border-border bg-raised px-2 py-1 font-mono text-xs text-primary placeholder:text-muted focus:border-accent disabled:opacity-40"
      />
      {error && (
        <div
          role="alert"
          className="flex items-center justify-between gap-2 rounded-input bg-danger/15 px-2 py-1 text-xs text-danger"
        >
          <span>{error}</span>
          <button
            type="button"
            aria-label="关闭错误"
            onClick={() => setError(null)}
            className="shrink-0 rounded px-1 text-danger hover:bg-danger/10"
          >
            ×
          </button>
        </div>
      )}
    </div>
  )
}
