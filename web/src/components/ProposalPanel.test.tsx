import { describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import ProposalPanel from './ProposalPanel'
import { api, useApi } from '../api'
import type { Proposal } from '../types'

vi.mock('../api', () => ({
  useApi: vi.fn(),
  api: { get: vi.fn(), post: vi.fn() },
}))

const mockUseApi = vi.mocked(useApi)
const mockPost = vi.mocked(api.post)

function mockPaths(paths: Record<string, unknown>) {
  mockUseApi.mockImplementation((path: string) => ({
    data: paths[path] ?? null,
    loading: false,
    error: null,
  }))
}

const premiseDetail: Proposal = {
  id: 'p1', kind: 'premise', status: 'pending',
  payload: { facts: [{ fact: 'node', id: 'n1', types: ['Concept'], name: '雪', props: { x: '新值' } }] },
}

const preview = {
  tier: 'full',
  violations: [],
  diff_preview: [
    { node_id: 'n1', key: 'x', old: '旧值', new: '新值', refs: ['n1'] },
  ],
}

describe('ProposalPanel（ui-design-01 §4 diff / §5.4 危险确认 / W7 外部改动）', () => {
  it('payload diff 视图：键名 muted，旧值 font-mono + danger 底色 + 删除线，新值 ok 底色（§4）', () => {
    mockPaths({
      '/api/proposals/p1': premiseDetail,
      '/api/proposals/p1/cascade_preview': preview,
      '/api/reconcile': [],
    })
    render(<ProposalPanel proposalId="p1" />)
    const row = screen.getByText('n1 · x')
    expect(row).toHaveClass('text-muted')
    const old = screen.getByText('旧值')
    expect(old).toHaveClass('font-mono', 'bg-danger/20', 'line-through')
    const next = screen.getByText('新值')
    expect(next).toHaveClass('font-mono', 'bg-ok/20')
  })

  it('确认后展示 cascade.violations：major 违规行 danger 分色（§5.5）', async () => {
    mockPaths({
      '/api/proposals/p1': premiseDetail,
      '/api/proposals/p1/cascade_preview': preview,
      '/api/reconcile': [],
    })
    mockPost.mockResolvedValue({
      seq: 5,
      cascade: {
        tier: 'full',
        violations: [{
          level: 'major', rule: 'contradiction',
          message: '属性 x 与当前生效值矛盾', refs: ['n1'],
          detail: { node_id: 'n1', key: 'x', old: '旧值', new: '新值' },
        }],
        cascade_proposal_id: null,
      },
    })
    render(<ProposalPanel proposalId="p1" />)
    fireEvent.click(screen.getByRole('button', { name: '确认提案' }))
    await waitFor(() => {
      expect(mockPost).toHaveBeenCalledWith('/api/proposals/p1/confirm')
    })
    const chip = screen.getByText('属性 x 与当前生效值矛盾')
    expect(chip.closest('li')).toHaveClass('border-danger')
    expect(chip.closest('li')).toHaveTextContent('major')
    expect(mockPost).toHaveBeenCalledTimes(1)
  })

  it('retcon kind：确认按钮走 confirm_retcon 端点，展示 payload.impact（violations + 受影响数）', async () => {
    const retconDetail: Proposal = {
      id: 'r1', kind: 'retcon', status: 'pending',
      payload: {
        facts: [],
        impact: {
          violations: [{ level: 'minor', rule: 'renamed_ref', message: '引用名待更新', refs: ['a'] }],
          affected_proposals: ['q1', 'q2'],
        },
      },
    }
    mockPaths({
      '/api/proposals/r1': retconDetail,
      '/api/proposals/r1/cascade_preview': { tier: 'full', violations: [], diff_preview: [] },
      '/api/reconcile': [],
    })
    mockPost.mockResolvedValue({
      seq: 7,
      cascade: { tier: 'full', violations: [], cascade_proposal_id: null },
    })
    render(<ProposalPanel proposalId="r1" />)
    // impact 摘要直接展示（propose 时已全量级联，P5）
    expect(screen.getByText('引用名待更新')).toBeInTheDocument()
    expect(screen.getByText(/影响 2 个待确认提案/)).toBeInTheDocument()
    // retcon 确认是危险操作 → 先弹二次确认对话框，确认后走 confirm_retcon
    fireEvent.click(screen.getByRole('button', { name: '确认回溯' }))
    expect(screen.getByRole('dialog')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: '确认' }))
    await waitFor(() => {
      expect(mockPost).toHaveBeenCalledWith('/api/proposals/r1/confirm_retcon')
    })
  })

  it('prose 提案 + reconcile changed 非空 → warn 条列出外部改动章节 + 确认按钮明确文案（W7）', () => {
    const proseDetail: Proposal = {
      id: 'pr1', kind: 'prose', status: 'pending',
      payload: { chapter_id: 'ch1', content: '正文草稿' },
    }
    mockPaths({
      '/api/proposals/pr1': proseDetail,
      '/api/proposals/pr1/cascade_preview': { tier: 'full', violations: [], diff_preview: [] },
      '/api/reconcile': [
        { chapter_id: 'ch1', status: 'external_change' },
        { chapter_id: 'ch2', status: 'missing_file' },
      ],
    })
    render(<ProposalPanel proposalId="pr1" />)
    expect(screen.getByText(/检测到外部改动/)).toBeInTheDocument()
    expect(screen.getByText('ch1、ch2')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: '确认并覆盖外部改动' })).toBeInTheDocument()
  })

  it('否决是危险操作：点击弹二次确认对话框（§5.4），Esc 取消不调接口；确认后走 reject', async () => {
    mockPaths({
      '/api/proposals/p1': premiseDetail,
      '/api/proposals/p1/cascade_preview': preview,
      '/api/reconcile': [],
    })
    mockPost.mockResolvedValue({ ok: true })
    mockPost.mockClear()
    render(<ProposalPanel proposalId="p1" />)
    fireEvent.click(screen.getByRole('button', { name: '否决' }))
    expect(screen.getByRole('dialog')).toBeInTheDocument()
    fireEvent.keyDown(window, { key: 'Escape' })
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    expect(mockPost).not.toHaveBeenCalled()
    // 重开对话框并确认
    fireEvent.click(screen.getByRole('button', { name: '否决' }))
    fireEvent.click(screen.getByRole('button', { name: '确认' }))
    await waitFor(() => {
      expect(mockPost).toHaveBeenCalledWith('/api/proposals/p1/reject')
    })
  })

  it('stale 提案：warn 描边 + stale_hint 展示（§5.6）', () => {
    mockPaths({
      '/api/proposals/p1': { ...premiseDetail, status: 'stale', stale_hint: '上游梗概已改' },
      '/api/proposals/p1/cascade_preview': preview,
      '/api/reconcile': [],
    })
    render(<ProposalPanel proposalId="p1" />)
    expect(screen.getByText('上游梗概已改')).toBeInTheDocument()
    expect(screen.getByTestId('proposal-panel')).toHaveClass('border-warn')
  })

  it('未选中提案：渲染占位提示，不发起请求', () => {
    mockUseApi.mockClear()
    render(<ProposalPanel proposalId={null} />)
    expect(screen.getByText('在列表中选择提案查看详情')).toBeInTheDocument()
    expect(mockUseApi).not.toHaveBeenCalled()
  })

  it('改写框：提交 instruction → rewrite 端点 → 新提案通知', async () => {
    mockPaths({
      '/api/proposals/p1': premiseDetail,
      '/api/proposals/p1/cascade_preview': preview,
      '/api/reconcile': [],
    })
    mockPost.mockResolvedValue({ proposal_id: 'np1' })
    render(<ProposalPanel proposalId="p1" />)
    fireEvent.change(screen.getByLabelText('改写指令'), { target: { value: '把主角改成猫' } })
    fireEvent.click(screen.getByRole('button', { name: '提交改写' }))
    await waitFor(() => {
      expect(mockPost).toHaveBeenCalledWith(
        '/api/proposals/p1/rewrite', { instruction: '把主角改成猫' })
    })
    expect(screen.getByText(/新提案 np1 已入队/)).toBeInTheDocument()
  })
})
