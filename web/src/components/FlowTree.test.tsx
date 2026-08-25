import { describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen, within } from '@testing-library/react'
import FlowTree from './FlowTree'
import { api, useApi } from '../api'
import type { FlowState } from '../types'

// 数据层 mock：FlowTree 自身消费 GET /api/flow（useApi）+ POST /api/seal（封卷）
vi.mock('../api', () => ({
  useApi: vi.fn(),
  api: { get: vi.fn(), post: vi.fn() },
}))

const mockUseApi = vi.mocked(useApi)
const mockPost = vi.mocked(api.post)

const flow: FlowState = {
  layers: {
    premise: 'done', synopsis: 'todo', summary: 'todo', beat_sheet: 'todo',
    characters: 'todo', scenes: 'todo', prose: 'todo',
  },
  current_layer: 'synopsis',
  volumes: [
    { id: 'v1', name: '卷一', chapters: [
      { id: 'c1', name: '第一章' }, { id: 'c2', name: '第二章' },
    ] },
  ],
}

function mockFlow(data: FlowState | null, loading = false) {
  mockUseApi.mockReturnValue({ data, loading, error: null })
}

describe('FlowTree（ui-design-01 §3 左栏）', () => {
  it('渲染七层进度：done 层 ✓ accent / todo ○ muted / current ● warn 高亮行', () => {
    mockFlow(flow)
    render(<FlowTree />)
    // 七层行齐全（仅层列表，卷章树是独立 listitem）
    const layers = within(screen.getByTestId('flow-layers'))
    expect(layers.getAllByRole('listitem')).toHaveLength(7)
    // done 层：✓ + accent
    const premise = screen.getByText('前提').closest('li')
    expect(premise).toHaveTextContent('✓')
    expect(premise).toHaveClass('text-accent')
    // current 层：warn 高亮
    const synopsis = screen.getByText('梗概').closest('li')
    expect(synopsis).toHaveTextContent('●')
    expect(synopsis).toHaveClass('text-warn')
    // todo 层：○ + muted
    const prose = screen.getByText('正文').closest('li')
    expect(prose).toHaveTextContent('○')
    expect(prose).toHaveClass('text-muted')
  })

  it('渲染卷→章两级树，点击章回调 onSelectChapter', () => {
    mockFlow(flow)
    const onSelectChapter = vi.fn()
    render(<FlowTree onSelectChapter={onSelectChapter} />)
    expect(screen.getByText('卷一')).toBeInTheDocument()
    const c1 = screen.getByText('第一章')
    expect(c1).toBeInTheDocument()
    fireEvent.click(c1)
    expect(onSelectChapter).toHaveBeenCalledWith({ id: 'c1', name: '第一章' })
  })

  it('无卷空态：current 层行下方显示"还没有卷——生成第一个场景提案"引导（§5.2）', () => {
    mockFlow({ ...flow, volumes: [] })
    render(<FlowTree />)
    expect(screen.getByText('还没有卷——生成第一个场景提案')).toBeInTheDocument()
    // 层进度照常渲染
    expect(screen.getAllByRole('listitem')).toHaveLength(7)
  })

  it('封卷为危险操作：点击弹二次确认对话框（§5.4），Esc 取消不调接口', () => {
    mockFlow(flow)
    render(<FlowTree />)
    fireEvent.click(screen.getByRole('button', { name: /封卷/ }))
    expect(screen.getByRole('dialog')).toBeInTheDocument()
    expect(screen.getByText(/封卷后卷内设定改动须走显式 retcon/)).toBeInTheDocument()
    fireEvent.keyDown(window, { key: 'Escape' })
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    expect(mockPost).not.toHaveBeenCalled()
  })

  it('只读会话禁用封卷按钮（写守卫 409 前置）', () => {
    mockFlow(flow)
    render(<FlowTree readonly />)
    expect(screen.getByRole('button', { name: /封卷/ })).toBeDisabled()
  })
})
