import { describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen } from '@testing-library/react'
import ProposalList from './ProposalList'
import { useApi } from '../api'
import type { Proposal } from '../types'

vi.mock('../api', () => ({
  useApi: vi.fn(),
  api: { get: vi.fn(), post: vi.fn() },
}))

const mockUseApi = vi.mocked(useApi)

const proposals: Proposal[] = [
  { id: 'p1', kind: 'premise', status: 'pending', payload: {} },
  { id: 'p2', kind: 'retcon', status: 'stale', payload: {}, stale_hint: '上游梗概已改' },
  { id: 'p3', kind: 'prose', status: 'confirmed', payload: {} },
  { id: 'p4', kind: 'scene', status: 'rejected', payload: {} },
]

function mockList(data: Proposal[]) {
  mockUseApi.mockReturnValue({ data, loading: false, error: null })
}

describe('ProposalList（右栏工作区）', () => {
  it('默认"待确认"视图优先展示 pending + stale；stale 行 warn 描边 + stale_hint 展示（§5.6）', () => {
    mockList(proposals)
    render(<ProposalList onSelect={() => {}} />)
    expect(screen.getByText('前提')).toBeInTheDocument()
    expect(screen.getByText('回溯变更')).toBeInTheDocument()
    // confirmed / rejected 不在待确认视图
    expect(screen.queryByText('正文')).not.toBeInTheDocument()
    expect(screen.queryByText('场景')).not.toBeInTheDocument()
    // stale 行：warn 描边 + hint 辅助行
    const staleRow = screen.getByText('回溯变更').closest('li')
    expect(staleRow).toHaveClass('border-warn')
    expect(screen.getByText('上游梗概已改')).toBeInTheDocument()
  })

  it('点击提案行 → onSelect 回调携带该提案', () => {
    mockList(proposals)
    const onSelect = vi.fn()
    render(<ProposalList onSelect={onSelect} />)
    fireEvent.click(screen.getByText('前提'))
    expect(onSelect).toHaveBeenCalledWith(proposals[0])
  })

  it('空提案列表渲染"暂无待确认提案"占位卡（§5.2）', () => {
    mockList([])
    render(<ProposalList onSelect={() => {}} />)
    expect(screen.getByText('暂无待确认提案')).toBeInTheDocument()
  })

  it('状态过滤 tab：切到"已确认"展示 confirmed 提案', () => {
    mockList(proposals)
    render(<ProposalList onSelect={() => {}} />)
    fireEvent.click(screen.getByRole('tab', { name: /已确认/ }))
    expect(screen.getByText('正文')).toBeInTheDocument()
    expect(screen.queryByText('前提')).not.toBeInTheDocument()
  })
})
