import { describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import App from './App'
import { useApi } from './api'
import type { Session } from './types'

// 数据层整体 mock：App 壳测试不触网络（真实 api 面由 T10–T13 组件测试覆盖）
vi.mock('./api', () => ({
  useApi: vi.fn(),
  api: { get: vi.fn(), post: vi.fn() },
}))

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
