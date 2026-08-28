import { beforeEach, describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import GenerateForm from './GenerateForm'
import { api, useApi } from '../api'
import type { InspirationItem } from '../types'

vi.mock('../api', () => ({
  useApi: vi.fn(),
  api: { get: vi.fn(), post: vi.fn() },
}))

const mockUseApi = vi.mocked(useApi)
const mockPost = vi.mocked(api.post)

beforeEach(() => {
  mockPost.mockClear()
  mockUseApi.mockReset()
  // 默认无灵感数据（derive 小节不渲染）；derive 用例自行喂 /api/inspirations
  mockUseApi.mockReturnValue({ data: null, loading: false, error: null })
})

const inspirations: InspirationItem[] = [
  { id: 'i1', name: '灵感一', text: '灵感一：AI 会做梦吗' },
  { id: 'i2', name: '灵感二', text: '灵感二：雪落在电线上' },
]

describe('GenerateForm（右栏工作区表单，E3 生成环）', () => {
  it('七类 artifact_type 可选，提交 → POST /api/generate → onGenerated 回调新提案 pid', async () => {
    mockPost.mockResolvedValue({ proposal_id: 'np1' })
    const onGenerated = vi.fn()
    render(<GenerateForm onGenerated={onGenerated} />)
    const select = screen.getByLabelText('生成类型')
    expect(select).toBeInTheDocument()
    fireEvent.change(select, { target: { value: 'prose' } })
    fireEvent.click(screen.getByRole('button', { name: '生成提案' }))
    await waitFor(() => {
      expect(mockPost).toHaveBeenCalledWith('/api/generate', { artifact_type: 'prose' })
    })
    expect(onGenerated).toHaveBeenCalledWith('np1')
  })

  it('locate 非法 JSON → 内联错误，不提交', () => {
    mockPost.mockResolvedValue({ proposal_id: 'np1' })
    render(<GenerateForm onGenerated={() => {}} />)
    fireEvent.change(screen.getByLabelText(/locate/), { target: { value: '{不是json' } })
    fireEvent.click(screen.getByRole('button', { name: '生成提案' }))
    expect(screen.getByText(/locate 不是合法 JSON/)).toBeInTheDocument()
    expect(mockPost).not.toHaveBeenCalled()
  })

  it('locate/extra 合法 JSON → 解析后随请求体提交', async () => {
    mockPost.mockResolvedValue({ proposal_id: 'np1' })
    render(<GenerateForm onGenerated={() => {}} />)
    fireEvent.change(screen.getByLabelText(/locate/), {
      target: { value: '{"chapter": "ch1"}' },
    })
    fireEvent.change(screen.getByLabelText(/extra/), {
      target: { value: '{"tone": "dark"}' },
    })
    fireEvent.click(screen.getByRole('button', { name: '生成提案' }))
    await waitFor(() => {
      expect(mockPost).toHaveBeenCalledWith('/api/generate', {
        artifact_type: 'premise',
        locate: { chapter: 'ch1' },
        extra: { tone: 'dark' },
      })
    })
  })

  it('提交失败：后端 detail 直显错误条（§5.3）', async () => {
    mockPost.mockRejectedValue(new Error('只读会话：写租约由 web:1 持有'))
    render(<GenerateForm onGenerated={() => {}} />)
    fireEvent.click(screen.getByRole('button', { name: '生成提案' }))
    await waitFor(() => {
      expect(screen.getByRole('alert')).toHaveTextContent('只读会话：写租约由 web:1 持有')
    })
  })

  it('只读会话禁用提交按钮', () => {
    render(<GenerateForm readonly onGenerated={() => {}} />)
    expect(screen.getByRole('button', { name: '生成提案' })).toBeDisabled()
  })
})

describe('GenerateForm 灵感多选 derive 联动（TC-SH-09 / R4）', () => {
  function mockInspirationData() {
    mockUseApi.mockImplementation((path: string) => ({
      data: path === '/api/inspirations' ? inspirations : null,
      loading: false,
      error: null,
    }))
  }

  it('有灵感数据 → 渲染"从灵感发起生成"小节（chips 勾选）', () => {
    mockInspirationData()
    render(<GenerateForm onGenerated={() => {}} />)
    expect(screen.getByText('从灵感发起生成')).toBeInTheDocument()
    expect(screen.getAllByTestId('derive-chip')).toHaveLength(2)
  })

  it('无灵感数据 → derive 小节整体不渲染', () => {
    render(<GenerateForm onGenerated={() => {}} />)
    expect(screen.queryByText('从灵感发起生成')).not.toBeInTheDocument()
    expect(screen.queryAllByTestId('derive-chip')).toHaveLength(0)
  })

  it('勾选灵感 → 提交 body 含 derive_from=[...选中 id]', async () => {
    mockInspirationData()
    mockPost.mockResolvedValue({ proposal_id: 'np1' })
    const onGenerated = vi.fn()
    render(<GenerateForm onGenerated={onGenerated} />)
    const chip1 = screen.getByRole('button', { name: '灵感一：AI 会做梦吗' })
    const chip2 = screen.getByRole('button', { name: '灵感二：雪落在电线上' })
    fireEvent.click(chip1)
    expect(chip1).toHaveAttribute('aria-pressed', 'true')
    fireEvent.click(chip2)
    fireEvent.click(screen.getByRole('button', { name: '生成提案' }))
    await waitFor(() => {
      expect(mockPost).toHaveBeenCalledWith('/api/generate', {
        artifact_type: 'premise',
        derive_from: ['i1', 'i2'],
      })
    })
    expect(onGenerated).toHaveBeenCalledWith('np1')
  })

  it('有灵感数据但未勾选 → body 不含 derive_from 键（与后端条件透传对齐）', async () => {
    mockInspirationData()
    mockPost.mockResolvedValue({ proposal_id: 'np1' })
    render(<GenerateForm onGenerated={() => {}} />)
    fireEvent.click(screen.getByRole('button', { name: '生成提案' }))
    await waitFor(() => {
      expect(mockPost).toHaveBeenCalledWith('/api/generate', { artifact_type: 'premise' })
    })
  })
})
