// 操作指引 tour 测试（TC-SH-14 / R2+R4）：欢迎卡首开显隐与跳过记键 / 六步推进与完成记键 /
// 运行中退出（退出按钮与 Esc）记键。jsdom 无真实布局——getBoundingClientRect 返回 0 矩形，
// 断言以"气泡文案/testid 出现与推进"为准，定位样式不做断言。
import { beforeEach, describe, expect, it } from 'vitest'
import { fireEvent, render, screen } from '@testing-library/react'
import Tour, { TOUR_STORAGE_KEY } from './Tour'
import { TOUR_STEPS, TOUR_LABELS } from './labels'

// 目标元素桩：Tour 以 [data-testid] 在 document 里找高亮目标，harness 预置全部 testid
function Harness() {
  return (
    <>
      {TOUR_STEPS.map((s) => (
        <div key={s.testid} data-testid={s.testid} />
      ))}
      <Tour />
    </>
  )
}

beforeEach(() => {
  localStorage.clear()
})

describe('Tour 欢迎卡（TC-SH-14 / R2+R4：首开无键显示）', () => {
  it('无键首开 → 欢迎卡显示（欢迎语 + 开始导览 + 跳过）', () => {
    render(<Harness />)
    expect(screen.getByTestId('tour-welcome')).toBeInTheDocument()
    expect(screen.getByText(TOUR_LABELS.welcomeTitle)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: TOUR_LABELS.start })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: TOUR_LABELS.skip })).toBeInTheDocument()
    // 未进入导览：无遮罩与气泡
    expect(screen.queryByTestId('tour-overlay')).not.toBeInTheDocument()
    expect(screen.queryByTestId('tour-bubble')).not.toBeInTheDocument()
  })

  it('跳过 → localStorage 记忆 + 欢迎卡消失；重挂不再出现', () => {
    const { unmount } = render(<Harness />)
    fireEvent.click(screen.getByRole('button', { name: TOUR_LABELS.skip }))
    expect(localStorage.getItem(TOUR_STORAGE_KEY)).not.toBeNull()
    expect(screen.queryByTestId('tour-welcome')).not.toBeInTheDocument()
    unmount()
    render(<Harness />)
    expect(screen.queryByTestId('tour-welcome')).not.toBeInTheDocument()
  })
})

describe('Tour 步骤引擎（TC-SH-14 / R7 六步推进）', () => {
  it('开始导览 → 第 1 步气泡与高亮遮罩出现（计数 1/6）', () => {
    render(<Harness />)
    fireEvent.click(screen.getByRole('button', { name: TOUR_LABELS.start }))
    expect(screen.queryByTestId('tour-welcome')).not.toBeInTheDocument()
    expect(screen.getByTestId('tour-overlay')).toBeInTheDocument()
    expect(screen.getByTestId('tour-highlight')).toBeInTheDocument()
    expect(screen.getByTestId('tour-bubble')).toBeInTheDocument()
    expect(screen.getByText(TOUR_STEPS[0].title)).toBeInTheDocument()
    expect(screen.getByText('1/6')).toBeInTheDocument()
  })

  it('前进到第 6 步 → "完成"替换"下一步"；完成 → 记键 + 全部消失', () => {
    render(<Harness />)
    fireEvent.click(screen.getByRole('button', { name: TOUR_LABELS.start }))
    for (let i = 2; i <= 6; i++) {
      fireEvent.click(screen.getByRole('button', { name: TOUR_LABELS.next }))
      expect(screen.getByText(`${i}/6`)).toBeInTheDocument()
      expect(screen.getByText(TOUR_STEPS[i - 1].title)).toBeInTheDocument()
    }
    expect(screen.getByRole('button', { name: TOUR_LABELS.finish })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: TOUR_LABELS.next })).not.toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: TOUR_LABELS.finish }))
    expect(localStorage.getItem(TOUR_STORAGE_KEY)).not.toBeNull()
    expect(screen.queryByTestId('tour-bubble')).not.toBeInTheDocument()
    expect(screen.queryByTestId('tour-overlay')).not.toBeInTheDocument()
  })

  it('"上一步"后退：第 2 步退回第 1 步文案；第 1 步无上一步按钮', () => {
    render(<Harness />)
    fireEvent.click(screen.getByRole('button', { name: TOUR_LABELS.start }))
    expect(screen.queryByRole('button', { name: TOUR_LABELS.prev })).not.toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: TOUR_LABELS.next }))
    fireEvent.click(screen.getByRole('button', { name: TOUR_LABELS.prev }))
    expect(screen.getByText('1/6')).toBeInTheDocument()
    expect(screen.getByText(TOUR_STEPS[0].title)).toBeInTheDocument()
  })

  it('运行中点"退出"→ 记键 + 消失', () => {
    render(<Harness />)
    fireEvent.click(screen.getByRole('button', { name: TOUR_LABELS.start }))
    fireEvent.click(screen.getByRole('button', { name: TOUR_LABELS.exit }))
    expect(localStorage.getItem(TOUR_STORAGE_KEY)).not.toBeNull()
    expect(screen.queryByTestId('tour-bubble')).not.toBeInTheDocument()
  })

  it('运行中 Esc 中止 → 记键 + 消失（R4）', () => {
    render(<Harness />)
    fireEvent.click(screen.getByRole('button', { name: TOUR_LABELS.start }))
    fireEvent.keyDown(window, { key: 'Escape' })
    expect(localStorage.getItem(TOUR_STORAGE_KEY)).not.toBeNull()
    expect(screen.queryByTestId('tour-bubble')).not.toBeInTheDocument()
  })

  it('runSignal>0 强制重启：已有记忆键也从第 1 步运行（清键在 App 事件侧）', () => {
    localStorage.setItem(TOUR_STORAGE_KEY, '1')
    // 模拟 App 递增 runSignal（手册"重看导览"按钮的启动方式）
    function SignalHarness({ runSignal }: { runSignal: number }) {
      return (
        <>
          {TOUR_STEPS.map((s) => (
            <div key={s.testid} data-testid={s.testid} />
          ))}
          <Tour runSignal={runSignal} />
        </>
      )
    }
    const { rerender } = render(<SignalHarness runSignal={0} />)
    expect(screen.queryByTestId('tour-welcome')).not.toBeInTheDocument()
    rerender(<SignalHarness runSignal={1} />)
    expect(screen.getByTestId('tour-bubble')).toBeInTheDocument()
    expect(screen.getByText('1/6')).toBeInTheDocument()
  })
})
