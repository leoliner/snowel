// 右栏工作区提案列表（ui-design-01 §5.2/§5.6）：status 过滤 tab（pending/stale 优先展示），
// stale 行 warn 描边 + stale_hint 辅助行；点击选中回调父级。
import { useState } from 'react'
import { useApi } from '../api'
import type { Proposal, ProposalStatus } from '../types'
import { KIND_LABELS } from './labels'

interface ProposalListProps {
  onSelect: (proposal: Proposal) => void
  selectedId?: string | null
}

type TabKey = 'pending' | 'confirmed' | 'rejected' | 'all'

const TABS: { key: TabKey; label: string; match: (s: ProposalStatus) => boolean }[] = [
  { key: 'pending', label: '待确认', match: (s) => s === 'pending' || s === 'stale' },
  { key: 'confirmed', label: '已确认', match: (s) => s === 'confirmed' },
  { key: 'rejected', label: '已否决', match: (s) => s === 'rejected' },
  { key: 'all', label: '全部', match: () => true },
]

const STATUS_CHIP: Record<string, string> = {
  pending: 'bg-raised text-muted',
  stale: 'border border-warn text-warn',
  confirmed: 'bg-ok/15 text-ok',
  rejected: 'bg-danger/15 text-danger',
}

export default function ProposalList({ onSelect, selectedId = null }: ProposalListProps) {
  const { data, loading, error } = useApi<Proposal[]>('/api/proposals')
  const [tabKey, setTabKey] = useState<TabKey>('pending')

  if (loading) {
    return (
      <div data-testid="proposal-skeleton" className="flex flex-col gap-2">
        <div className="skeleton h-6" />
        <div className="skeleton h-12" />
        <div className="skeleton h-12" />
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

  const tab = TABS.find((t) => t.key === tabKey) ?? TABS[0]
  const items = (Array.isArray(data) ? data : [])
    .filter((p) => tab.match(p.status))
    .sort((a, b) => {
      // 待确认视图：pending 优先于 stale（§5.6 优先展示）
      if (tab.key === 'pending' && a.status !== b.status) {
        return a.status === 'pending' ? -1 : 1
      }
      return 0
    })

  return (
    <div data-testid="proposal-list" className="flex flex-col gap-2">
      <div role="tablist" className="flex gap-1">
        {TABS.map((t) => (
          <button
            key={t.key}
            type="button"
            role="tab"
            aria-selected={t.key === tabKey}
            onClick={() => setTabKey(t.key)}
            className={`rounded-chip px-2 py-1 text-xs ${
              t.key === tabKey
                ? 'bg-accent text-base'
                : 'bg-raised text-muted hover:text-primary'
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      {items.length === 0 ? (
        <div className="rounded-card border border-border bg-raised px-3 py-4 text-center text-sm text-muted">
          {tabKey === 'all' ? '暂无提案' : `暂无${tab.label}提案`}
        </div>
      ) : (
        <ul className="flex flex-col gap-1">
          {items.map((p) => (
            <li
              key={p.id}
              className={`rounded-input border ${
                selectedId === p.id
                  ? 'border-accent bg-raised'
                  : p.status === 'stale'
                    ? 'border-warn bg-raised/60'
                    : 'border-transparent hover:bg-raised'
              }`}
            >
              <button
                type="button"
                onClick={() => onSelect(p)}
                className="w-full px-2 py-1.5 text-left"
              >
                <div className="flex items-center gap-2">
                  <span className="min-w-0 flex-1 truncate text-sm text-primary">
                    {KIND_LABELS[p.kind] ?? p.kind}
                  </span>
                  <span
                    className={`shrink-0 rounded-chip px-1.5 py-0.5 text-xs ${STATUS_CHIP[p.status] ?? 'bg-raised text-muted'}`}
                  >
                    {p.status}
                  </span>
                </div>
                {p.status === 'stale' && p.stale_hint && (
                  <div className="mt-0.5 truncate text-xs text-warn" title={p.stale_hint}>
                    {p.stale_hint}
                  </div>
                )}
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
