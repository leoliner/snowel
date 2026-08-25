// 分卷 POV 分布（ui-design-01 §2 + W4）：每卷一根水平堆叠条，段宽按卷内 POV
// 频次占比；段色按 POV 出现顺序循环语义色（accent/ok/warn/danger…，分类色）；
// 卷名 text-muted 轴标签，无 address 的 POV 聚合为"未分卷"；空态（§5.2）。
import { useApi } from '../api'
import type { PovStatsResponse } from '../types'

// 语义色循环（§2.1）：数据主体用语义色，超 4 种 POV 回绕
const SEGMENT_FILLS = ['fill-accent', 'fill-ok', 'fill-warn', 'fill-danger']

const W = 320
const BAR_H = 14
const ROW_H = 26
const LABEL_W = 84

export default function PovChart() {
  const { data, loading, error } = useApi<PovStatsResponse>('/api/stats/pov')

  if (loading) {
    return (
      <div data-testid="pov-skeleton" className="flex flex-col gap-2">
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

  const volumes = data?.by_volume ?? []
  if (volumes.length === 0) {
    return (
      <div className="rounded-card border border-border bg-raised px-3 py-4 text-center text-sm text-muted">
        暂无 POV 数据
      </div>
    )
  }

  // 最长条 = 全卷最大合计，跨卷比例可比
  const maxTotal = Math.max(
    ...volumes.map((v) => Object.values(v.counts ?? {}).reduce((a, b) => a + b, 0)),
    1,
  )
  const barW = W - LABEL_W - 8

  return (
    <div data-testid="pov-chart">
      <svg width={W} height={volumes.length * ROW_H} role="img" aria-label="POV 分布">
        {volumes.map((v, i) => {
          const counts = v.counts ?? {}
          const names = Object.keys(counts)
          let x = LABEL_W
          return (
            <g key={v.volume_id ?? `vol-${i}`}>
              <text x={4} y={i * ROW_H + BAR_H} className="fill-muted text-[10px]">
                {v.volume_name ?? '未分卷'}
              </text>
              {names.map((name, j) => {
                const width = (counts[name] / maxTotal) * barW
                const seg = (
                  <rect
                    key={name}
                    x={x}
                    y={i * ROW_H}
                    width={Math.max(width, 1)}
                    height={BAR_H}
                    rx={2}
                    className={SEGMENT_FILLS[j % SEGMENT_FILLS.length]}
                  />
                )
                x += width
                return seg
              })}
            </g>
          )
        })}
      </svg>
    </div>
  )
}
