import { act, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import ChatSidebar from './ChatSidebar'
import { streamSSE } from '../sse'
import type { ChatEvent } from '../types'

vi.mock('../sse', () => ({ streamSSE: vi.fn() }))

const mockStream = vi.mocked(streamSSE)

const FOUR_EVENTS: ChatEvent[] = [
  { type: 'tool_call', tool: 'generate', args: { artifact_type: 'scene' } },
  { type: 'tool_result', tool: 'generate', ok: true, summary: '已生成场景提案' },
  { type: 'reply', text: '好的，已生成场景提案，请到右侧确认。' },
  { type: 'done', proposal_ids: ['p1', 'p2'] },
]

// 喂事件后保持流打开（不 resolve），返回 release 关闭流触发 finalize
function holdStream(events: ChatEvent[] = []) {
  let release!: () => void
  const gate = new Promise<void>((r) => { release = r })
  mockStream.mockImplementation(async (_url, _body, onEvent) => {
    for (const ev of events) onEvent(ev)
    await gate
  })
  return release
}

// 发送一条消息；冲刷流结束（finalize）等微任务，避免 act 警告
async function send(text: string) {
  fireEvent.change(screen.getByLabelText('聊天消息'), { target: { value: text } })
  fireEvent.click(screen.getByRole('button', { name: '发送' }))
  await act(async () => {})
}

beforeEach(() => {
  mockStream.mockReset()
  holdStream() // 默认：无事件、流保持打开
})

describe('ChatSidebar（聊天侧栏，ui-design-01 §5.7/§5.8）', () => {
  it('按序四事件 → tool 卡片/就地结果/reply 最终文本 + 入队链接（§5.8）', async () => {
    const release = holdStream(FOUR_EVENTS)
    const onGoProposals = vi.fn()
    render(<ChatSidebar onGoProposals={onGoProposals} />)
    await send('生成一个场景提案')

    // tool_call 卡片 + tool_result 就地更新成败
    await waitFor(() => {
      expect(screen.getByText(/调用 generate/)).toBeInTheDocument()
      expect(screen.getByText(/成功：已生成场景提案/)).toBeInTheDocument()
    })
    // done → 入队链接（accent，proposal_ids 非空）
    expect(screen.getByRole('button', { name: '已入队 2 个提案 → 去确认' })).toBeInTheDocument()

    // 收束流 → reply 完整入历史；链接保留
    await act(async () => release())
    await waitFor(() => {
      expect(screen.getByText('好的，已生成场景提案，请到右侧确认。')).toBeInTheDocument()
    })
    expect(screen.getByRole('button', { name: '已入队 2 个提案 → 去确认' })).toBeInTheDocument()

    // 请求体：message + 此前轮次历史（不含本次消息）
    expect(mockStream.mock.calls[0][1]).toEqual({ message: '生成一个场景提案', history: [] })
  })

  it('done 无入队提案（proposal_ids 空）→ 不显示去确认链接', async () => {
    holdStream([{ type: 'reply', text: '好的' }, { type: 'done', proposal_ids: [] }])
    render(<ChatSidebar onGoProposals={vi.fn()} />)
    await send('生成一个场景提案')
    await waitFor(() => expect(screen.getByText('好的')).toBeInTheDocument())
    expect(screen.queryByRole('button', { name: /已入队/ })).not.toBeInTheDocument()
  })

  it('tool_result ok=false → 卡片就地显示失败', async () => {
    holdStream([
      { type: 'tool_call', tool: 'query', args: {} },
      { type: 'tool_result', tool: 'query', ok: false, summary: '检索超时' },
    ])
    render(<ChatSidebar onGoProposals={vi.fn()} />)
    await send('查一下')
    await waitFor(() => {
      expect(screen.getByText(/调用 query 失败：检索超时/)).toBeInTheDocument()
    })
  })

  it('reply 打字机渐显：断言最终文本渲染而非动画帧（§5.8）', async () => {
    holdStream([
      { type: 'reply', text: '好的，这是完整的打字机回复文本，用于断言最终渲染。' },
      { type: 'done', proposal_ids: [] },
    ])
    render(<ChatSidebar onGoProposals={vi.fn()} />)
    await send('你好')
    await waitFor(() => {
      expect(screen.getByText('好的，这是完整的打字机回复文本，用于断言最终渲染。')).toBeInTheDocument()
    })
  })

  it('Enter 发送 / Shift+Enter 换行不发送（§5.7）', async () => {
    render(<ChatSidebar onGoProposals={vi.fn()} />)
    const input = screen.getByLabelText('聊天消息')
    fireEvent.change(input, { target: { value: '你好' } })
    fireEvent.keyDown(input, { key: 'Enter', shiftKey: true })
    expect(mockStream).not.toHaveBeenCalled()
    fireEvent.keyDown(input, { key: 'Enter' })
    await waitFor(() => expect(mockStream).toHaveBeenCalledTimes(1))
    expect(mockStream.mock.calls[0][1]).toEqual({ message: '你好', history: [] })
  })

  it('IME 组合态（isComposing）下 Enter 确认候选词不发送、输入保留', async () => {
    render(<ChatSidebar onGoProposals={vi.fn()} />)
    const input = screen.getByLabelText('聊天消息')
    fireEvent.change(input, { target: { value: 'nihao' } })
    // 中文输入法确认候选词：keydown 的 nativeEvent.isComposing=true（round 1 fix）
    fireEvent.keyDown(input, { key: 'Enter', isComposing: true })
    expect(mockStream).not.toHaveBeenCalled()
    expect(input).toHaveValue('nihao')
  })

  it('流进行中显示"中断"按钮，点击 → abort（Esc 同效，§5.7）', async () => {
    let signal: AbortSignal | undefined
    mockStream.mockImplementation(async (_url, _body, _onEvent, sig) => {
      signal = sig
      await new Promise<void>((_resolve, reject) => {
        sig?.addEventListener('abort', () => {
          const err = new Error('The user aborted a request.')
          err.name = 'AbortError'
          reject(err)
        })
      })
    })
    render(<ChatSidebar onGoProposals={vi.fn()} />)
    await send('你好')

    // 点击中断按钮 → abort
    fireEvent.click(screen.getByRole('button', { name: '中断' }))
    await act(async () => {})
    expect(signal?.aborted).toBe(true)
    await waitFor(() => {
      expect(screen.queryByRole('button', { name: '中断' })).not.toBeInTheDocument()
    })

    // 再来一轮：Esc 同效
    await send('你好')
    fireEvent.keyDown(window, { key: 'Escape' })
    await act(async () => {})
    expect(signal?.aborted).toBe(true)
    await waitFor(() => {
      expect(screen.queryByRole('button', { name: '中断' })).not.toBeInTheDocument()
    })
  })

  it('error 事件 → 红条 + 重试再次发送同一消息（§5.3）', async () => {
    mockStream.mockImplementation(async (_url, _body, onEvent) => {
      onEvent({ type: 'error', text: '模型服务不可用' })
    })
    render(<ChatSidebar onGoProposals={vi.fn()} />)
    await send('生成一个场景提案')
    await waitFor(() => {
      expect(screen.getByRole('alert')).toHaveTextContent('模型服务不可用')
    })

    // 重试：不新增 user 气泡，历史不含重试消息本身
    fireEvent.click(screen.getByRole('button', { name: '重试' }))
    await act(async () => {})
    expect(mockStream).toHaveBeenCalledTimes(2)
    expect(mockStream.mock.calls[1][1]).toEqual({ message: '生成一个场景提案', history: [] })
  })

  it('历史本地维护：第二轮请求携带首轮 user+assistant 历史', async () => {
    mockStream.mockImplementation(async (_url, _body, onEvent) => {
      onEvent({ type: 'reply', text: '第一轮回复' })
      onEvent({ type: 'done', proposal_ids: [] })
    })
    render(<ChatSidebar onGoProposals={vi.fn()} />)
    await send('第一轮问题')
    await waitFor(() => expect(screen.getByText('第一轮回复')).toBeInTheDocument())
    await send('第二轮问题')
    await waitFor(() => expect(mockStream).toHaveBeenCalledTimes(2))
    expect(mockStream.mock.calls[1][1]).toEqual({
      message: '第二轮问题',
      history: [
        { role: 'user', text: '第一轮问题' },
        { role: 'assistant', text: '第一轮回复' },
      ],
    })
  })

  it('只读：输入框与发送按钮禁用', () => {
    render(<ChatSidebar readonly onGoProposals={vi.fn()} />)
    expect(screen.getByLabelText('聊天消息')).toBeDisabled()
    expect(screen.getByRole('button', { name: '发送' })).toBeDisabled()
  })
})
