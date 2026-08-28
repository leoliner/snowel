// 手册弹窗测试（TC-SH-13 / R3）：目录 12 章 / 点击定位 / 关键词过滤 / esc 与遮罩关闭 / md 源真实渲染
// 注意：不 mock md 源——import.meta.glob 在 vitest 下走同一条 vite 管线，断言用真实 12 章内容
import { useState } from 'react'
import { beforeAll, beforeEach, describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen, within } from '@testing-library/react'
import ManualModal from './ManualModal'

// jsdom 未实现滚动 API：scrollIntoView 以 vi.fn 桩替代，定位断言只看"点击目录触发调用"
beforeAll(() => {
  Element.prototype.scrollIntoView = vi.fn()
})
beforeEach(() => {
  vi.mocked(Element.prototype.scrollIntoView).mockClear()
})

// open/onClose 走父层 state 的最小挂载壳（App 内即此用法：入口按钮 open、esc/遮罩 onClose）
function Harness({ onClose }: { onClose: () => void }) {
  const [open, setOpen] = useState(true)
  return (
    <>
      <button type="button" data-testid="harness-reopen" onClick={() => setOpen(true)}>
        reopen
      </button>
      <ManualModal
        open={open}
        onClose={() => {
          setOpen(false)
          onClose()
        }}
      />
    </>
  )
}

describe('ManualModal 手册弹窗（TC-SH-13 / R3）', () => {
  it('open=false 不渲染弹窗；open=true 渲染 dialog（aria-label 使用手册）', () => {
    render(<ManualModal open={false} onClose={vi.fn()} />)
    expect(screen.queryByTestId('manual-modal')).not.toBeInTheDocument()
    render(<ManualModal open onClose={vi.fn()} />)
    expect(screen.getByRole('dialog', { name: '使用手册' })).toBeInTheDocument()
  })

  it('目录渲染 12 章（真实 md 源解析，首章快速上手 / 末章检索与偏好）', () => {
    render(<ManualModal open onClose={vi.fn()} />)
    const toc = screen.getByTestId('manual-toc')
    const items = within(toc).getAllByRole('button')
    expect(items).toHaveLength(12)
    expect(items[0]).toHaveTextContent('快速上手')
    expect(items[11]).toHaveTextContent('检索与偏好')
  })

  it('默认高亮首章；点击目录项触发滚动定位并移动高亮', () => {
    render(<ManualModal open onClose={vi.fn()} />)
    expect(screen.getByTestId('manual-toc-01-getting-started')).toHaveAttribute('aria-current', 'true')
    fireEvent.click(screen.getByTestId('manual-toc-03-proposals'))
    expect(Element.prototype.scrollIntoView).toHaveBeenCalled()
    expect(screen.getByTestId('manual-toc-03-proposals')).toHaveAttribute('aria-current', 'true')
    expect(screen.getByTestId('manual-toc-01-getting-started')).not.toHaveAttribute('aria-current')
    expect(within(screen.getByTestId('manual-content')).getByTestId('manual-chapter-03-proposals')).toBeInTheDocument()
  })

  it('过滤框输入正文关键词 → 目录与内容只留命中章；清空复原 12 章', () => {
    render(<ManualModal open onClose={vi.fn()} />)
    fireEvent.change(screen.getByLabelText('过滤手册'), { target: { value: '心跳续租' } })
    const items = within(screen.getByTestId('manual-toc')).getAllByRole('button')
    expect(items).toHaveLength(1)
    expect(items[0]).toHaveTextContent('租约与多端')
    expect(screen.getByTestId('manual-chapter-08-lease')).toBeInTheDocument()
    expect(screen.queryByTestId('manual-chapter-01-getting-started')).not.toBeInTheDocument()
    fireEvent.change(screen.getByLabelText('过滤手册'), { target: { value: '' } })
    expect(within(screen.getByTestId('manual-toc')).getAllByRole('button')).toHaveLength(12)
    expect(screen.getByTestId('manual-chapter-01-getting-started')).toBeInTheDocument()
  })

  it('无命中章节 → 目录呈现空态提示', () => {
    render(<ManualModal open onClose={vi.fn()} />)
    fireEvent.change(screen.getByLabelText('过滤手册'), { target: { value: '绝不存在的关键词xyz' } })
    expect(screen.getByTestId('manual-empty')).toBeInTheDocument()
    expect(within(screen.getByTestId('manual-content')).queryByRole('heading')).not.toBeInTheDocument()
  })

  it('esc 关闭（onClose 透传父层后弹窗消失）', () => {
    const onClose = vi.fn()
    render(<Harness onClose={onClose} />)
    fireEvent.keyDown(window, { key: 'Escape' })
    expect(onClose).toHaveBeenCalledTimes(1)
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  })

  it('遮罩点击关闭；弹窗内部点击不误关', () => {
    const onClose = vi.fn()
    render(<Harness onClose={onClose} />)
    fireEvent.mouseDown(screen.getByTestId('manual-modal'))
    expect(onClose).toHaveBeenCalledTimes(1)
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    // 第二次打开：内容区（弹窗内部）mousedown 不触发关闭
    render(<Harness onClose={onClose} />)
    fireEvent.mouseDown(within(screen.getByRole('dialog')).getByTestId('manual-content'))
    expect(onClose).toHaveBeenCalledTimes(1)
    expect(screen.getByRole('dialog')).toBeInTheDocument()
  })

  it('内容 markdown 元素真实来自 md 源：代码块 / h2 / 列表 / GFM 表格', () => {
    render(<ManualModal open onClose={vi.fn()} />)
    // 01 章：围栏代码块（pre > code）内容与源文一致
    const ch01 = screen.getByTestId('manual-chapter-01-getting-started')
    expect(ch01.querySelector('pre > code')).toHaveTextContent('pip install -e . -e ./shell')
    expect(within(ch01).getAllByRole('listitem').length).toBeGreaterThan(0)
    // 05 章：h2 即源文首行章节标题
    expect(
      within(screen.getByTestId('manual-chapter-05-seal-retcon')).getByRole('heading', {
        level: 2,
        name: '封卷与 retcon',
      })
    ).toBeInTheDocument()
    // 08 章：GFM 表格表头与源文一致
    expect(
      within(screen.getByTestId('manual-chapter-08-lease')).getByRole('columnheader', { name: '入口' })
    ).toBeInTheDocument()
  })
})
