// 角色关系图（W4）：圆环布局——角色节点等距分布于圆周（accent 圆点），
// 有关系的节点对以 muted 连线（两端均在活跃节点集内才画）；节点名 text-muted
// 标注；空态"暂无角色关系"（§5.2）。
import { useApi } from '../api'
import type { RelationsStatsResponse } from '../types'

const W = 320
const H = 240
const R = 88
const CX = W / 2
const CY = H / 2
const NODE_R = 6

export default function RelationsGraph() {
  const { data, loading, error } = useApi<RelationsStatsResponse>('/api/stats/relations')

  if (loading) {
    return (
      <div data-testid="relations-skeleton" className="flex flex-col gap-2">
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

  const nodes = data?.nodes ?? []
  if (nodes.length === 0) {
    return (
      <div className="rounded-card border border-border bg-raised px-3 py-4 text-center text-sm text-muted">
        暂无角色关系
      </div>
    )
  }

  // 圆周均分：首节点在正上方（-π/2），顺时针排列
  const pos = new Map<string, { x: number; y: number }>()
  nodes.forEach((n, i) => {
    const a = (2 * Math.PI * i) / nodes.length - Math.PI / 2
    pos.set(n.id, { x: CX + R * Math.cos(a), y: CY + R * Math.sin(a) })
  })
  const edges = (data?.edges ?? []).filter((e) => pos.has(e.src) && pos.has(e.dst))

  return (
    <div data-testid="relations-graph">
      <svg width={W} height={H} role="img" aria-label="角色关系图">
        {edges.map((e) => {
          const a = pos.get(e.src)!
          const b = pos.get(e.dst)!
          return (
            <line
              key={e.id}
              x1={a.x}
              y1={a.y}
              x2={b.x}
              y2={b.y}
              className="stroke-muted"
              strokeWidth={1}
            />
          )
        })}
        {nodes.map((n) => {
          const p = pos.get(n.id)!
          return (
            <g key={n.id}>
              <circle cx={p.x} cy={p.y} r={NODE_R} className="fill-accent" />
              <text x={p.x} y={p.y + NODE_R + 12} textAnchor="middle" className="fill-muted text-[10px]">
                {n.name}
              </text>
            </g>
          )
        })}
      </svg>
    </div>
  )
}
