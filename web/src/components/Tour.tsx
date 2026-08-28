// 操作指引 tour（TC-SH-14 / R2 自写零依赖）：状态机 welcome→running→idle 收在组件内部——
// 挂载时读 localStorage 记忆键决定首开欢迎卡；跳过/完成/Esc 中止统一记键关闭（R4 一个键管出口）；
// 外部经 runSignal 递增强制重启（手册"重看导览"），从第 1 步运行（清键由 App 事件侧负责）。
// 高亮 = 全屏半透明遮罩 + target 矩形定位环（不改 target 自身 class）；气泡相对矩形上下自适应，
// 矩形为 0（jsdom/目标缺失）时兜底视口左上固定位置——测试断言只看 testid/文案与推进。
import { useEffect, useState } from 'react'
import type { CSSProperties } from 'react'
import { TOUR_LABELS, TOUR_STEPS } from './labels'

// R4：tour 状态记忆键——存在即视为"已看过"，欢迎卡不再自动出现
export const TOUR_STORAGE_KEY = 'snowel.tour.done'

interface TourProps {
  // 递增信号：App 里"重看导览"按钮 +1 触发强制重启（回到第 1 步）
  runSignal?: number
}

type Phase = 'welcome' | 'running' | 'idle'

interface Rect {
  left: number
  top: number
  width: number
  height: number
}

// 气泡宽度与间距预算（与 w-72 / 8px 间距保持一致）
const BUBBLE_WIDTH = 288
const BUBBLE_GAP = 8
// 兜底定位：顶栏(48px)之下、贴左侧——0 矩形环境下气泡保证可见
const FALLBACK_POS = { left: 16, top: 64 }

export default function Tour({ runSignal = 0 }: TourProps) {
  const [phase, setPhase] = useState<Phase>(() =>
    localStorage.getItem(TOUR_STORAGE_KEY) ? 'idle' : 'welcome')
  const [stepIndex, setStepIndex] = useState(0)
  // 重启信号采用 React 认可的"渲染期依据 prop 调整状态"模式（避免 effect 内 setState 级联渲染）
  const [seenSignal, setSeenSignal] = useState(runSignal)
  if (runSignal !== seenSignal) {
    setSeenSignal(runSignal)
    setStepIndex(0)
    setPhase('running')
  }

  // 跳过 / 完成 / Esc 中止同归：记键 + 关闭
  const finish = () => {
    localStorage.setItem(TOUR_STORAGE_KEY, '1')
    setPhase('idle')
  }

  useEffect(() => {
    if (phase !== 'running') return
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') finish()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [phase])

  if (phase === 'idle') return null

  if (phase === 'welcome') {
    // 顶栏下方右侧固定浮层（不遮工作区）
    return (
      <div
        role="dialog"
        aria-label={TOUR_LABELS.welcomeTitle}
        data-testid="tour-welcome"
        className="fixed right-4 top-14 z-40 w-72 rounded-card border border-border bg-panel p-4 shadow-elev2"
      >
        <div className="text-sm font-medium text-primary">{TOUR_LABELS.welcomeTitle}</div>
        <p className="mt-2 text-sm leading-relaxed text-muted">{TOUR_LABELS.welcomeBody}</p>
        <div className="mt-3 flex justify-end gap-2">
          <button
            type="button"
            onClick={finish}
            className="rounded-btn border border-border bg-raised px-3 py-1.5 text-sm text-primary hover:bg-border"
          >
            {TOUR_LABELS.skip}
          </button>
          <button
            type="button"
            autoFocus
            onClick={() => {
              setStepIndex(0)
              setPhase('running')
            }}
            className="rounded-btn bg-accent px-3 py-1.5 text-sm text-white hover:opacity-90"
          >
            {TOUR_LABELS.start}
          </button>
        </div>
      </div>
    )
  }

  const step = TOUR_STEPS[stepIndex]
  const last = stepIndex === TOUR_STEPS.length - 1
  // 渲染期测量目标矩形（R2 允许简化重算时机；读 DOM 幂等，每步/每渲染刷新反而更及时）
  const targetRect = document
    .querySelector(`[data-testid="${step.testid}"]`)
    ?.getBoundingClientRect()
  const rect: Rect | null = targetRect
    ? { left: targetRect.left, top: targetRect.top, width: targetRect.width, height: targetRect.height }
    : null

  // 气泡定位：矩形有效 → 目标下方优先（视口下部不够放则上移到目标上方）；
  // 0 矩形（jsdom / 目标缺失）→ 兜底固定位置
  const realRect = rect !== null && (rect.width > 0 || rect.height > 0)
  let bubbleStyle: CSSProperties = { left: FALLBACK_POS.left, top: FALLBACK_POS.top }
  if (realRect && rect) {
    const left = Math.max(16, Math.min(rect.left, window.innerWidth - BUBBLE_WIDTH - 16))
    const below = rect.top + rect.height + BUBBLE_GAP + 200 < window.innerHeight
    bubbleStyle = below
      ? { left, top: rect.top + rect.height + BUBBLE_GAP }
      : { left, top: Math.max(8, rect.top - BUBBLE_GAP), transform: 'translateY(-100%)' }
  }

  return (
    <>
      {/* 全屏半透明遮罩：罩住工作区，聚焦当前步 */}
      <div data-testid="tour-overlay" className="fixed inset-0 z-40 bg-base/70" />
      {/* 高亮环：定位框叠加在 target 之上（不改 target class），jsdom 0 矩形时仅为 0 尺寸占位 */}
      {rect && (
        <div
          data-testid="tour-highlight"
          className="pointer-events-none fixed z-40 rounded-md ring-2 ring-accent"
          style={{
            left: rect.left - 4,
            top: rect.top - 4,
            width: rect.width + 8,
            height: rect.height + 8,
          }}
        />
      )}
      <div
        role="dialog"
        aria-label={step.title}
        data-testid="tour-bubble"
        style={bubbleStyle}
        className="fixed z-50 w-72 rounded-card border border-border bg-panel p-4 shadow-elev2"
      >
        <div className="flex items-baseline justify-between gap-2">
          <span className="text-sm font-medium text-primary">{step.title}</span>
          <span data-testid="tour-count" className="shrink-0 text-xs text-muted">
            {stepIndex + 1}/{TOUR_STEPS.length}
          </span>
        </div>
        <p className="mt-2 text-sm leading-relaxed text-muted">{step.body}</p>
        <div className="mt-3 flex items-center justify-between gap-2">
          <button
            type="button"
            onClick={finish}
            className="rounded-btn border border-border bg-raised px-2 py-1 text-xs text-primary hover:bg-border"
          >
            {TOUR_LABELS.exit}
          </button>
          <div className="flex gap-2">
            {stepIndex > 0 && (
              <button
                type="button"
                onClick={() => setStepIndex((i) => i - 1)}
                className="rounded-btn border border-border bg-raised px-3 py-1 text-xs text-primary hover:bg-border"
              >
                {TOUR_LABELS.prev}
              </button>
            )}
            {last ? (
              <button
                type="button"
                onClick={finish}
                className="rounded-btn bg-accent px-3 py-1 text-xs text-white hover:opacity-90"
              >
                {TOUR_LABELS.finish}
              </button>
            ) : (
              <button
                type="button"
                onClick={() => setStepIndex((i) => i + 1)}
                className="rounded-btn bg-accent px-3 py-1 text-xs text-white hover:opacity-90"
              >
                {TOUR_LABELS.next}
              </button>
            )}
          </div>
        </div>
      </div>
    </>
  )
}
