import { describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import App from './App'
import { useApi } from './api'
import { streamSSE } from './sse'
import type { Session } from './types'

// 数据层整体 mock：App 壳测试不触网络（真实 api 面由 T10–T13 组件测试覆盖）
vi.mock('./api', () => ({
  useApi: vi.fn(),
  api: { get: vi.fn(), post: vi.fn() },
}))
// 聊天流 mock：App 壳测试不发真实 SSE 请求
vi.mock('./sse', () => ({ streamSSE: vi.fn() }))

const mockUseApi = vi.mocked(useApi)

const writableSession: Session = {
  project: 'demo',
  readonly: false,
  holder: null,
  flow: {
    layers: { premise: 'done', synopsis: 'todo', summary: 'todo', beat_sheet: 'todo',
              characters: 'todo', scenes: 'todo', prose: 'todo' },
    current_layer: 'synopsis',
    volumes: [{ id: 'v1', name: '卷一', chapters: [{ id: 'c1', name: '第一章' }] }],
  },
}

const readonlySession: Session = {
  ...writableSession,
  readonly: true,
  holder: 'mcp:42',
}

function mockSession(session: Session | null, loading = false, error: string | null = null) {
  mockUseApi.mockReturnValue({ data: session, loading, error })
}

describe('App 三栏布局壳（ui-design-01 §3）', () => {
  it('渲染四容器：col-flow / col-prose / col-workspace / col-chat', () => {
    mockSession(writableSession)
    render(<App />)
    expect(screen.getByTestId('col-flow')).toBeInTheDocument()
    expect(screen.getByTestId('col-prose')).toBeInTheDocument()
    expect(screen.getByTestId('col-workspace')).toBeInTheDocument()
    expect(screen.getByTestId('col-chat')).toBeInTheDocument()
  })

  it('顶栏展示项目名与当前卷·章占位（取 flow 首个卷章）', () => {
    mockSession(writableSession)
    render(<App />)
    expect(screen.getByText('demo')).toBeInTheDocument()
    expect(screen.getByText(/卷一 · 第一章/)).toBeInTheDocument()
  })

  it('顶栏会话状态点：写会话绿（ok） / 只读会话黄（warn）', () => {
    mockSession(writableSession)
    const { rerender } = render(<App />)
    expect(screen.getByTestId('session-dot')).toHaveClass('bg-ok')
    mockSession(readonlySession)
    rerender(<App />)
    expect(screen.getByTestId('session-dot')).toHaveClass('bg-warn')
  })
})

describe('SessionBanner 只读横幅（ui-design-01 §3）', () => {
  it('readonly=true 显示"只读模式：写租约由 {holder} 持有"', () => {
    mockSession(readonlySession)
    render(<App />)
    expect(screen.getByText('只读模式：写租约由 mcp:42 持有')).toBeInTheDocument()
  })

  it('readonly=false 不显示横幅', () => {
    mockSession(writableSession)
    render(<App />)
    expect(screen.queryByText(/只读模式：写租约由/)).not.toBeInTheDocument()
  })
})

describe('useApi 加载/错误态（ui-design-01 §5.1/§5.3）', () => {
  it('loading=true 时各栏渲染骨架屏块', () => {
    mockSession(null, true)
    render(<App />)
    expect(screen.getAllByTestId('skeleton').length).toBeGreaterThan(0)
  })

  it('error 时渲染红条展示后端 detail 文案', () => {
    mockSession(null, false, '网络失败：后端未启动')
    render(<App />)
    expect(screen.getByTestId('error-bar')).toHaveTextContent('网络失败：后端未启动')
  })
})

describe('T13 工作区 tab（提案/可视化互斥，ui-design-01 §3）', () => {
  it('点"可视化"渲染统计图区段（挂载四图），点"提案"回到提案面板', () => {
    mockSession(writableSession)
    render(<App />)
    expect(screen.getByTestId('proposal-list')).toBeInTheDocument()

    fireEvent.click(screen.getByRole('tab', { name: '可视化' }))
    expect(screen.getByTestId('viz-sections')).toBeInTheDocument()
    // 互斥：提案面板内容卸载（统计 mock 数据为 Session 形状 → 四空态）
    expect(screen.queryByTestId('proposal-list')).not.toBeInTheDocument()
    expect(screen.getByText('暂无 POV 数据')).toBeInTheDocument()
    expect(screen.getByRole('tab', { name: '可视化' })).toHaveAttribute('aria-selected', 'true')

    fireEvent.click(screen.getByRole('tab', { name: '提案' }))
    expect(screen.getByTestId('proposal-list')).toBeInTheDocument()
    expect(screen.queryByTestId('viz-sections')).not.toBeInTheDocument()
  })

  it('空态"去生成"按钮：中栏空态引导切回"提案"tab（L22#3 App 接线）', () => {
    mockSession({ ...writableSession, flow: { ...writableSession.flow, volumes: [] } })
    render(<App />)
    // 先切到"可视化"tab，验证空态按钮把工作区切回提案面板
    fireEvent.click(screen.getByRole('tab', { name: '可视化' }))
    expect(screen.getByTestId('viz-sections')).toBeInTheDocument()
    expect(screen.getByText('还没有章节——生成第一个场景提案')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: '去生成' }))
    expect(screen.getByRole('tab', { name: '提案' })).toHaveAttribute('aria-selected', 'true')
    expect(screen.getByTestId('proposal-list')).toBeInTheDocument()
    expect(screen.queryByTestId('viz-sections')).not.toBeInTheDocument()
  })
})

describe('T3 灵感面板挂载（TC-SH-09 / R4：proposals tab，GenerateForm 之上）', () => {
  it('提案 tab 渲染灵感面板；写会话空文本 → 保存禁用（列表为空不炸——useApi 全路径 mock 兜底）', () => {
    mockSession(writableSession)
    render(<App />)
    expect(screen.getByTestId('inspiration-panel')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: '保存灵感' })).toBeDisabled()
  })

  it('只读会话 → 灵感面板 textarea 与保存按钮禁用（readonly 传递）', () => {
    mockSession(readonlySession)
    render(<App />)
    expect(screen.getByTestId('inspiration-panel')).toBeInTheDocument()
    expect(screen.getByLabelText('灵感原话')).toBeDisabled()
    expect(screen.getByRole('button', { name: '保存灵感' })).toBeDisabled()
  })
})

describe('T2 手册弹窗入口（TC-SH-13 / R3：顶栏"？"常驻）', () => {
  it('manual-btn 存在（title 使用手册）；点击打开弹窗且目录为真实 12 章', () => {
    mockSession(writableSession)
    render(<App />)
    expect(screen.queryByRole('dialog', { name: '使用手册' })).not.toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: '使用手册' }))
    expect(screen.getByTestId('manual-btn')).toBeInTheDocument()
    expect(screen.getByRole('dialog', { name: '使用手册' })).toBeInTheDocument()
    expect(within(screen.getByTestId('manual-toc')).getAllByRole('button')).toHaveLength(12)
  })

  it('弹窗内关闭按钮 → 弹窗收起（onClose 接线）', () => {
    mockSession(writableSession)
    render(<App />)
    fireEvent.click(screen.getByTestId('manual-btn'))
    expect(screen.getByRole('dialog', { name: '使用手册' })).toBeInTheDocument()
    fireEvent.click(screen.getByTestId('manual-close'))
    expect(screen.queryByRole('dialog', { name: '使用手册' })).not.toBeInTheDocument()
  })
})

describe('T12 遗留：聊天入队提案 → 去确认（T13：切回"提案"tab + refreshKey）', () => {
  it('可视化 tab 下点"去确认"链接 → 切回"提案"tab + ProposalList/FlowTree 以新 key 重拉', async () => {
    mockSession(writableSession)
    vi.mocked(streamSSE).mockImplementation(async (_url, _body, onEvent) => {
      onEvent({ type: 'done', proposal_ids: ['p1'] })
    })
    render(<App />)
    // 先切到"可视化"tab，验证 onGoProposals 会把工作区切回提案面板
    fireEvent.click(screen.getByRole('tab', { name: '可视化' }))
    expect(screen.getByTestId('viz-sections')).toBeInTheDocument()

    const flowCalls = () => mockUseApi.mock.calls.filter((c) => c[0] === '/api/flow').length
    const listCalls = () => mockUseApi.mock.calls.filter((c) => c[0] === '/api/proposals').length
    const beforeFlow = flowCalls()
    const beforeList = listCalls()

    fireEvent.change(screen.getByLabelText('聊天消息'), { target: { value: '生成提案' } })
    fireEvent.click(screen.getByRole('button', { name: '发送' }))
    fireEvent.click(await screen.findByRole('button', { name: /已入队 1 个提案/ }))

    // onGoProposals（T13 接线）：切回"提案"tab
    expect(screen.getByRole('tab', { name: '提案' })).toHaveAttribute('aria-selected', 'true')
    expect(screen.getByTestId('proposal-list')).toBeInTheDocument()
    expect(screen.queryByTestId('viz-sections')).not.toBeInTheDocument()
    // refreshKey 递增 → 消费方以新 key 重拉（/api/flow 另有 ProseEditor 消费，仅断增量）
    await waitFor(() => {
      expect(flowCalls()).toBeGreaterThan(beforeFlow)
      expect(listCalls()).toBeGreaterThan(beforeList)
    })
  })
})
