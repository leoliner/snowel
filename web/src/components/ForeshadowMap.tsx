// 伏笔时间线（W4）：x 轴 = 拍序（跨条目按拍 id 首次出现顺序均分占位），每条伏笔
// 自 planted_at 至 payoff_beat 画区间条（paid=ok / stale=danger，§2.1 语义色）；
// 仅种植（payoff 未设）在 planted 位画 warn 圆点；端缺失时退化为圆点。
// 拍 id 轴标签 text-muted 截断；图例文字标签满足 §2.1 语义色配文字约定。
import { useApi } from '../api'
import type { ForeshadowItem, ForeshadowStatsResponse } from '../types'

const W = 320
const LABEL_W = 72
const ROW_H = 22
const DOT_R = 3.5
const BAR_H = 8

export default function ForeshadowMap() {
  const { data, loading, error } = useApi<ForeshadowStatsResponse>('/api/stats/foreshadow')

  if (loading) {
    return (
      <div data-testid="foreshadow-skeleton" className="flex flex-col gap-2">
        <div className="skeleton h-4" />
        <div className="skeleton h-3" />
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

  const items = data?.items ?? []
  if (items.length === 0) {
    return (
      <div className="rounded-card border border-border bg-raised px-3 py-4 text-center text-sm text-muted">
        暂无伏笔
      </div>
    )
  }

  // 拍序：跨条目按首次出现顺序收集（planted_at → payoff_beat），均分 x 轴
  const beatOrder: string[] = []
  for (const it of items) {
    for (const b of [it.planted_at, it.payoff_beat]) {
      if (b && !beatOrder.includes(b)) beatOrder.push(b)
    }
  }
  const slot = Math.max((W - LABEL_W - 8) / Math.max(beatOrder.length, 1), 8)
  const xOf = (b: string | null) => (b ? beatOrder.indexOf(b) * slot : -1)
  // 轴标签（拍 id）text-muted 截断，防长 id 挤压
  const AXIS_H = 14

  return (
    <div data-testid="foreshadow-map">
      {/* 图例（§2.1：danger/ok/warn 语义色必配文字标签） */}
      <div className="mb-1 flex gap-3 text-xs text-muted">
        <span className="flex items-center gap-1">
          <span className="h-2 w-2 rounded-full bg-warn" />
          已种植
        </span>
        <span className="flex items-center gap-1">
          <span className="h-2 w-2 rounded-full bg-ok" />
          已回收
        </span>
        <span className="flex items-center gap-1">
          <span className="h-2 w-2 rounded-full bg-danger" />
          失效
        </span>
      </div>
      <svg width={W} height={items.length * ROW_H + 12 + AXIS_H} role="img" aria-label="伏笔时间线">
        {items.map((it: ForeshadowItem, i) => {
          const y = i * ROW_H + 12
          const px = xOf(it.planted_at)
          const qx = xOf(it.payoff_beat)
          const color = it.status === 'paid' ? 'fill-ok' : 'fill-danger'
          // 区间条：两端拍位齐备且 payoff 在 planted 之后；否则退化圆点
          const showBar = px >= 0 && qx > px
          const anchor = showBar ? px : qx >= 0 ? qx : px
          return (
            <g key={it.id}>
              <text x={4} y={y + 4} className="fill-muted text-[10px]">
                {it.name}
              </text>
              {showBar ? (
                <rect
                  x={LABEL_W + 4 + px}
                  y={y - BAR_H / 2}
                  width={qx - px}
                  height={BAR_H}
                  rx={2}
                  className={color}
                />
              ) : (
                <circle
                  cx={LABEL_W + 4 + anchor}
                  cy={y}
                  r={DOT_R}
                  className={it.status === 'planted' ? 'fill-warn' : color}
                />
              )}
            </g>
          )
        })}
        {/* x 轴拍序标签（text-muted，截断至 6 字符） */}
        {beatOrder.map((b, i) => (
          <text
            key={b}
            x={LABEL_W + 4 + i * slot}
            y={items.length * ROW_H + 12 + 10}
            textAnchor="middle"
            className="fill-muted text-[9px]"
          >
            {b.length > 6 ? `${b.slice(0, 6)}…` : b}
          </text>
        ))}
      </svg>
    </div>
  )
}
