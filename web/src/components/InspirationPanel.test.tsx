import { beforeEach, describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import InspirationPanel from './InspirationPanel'
import { api, useApi } from '../api'
import type { InspirationItem } from '../types'

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

const items: InspirationItem[] = [
  { id: 'i1', name: '灵感一', text: 'AI 会做梦吗' },
  { id: 'i2', name: '灵感二', text: '雪落在电线上，像一排休眠的琴弦——这是一句非常长的灵感原话用来验证截断样式' },
]

beforeEach(() => {
  mockPost.mockClear()
  mockUseApi.mockReset()
  mockUseApi.mockReturnValue({ data: null, loading: false, error: null })
})

describe('InspirationPanel（右栏提案 tab 灵感面板，TC-SH-09 / R4）', () => {
  it('列表渲染：序号 + text（useApi /api/inspirations），长文本可截断', () => {
    mockPaths({ '/api/inspirations': items })
    render(<InspirationPanel readonly={false} refreshKey={0} onSaved={() => {}} />)
    expect(screen.getByTestId('inspiration-panel')).toBeInTheDocument()
    expect(screen.getByText('AI 会做梦吗')).toBeInTheDocument()
    expect(screen.getByText(/雪落在电线上/)).toBeInTheDocument()
    expect(screen.getAllByTestId('inspiration-item')).toHaveLength(2)
    expect(screen.getByText('1.')).toBeInTheDocument()
  })

  it('保存原话 → api.post("/api/inspirations", {text}) + onSaved 回调 + 输入清空', async () => {
    mockPost.mockResolvedValue({ inspiration_id: 'i9' })
    const onSaved = vi.fn()
    render(<InspirationPanel readonly={false} refreshKey={0} onSaved={onSaved} />)
    fireEvent.change(screen.getByLabelText('灵感原话'), { target: { value: '新的灵感' } })
    fireEvent.click(screen.getByRole('button', { name: '保存灵感' }))
    await waitFor(() => {
      expect(mockPost).toHaveBeenCalledWith('/api/inspirations', { text: '新的灵感' })
    })
    expect(onSaved).toHaveBeenCalledTimes(1)
    expect(screen.getByLabelText('灵感原话')).toHaveValue('')
  })

  it('空文本 → 保存按钮禁用', () => {
    render(<InspirationPanel readonly={false} refreshKey={0} onSaved={() => {}} />)
    expect(screen.getByRole('button', { name: '保存灵感' })).toBeDisabled()
  })

  it('只读 → textarea 与保存按钮禁用（双重保险 §2 写操作双保险）', () => {
    render(<InspirationPanel readonly refreshKey={0} onSaved={() => {}} />)
    expect(screen.getByLabelText('灵感原话')).toBeDisabled()
    expect(screen.getByRole('button', { name: '保存灵感' })).toBeDisabled()
    expect(mockPost).not.toHaveBeenCalled()
  })

  it('POST 失败 → 红条呈现后端 detail（§5.3 doSave 范式）', async () => {
    mockPost.mockRejectedValue(new Error('灵感文本不能为空'))
    const onSaved = vi.fn()
    render(<InspirationPanel readonly={false} refreshKey={0} onSaved={onSaved} />)
    fireEvent.change(screen.getByLabelText('灵感原话'), { target: { value: 'x' } })
    fireEvent.click(screen.getByRole('button', { name: '保存灵感' }))
    await waitFor(() => {
      expect(screen.getByRole('alert')).toHaveTextContent('灵感文本不能为空')
    })
    expect(onSaved).not.toHaveBeenCalled()
  })
})
