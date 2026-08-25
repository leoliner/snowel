// 章节节奏（W4）：每章双条形并排——拍数 accent / 段落数 ok（§2.1 语义色），
// 章名 text-muted 轴标签；条宽按全局最大值归一（跨章可比）。空态"暂无章节"。
import { useApi } from '../api'
import type { PacingStatsResponse } from '../types'

const W = 320
const LABEL_W = 84
const ROW_H = 26
const BAR_H = 10
const GAP = 4 // 双条间距

export default function PacingBars() {
  const { data, loading, error } = useApi<PacingStatsResponse>('/api/stats/pacing')

  if (loading) {
    return (
      <div data-testid="pacing-skeleton" className="flex flex-col gap-2">
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

  const chapters = data?.chapters ?? []
  if (chapters.length === 0) {
    return (
      <div className="rounded-card border border-border bg-raised px-3 py-4 text-center text-sm text-muted">
        暂无章节
      </div>
    )
  }

  const maxVal = Math.max(...chapters.flatMap((c) => [c.beats, c.paragraphs]), 1)
  const barW = W - LABEL_W - 8
  const w = (v: number) => Math.max((v / maxVal) * barW, 1)

  return (
    <div data-testid="pacing-bars">
      <svg width={W} height={chapters.length * ROW_H} role="img" aria-label="章节节奏">
        {chapters.map((c, i) => {
          const y = i * ROW_H
          return (
            <g key={c.chapter_id}>
              <text x={4} y={y + BAR_H} className="fill-muted text-[10px]">
                {c.name}
              </text>
              <rect x={LABEL_W} y={y} width={w(c.beats)} height={BAR_H} rx={2} className="fill-accent" />
              <rect
                x={LABEL_W}
                y={y + BAR_H + GAP}
                width={w(c.paragraphs)}
                height={BAR_H}
                rx={2}
                className="fill-ok"
              />
            </g>
          )
        })}
      </svg>
    </div>
  )
}
