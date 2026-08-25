// 左栏流程树（ui-design-01 §3/§5.2）：七层进度（done ✓ / todo ○ / current ● warn 高亮）
// + 卷→章两级树；无卷空态引导；卷行"封卷"危险操作（§5.4 二次确认，POST /api/seal）。
import { useState } from 'react'
import { api, useApi } from '../api'
import type { Chapter, FlowState, Volume } from '../types'
import { LAYER_LABELS, LAYERS } from './labels'
import ConfirmDialog from './ConfirmDialog'

interface FlowTreeProps {
  readonly?: boolean
  onSelectChapter?: (chapter: Chapter) => void
  // T12：外部刷新信号（聊天入队提案/确认否决后重拉流程状态）
  refreshKey?: number
}

export default function FlowTree({ readonly = false, onSelectChapter, refreshKey = 0 }: FlowTreeProps) {
  const { data, loading, error } = useApi<FlowState>('/api/flow', refreshKey)
  const [sealVolume, setSealVolume] = useState<Volume | null>(null)
  const [sealing, setSealing] = useState(false)
  const [sealError, setSealError] = useState<string | null>(null)

  if (loading) {
    return (
      <div data-testid="flow-skeleton" className="flex flex-col gap-2">
        <div className="skeleton h-6" />
        <div className="skeleton h-4" />
        <div className="skeleton h-4" />
        <div className="skeleton h-4" />
      </div>
    )
  }
  if (error) {
    return (
      <div role="alert" className="rounded-card bg-danger/15 px-3 py-2 text-sm text-danger">
        {error}
      </div>
    )
  }

  const layers = data?.layers
  const volumes = data?.volumes ?? []
  const current = data?.current_layer ?? null

  const doSeal = async () => {
    if (!sealVolume) return
    setSealing(true)
    setSealError(null)
    try {
      await api.post('/api/seal', { volume_id: sealVolume.id })
      setSealVolume(null)
    } catch (err) {
      setSealError(err instanceof Error ? err.message : String(err))
    } finally {
      setSealing(false)
    }
  }

  return (
    <div className="flex flex-col gap-4">
      {/* 七层流程（§3：done ✓ accent / todo ○ muted / current ● warn 高亮） */}
      <ul data-testid="flow-layers" className="flex flex-col gap-1">
        {LAYERS.map((layer) => {
          const done = layers?.[layer] === 'done'
          const isCurrent = layer === current
          return (
            <li
              key={layer}
              className={`flex items-center gap-2 rounded-input px-2 py-1.5 text-sm ${
                done
                  ? 'text-accent'
                  : isCurrent
                    ? 'bg-warn/10 font-medium text-warn'
                    : 'text-muted'
              }`}
            >
              <span className="w-4 shrink-0 text-center">{done ? '✓' : isCurrent ? '●' : '○'}</span>
              <span className="truncate">{LAYER_LABELS[layer]}</span>
              {isCurrent && <span className="ml-auto text-xs text-muted">当前</span>}
            </li>
          )
        })}
      </ul>

      {/* 无卷空态引导（§5.2）：落在 current 层行下方 */}
      {volumes.length === 0 && (
        <p className="rounded-card border border-border bg-raised px-3 py-2 text-sm text-muted">
          还没有卷——生成第一个场景提案
        </p>
      )}

      {/* 卷→章两级树（§3） */}
      {volumes.length > 0 && (
        <ul className="flex flex-col gap-3">
          {volumes.map((vol) => (
            <li key={vol.id} className="flex flex-col gap-1">
              <div className="flex items-center gap-2">
                <span className="min-w-0 flex-1 truncate text-sm font-medium text-primary">
                  {vol.name}
                </span>
                <button
                  type="button"
                  disabled={readonly}
                  title="封卷后卷内设定改动须走显式 retcon"
                  onClick={() => setSealVolume(vol)}
                  className="shrink-0 rounded-btn border border-danger/40 px-1.5 py-0.5 text-xs text-danger hover:bg-danger/10 disabled:cursor-not-allowed disabled:opacity-40"
                >
                  封卷
                </button>
              </div>
              <ul className="flex flex-col gap-0.5">
                {vol.chapters.map((ch) => (
                  <li key={ch.id}>
                    <button
                      type="button"
                      onClick={() => onSelectChapter?.(ch)}
                      className="w-full truncate rounded-input px-2 py-1 text-left text-sm text-muted hover:bg-raised hover:text-primary"
                    >
                      {ch.name}
                    </button>
                  </li>
                ))}
              </ul>
            </li>
          ))}
        </ul>
      )}

      {sealError && (
        <div role="alert" className="rounded-card bg-danger/15 px-3 py-2 text-sm text-danger">
          {sealError}
        </div>
      )}

      {sealVolume && (
        <ConfirmDialog
          title={`封卷：${sealVolume.name}`}
          consequence="封卷后卷内设定改动须走显式 retcon（回溯修订），且不可直接修改卷内节点。"
          busy={sealing}
          onConfirm={doSeal}
          onCancel={() => setSealVolume(null)}
        />
      )}
    </div>
  )
}
