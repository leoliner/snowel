import { beforeEach, describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import GenerateForm from './GenerateForm'
import { api } from '../api'

vi.mock('../api', () => ({
  useApi: vi.fn(),
  api: { get: vi.fn(), post: vi.fn() },
}))

const mockPost = vi.mocked(api.post)

beforeEach(() => {
  mockPost.mockClear()
})

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
