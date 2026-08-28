import { beforeEach, describe, expect, it, vi } from 'vitest'
import { act, fireEvent, render, screen, waitFor } from '@testing-library/react'
import ProseEditor from './ProseEditor'
import { api, useApi } from '../api'
import type { FlowState } from '../types'

// 数据层 mock：ProseEditor 消费 GET /api/flow + /api/reconcile（useApi）
// + POST /api/prose（保存）/ POST /api/writeback/extract（抽取）
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

const flow: FlowState = {
  layers: {
    premise: 'done', synopsis: 'done', summary: 'done', beat_sheet: 'done',
    characters: 'done', scenes: 'done', prose: 'todo',
  },
  current_layer: 'prose',
  volumes: [
    { id: 'v1', name: '卷一', chapters: [
      { id: 'c1', name: '第一章' }, { id: 'c2', name: '第二章' },
    ] },
  ],
}

beforeEach(() => {
  mockPost.mockReset()
})

describe('ProseEditor（ui-design-01 §5.2/§5.9 中栏正文编辑页）', () => {
  it('章节列表渲染（flow.volumes[].chapters）；reconcile missing_file 章显示状态 chip', () => {
    mockPaths({
      '/api/flow': flow,
      '/api/reconcile': [{ chapter_id: 'c2', status: 'missing_file' }],
    })
    render(<ProseEditor />)
    // 章名同时出现在列表与编辑区头（选中章），取列表内按钮断言
    expect(screen.getAllByText('第一章').length).toBeGreaterThan(0)
    expect(screen.getAllByText('第二章').length).toBeGreaterThan(0)
    expect(screen.getByText('镜像缺失')).toBeInTheDocument()
    expect(screen.queryByText('外部改动')).not.toBeInTheDocument()
  })

  it('无章空态："还没有章节——生成第一个场景提案" + 按钮回调 onGoGenerate（§5.2）', () => {
    mockPaths({ '/api/flow': { ...flow, volumes: [] }, '/api/reconcile': [] })
    const onGoGenerate = vi.fn()
    render(<ProseEditor onGoGenerate={onGoGenerate} />)
    expect(screen.getByText('还没有章节——生成第一个场景提案')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: /去生成/ }))
    expect(onGoGenerate).toHaveBeenCalled()
  })

  it('编辑区语义类名：font-prose + text-prose + 42em 行宽居中（§5.9）', () => {
    mockPaths({ '/api/flow': flow, '/api/reconcile': [] })
    render(<ProseEditor />)
    const ta = screen.getByLabelText('正文')
    expect(ta).toHaveClass('font-prose', 'text-prose', 'max-w-[42em]', 'mx-auto')
  })

  it('未保存改动 → 章名旁 warn 圆点；保存 → POST /api/prose 创建提案，圆点清除 + "已创建提案待确认"', async () => {
    mockPaths({ '/api/flow': flow, '/api/reconcile': [] })
    mockPost.mockResolvedValue({ proposal_id: 'pr1' })
    render(<ProseEditor />)
    expect(screen.queryByTestId('unsaved-dot')).not.toBeInTheDocument()
    const ta = screen.getByLabelText('正文')
    fireEvent.change(ta, { target: { value: '段一\n\n段二' } })
    expect(screen.getByTestId('unsaved-dot')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: '保存为提案' }))
    await waitFor(() => {
      expect(mockPost).toHaveBeenCalledWith('/api/prose', {
        chapter_id: 'c1', content: '段一\n\n段二',
      })
    })
    expect(screen.getByText(/已创建提案待确认/)).toBeInTheDocument()
    expect(screen.queryByTestId('unsaved-dot')).not.toBeInTheDocument()
  })

  it('保存失败：后端 detail 直显错误条（§5.3），圆点保留', async () => {
    mockPaths({ '/api/flow': flow, '/api/reconcile': [] })
    mockPost.mockRejectedValue(new Error('只读会话：写租约由 web:1 持有'))
    render(<ProseEditor />)
    fireEvent.change(screen.getByLabelText('正文'), { target: { value: '草稿' } })
    fireEvent.click(screen.getByRole('button', { name: '保存为提案' }))
    await waitFor(() => {
      expect(screen.getByRole('alert')).toHaveTextContent('只读会话：写租约由 web:1 持有')
    })
    expect(screen.getByTestId('unsaved-dot')).toBeInTheDocument()
  })

  it('抽取入口：POST /api/writeback/extract → 结果面板（appeared/warnings/cascade major 行/偏差）', async () => {
    mockPaths({ '/api/flow': flow, '/api/reconcile': [] })
    mockPost.mockResolvedValue({
      chapter_id: 'c1',
      proposal_id: null,
      auto_event_seq: 3,
      warnings: ['缺少必要要素：雨夜'],
      appeared: ['江晚'],
      cascade: {
        tier: 'light',
        violations: [{
          level: 'major', rule: 'contradiction',
          message: '属性 x 与当前生效值矛盾', refs: ['n1'],
        }],
        cascade_proposal_id: null,
      },
      deviation: { microbeat: { done: 1, total: 2 }, missing_elements: ['雨夜'] },
    })
    render(<ProseEditor />)
    fireEvent.click(screen.getByRole('button', { name: '抽取事实' }))
    await waitFor(() => {
      expect(mockPost).toHaveBeenCalledWith('/api/writeback/extract', { chapter_id: 'c1' })
      expect(screen.getByTestId('extract-panel')).toBeInTheDocument()
    })
    expect(screen.getByText(/江晚/)).toBeInTheDocument()          // appeared
    expect(screen.getByText('缺少必要要素：雨夜')).toBeInTheDocument()  // warnings
    const vio = screen.getByText('属性 x 与当前生效值矛盾')          // cascade major
    expect(vio.closest('li')).toHaveClass('border-danger')
    expect(vio.closest('li')).toHaveTextContent('major')
    expect(screen.getByText(/微节拍覆盖 1\/2/)).toBeInTheDocument()  // deviation
    expect(screen.getByText(/缺失要素：雨夜/)).toBeInTheDocument()
  })

  it('外部改动（reconcile external_change 非空）→ 编辑器顶部 warn 条 + "重新登记"聚焦该章', () => {
    mockPaths({
      '/api/flow': flow,
      '/api/reconcile': [
        { chapter_id: 'c1', status: 'missing_file' },
        { chapter_id: 'c2', status: 'external_change' },
      ],
    })
    const onSelectChapter = vi.fn()
    render(<ProseEditor onSelectChapter={onSelectChapter} />)
    const bar = screen.getByRole('alert')
    expect(bar).toHaveTextContent('外部改动')
    expect(bar).toHaveTextContent('c2')
    fireEvent.click(screen.getByRole('button', { name: '重新登记' }))
    expect(screen.getByTestId('editor-chapter')).toHaveTextContent('第二章')
    expect(onSelectChapter).toHaveBeenCalledWith({ id: 'c2', name: '第二章' })
  })

  it('只读会话：保存/抽取按钮禁用（写守卫 409 前置）', () => {
    mockPaths({ '/api/flow': flow, '/api/reconcile': [] })
    render(<ProseEditor readonly />)
    expect(screen.getByRole('button', { name: '保存为提案' })).toBeDisabled()
    expect(screen.getByRole('button', { name: '抽取事实' })).toBeDisabled()
  })

  // ---- fix round 1（评审 Important×2）----

  it('选中章加载正文：GET /api/chapters/{id}/prose 初始化编辑区；无行章空白可输入（F1）', () => {
    mockPaths({
      '/api/flow': flow,
      '/api/reconcile': [],
      '/api/chapters/c1/prose': { chapter_id: 'c1', prose: '段一\n\n段二' },
      '/api/chapters/c2/prose': { chapter_id: 'c2', prose: null },
    })
    render(<ProseEditor />)
    const ta = screen.getByLabelText('正文')
    expect(ta).toHaveValue('段一\n\n段二')
    // 基线 = 已加载正文：无未保存改动 → 无 warn 圆点
    expect(screen.queryByTestId('unsaved-dot')).not.toBeInTheDocument()
    // 切到无镜像行的章 → 空白可输入
    fireEvent.click(screen.getByText('第二章'))
    expect(screen.getByLabelText('正文')).toHaveValue('')
    fireEvent.change(screen.getByLabelText('正文'), { target: { value: '新草稿' } })
    expect(screen.getByLabelText('正文')).toHaveValue('新草稿')
  })

  it('未保存改动时切章 → ConfirmDialog，取消不切且草稿保留、确认切换并丢弃（F2）', () => {
    mockPaths({
      '/api/flow': flow,
      '/api/reconcile': [],
      '/api/chapters/c1/prose': { chapter_id: 'c1', prose: '第一章正文' },
      '/api/chapters/c2/prose': { chapter_id: 'c2', prose: '第二章正文' },
    })
    render(<ProseEditor />)
    const ta = screen.getByLabelText('正文')
    fireEvent.change(ta, { target: { value: '未保存草稿' } })
    fireEvent.click(screen.getByText('第二章'))
    expect(screen.getByRole('dialog')).toBeInTheDocument()
    expect(screen.getByText(/有未保存的改动，切换章节将丢弃/)).toBeInTheDocument()
    fireEvent.keyDown(window, { key: 'Escape' })
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    expect(screen.getByTestId('editor-chapter')).toHaveTextContent('第一章')
    expect(screen.getByLabelText('正文')).toHaveValue('未保存草稿')
    // 再次点选并确认 → 切换且丢弃草稿，新章正文为基线
    fireEvent.click(screen.getByText('第二章'))
    fireEvent.click(screen.getByRole('button', { name: '确认' }))
    expect(screen.getByTestId('editor-chapter')).toHaveTextContent('第二章')
    expect(screen.getByLabelText('正文')).toHaveValue('第二章正文')
    expect(screen.queryByTestId('unsaved-dot')).not.toBeInTheDocument()
  })

  it('FlowTree 联动切章（chapterId prop）在未保存时同样弹确认框（F2 三入口）', () => {
    mockPaths({
      '/api/flow': flow,
      '/api/reconcile': [],
      '/api/chapters/c1/prose': { chapter_id: 'c1', prose: '第一章正文' },
      '/api/chapters/c2/prose': { chapter_id: 'c2', prose: '第二章正文' },
    })
    const { rerender } = render(<ProseEditor chapterId="c1" />)
    fireEvent.change(screen.getByLabelText('正文'), { target: { value: '草稿' } })
    rerender(<ProseEditor chapterId="c2" />)          // App 经 FlowTree 改选中章
    expect(screen.getByRole('dialog')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: '确认' }))
    expect(screen.getByTestId('editor-chapter')).toHaveTextContent('第二章')
    expect(screen.getByLabelText('正文')).toHaveValue('第二章正文')
  })

  // ---- final review fix 2（评审 Important：失败 GET 后旧章 data 残留新章下）----

  it('正文加载失败：错误条渲染 + 编辑区清空（旧章正文不残留）+ 保存不可用', () => {
    // c2 的 prose GET 失败（transient 500/断网）：text/savedText 必须重置为空
    // 基线，否则旧章正文留在新章下、作者保存即错章覆盖
    mockUseApi.mockImplementation((path: string) => {
      if (path === '/api/chapters/c2/prose') {
        return { data: null, loading: false, error: '正文加载失败（500）' }
      }
      if (path === '/api/chapters/c1/prose') {
        return { data: { chapter_id: 'c1', prose: '第一章正文' }, loading: false, error: null }
      }
      if (path === '/api/flow') return { data: flow, loading: false, error: null }
      if (path === '/api/reconcile') return { data: [], loading: false, error: null }
      return { data: null, loading: false, error: null }
    })
    render(<ProseEditor />)
    expect(screen.getByLabelText('正文')).toHaveValue('第一章正文')
    fireEvent.click(screen.getByText('第二章'))
    const alert = screen.getByRole('alert')
    expect(alert).toHaveTextContent('正文加载失败（500）')
    // 编辑区为空基线：旧章正文不残留
    expect(screen.getByLabelText('正文')).toHaveValue('')
    // 空基线 → 无未保存圆点 → 保存按钮禁用（防旧内容被存进新章）
    expect(screen.queryByTestId('unsaved-dot')).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: '保存为提案' })).toBeDisabled()
  })

  it('错误条"重试"：重拉正文成功后恢复基线，错误条消失', async () => {
    mockUseApi.mockImplementation((path: string, refreshKey = 0) => {
      if (path === '/api/chapters/c2/prose') {
        return refreshKey === 0
          ? { data: null, loading: false, error: '正文加载失败（500）' }
          : { data: { chapter_id: 'c2', prose: '第二章正文' }, loading: false, error: null }
      }
      if (path === '/api/chapters/c1/prose') {
        return { data: { chapter_id: 'c1', prose: '第一章正文' }, loading: false, error: null }
      }
      if (path === '/api/flow') return { data: flow, loading: false, error: null }
      if (path === '/api/reconcile') return { data: [], loading: false, error: null }
      return { data: null, loading: false, error: null }
    })
    render(<ProseEditor />)
    fireEvent.click(screen.getByText('第二章'))
    expect(screen.getByRole('alert')).toHaveTextContent('正文加载失败（500）')
    fireEvent.click(screen.getByRole('button', { name: '重试' }))
    await waitFor(() => {
      expect(screen.getByLabelText('正文')).toHaveValue('第二章正文')
    })
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
    expect(screen.queryByTestId('unsaved-dot')).not.toBeInTheDocument()
  })

  // ---- Task 4（TC-SH-10 / R5）：拍侧栏 + 合并/删除操作 ----

  const beats = [
    { id: 'b1', name: '开场拍', story_order: 1 },
    { id: 'b2', name: '冲突拍', story_order: 2 },
    { id: 'b3', name: '收束拍', story_order: 3 },
  ]
  const beatPaths = {
    '/api/chapters/c1/beats': beats,
    '/api/stats/foreshadow': { items: [] },
  }

  it('拍侧栏渲染章内拍列表（story_order 序号 + 拍名）', () => {
    mockPaths({ '/api/flow': flow, '/api/reconcile': [], ...beatPaths })
    render(<ProseEditor />)
    expect(screen.getByTestId('beat-sidebar')).toBeInTheDocument()
    const names = screen.getAllByTestId('beat-name').map((el) => el.textContent)
    expect(names).toEqual(['1. 开场拍', '2. 冲突拍', '3. 收束拍'])
  })

  it('合并流：选源拍→点合并→点目标拍→ConfirmDialog 含伏笔迁移预览（N>0 列名称）→确认→POST merge 参数', async () => {
    mockPaths({
      '/api/flow': flow,
      '/api/reconcile': [],
      ...beatPaths,
      '/api/stats/foreshadow': {
        items: [
          { id: 'f1', name: '林中剑', planted_at: 'b1', payoff_beat: null, status: 'planted' },
          { id: 'f2', name: '别处伏笔', planted_at: 'b2', payoff_beat: null, status: 'planted' },
        ],
      },
    })
    mockPost.mockResolvedValue({ merged: true, moved: 7 })
    render(<ProseEditor />)
    fireEvent.click(screen.getByTestId('beat-merge-b1'))       // 选源拍：进入目标点选态
    expect(screen.getByTestId('beat-pick-hint')).toHaveTextContent('开场拍')
    fireEvent.click(screen.getByTestId('beat-target-b2'))      // 点目标拍 → 弹确认框
    expect(screen.getByRole('dialog')).toHaveTextContent('将迁移 1 个伏笔：林中剑')
    fireEvent.click(screen.getByRole('button', { name: '确认' }))
    await waitFor(() => {
      expect(mockPost).toHaveBeenCalledWith('/api/beats/merge', { source: 'b1', target: 'b2' })
    })
    expect(screen.getByTestId('beat-note')).toHaveTextContent('已合并')
  })

  it('合并预览 N=0：对话框显示"无伏笔引用此拍"；取消退出不触发 POST', () => {
    mockPaths({
      '/api/flow': flow,
      '/api/reconcile': [],
      ...beatPaths,
      '/api/stats/foreshadow': {
        items: [
          { id: 'f2', name: '别处伏笔', planted_at: 'b2', payoff_beat: null, status: 'planted' },
        ],
      },
    })
    render(<ProseEditor />)
    fireEvent.click(screen.getByTestId('beat-merge-b1'))
    fireEvent.click(screen.getByTestId('beat-target-b3'))
    expect(screen.getByRole('dialog')).toHaveTextContent('无伏笔引用此拍')
    fireEvent.click(screen.getByRole('button', { name: '取消' }))
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    expect(mockPost).not.toHaveBeenCalled()
  })

  it('删除流：点删除→确认→POST /api/beats/delete {beat_id} + 成功提示', async () => {
    mockPaths({ '/api/flow': flow, '/api/reconcile': [], ...beatPaths })
    mockPost.mockResolvedValue({ deleted: true })
    render(<ProseEditor />)
    fireEvent.click(screen.getByTestId('beat-delete-b3'))
    expect(screen.getByRole('dialog')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: '确认' }))
    await waitFor(() => {
      expect(mockPost).toHaveBeenCalledWith('/api/beats/delete', { beat_id: 'b3' })
    })
    expect(screen.getByTestId('beat-note')).toHaveTextContent('已删除')
  })

  it('拒绝呈现：删除被伏笔引用拍 → 后端 400 detail 红条文案', async () => {
    mockPaths({ '/api/flow': flow, '/api/reconcile': [], ...beatPaths })
    mockPost.mockRejectedValue(
      new Error('该拍承载 1 个伏笔引用，先 merge_beats 到承接拍或迁移伏笔'))
    render(<ProseEditor />)
    fireEvent.click(screen.getByTestId('beat-delete-b1'))
    fireEvent.click(screen.getByRole('button', { name: '确认' }))
    await waitFor(() => {
      expect(screen.getByRole('alert')).toHaveTextContent(
        '该拍承载 1 个伏笔引用，先 merge_beats 到承接拍或迁移伏笔')
    })
  })

  it('只读会话：合并/删除按钮禁用（写守卫 409 前置双保险）', () => {
    mockPaths({ '/api/flow': flow, '/api/reconcile': [], ...beatPaths })
    render(<ProseEditor readonly />)
    expect(screen.getByTestId('beat-merge-b1')).toBeDisabled()
    expect(screen.getByTestId('beat-delete-b1')).toBeDisabled()
  })

  it('保存/抽取在途切章：过期响应丢弃，新章无幽灵圆点/无错章提示（F3）', async () => {
    mockPaths({
      '/api/flow': flow,
      '/api/reconcile': [],
      '/api/chapters/c1/prose': { chapter_id: 'c1', prose: '第一章正文' },
      '/api/chapters/c2/prose': { chapter_id: 'c2', prose: '第二章正文' },
    })
    let resolveSave: ((v: { proposal_id: string }) => void) | undefined
    mockPost.mockImplementationOnce(
      () => new Promise((resolve) => { resolveSave = resolve }))
    render(<ProseEditor />)
    fireEvent.change(screen.getByLabelText('正文'), { target: { value: '未保存草稿' } })
    fireEvent.click(screen.getByRole('button', { name: '保存为提案' }))
    // 保存在途：切章（未保存 → 弹窗确认）
    fireEvent.click(screen.getByText('第二章'))
    fireEvent.click(screen.getByRole('button', { name: '确认' }))
    expect(screen.getByTestId('editor-chapter')).toHaveTextContent('第二章')
    // 过期响应到达 → 丢弃：不落 savedText/提示，不污染新章
    await act(async () => { resolveSave?.({ proposal_id: 'pr1' }) })
    expect(screen.queryByText(/已创建提案待确认/)).not.toBeInTheDocument()
    expect(screen.queryByTestId('unsaved-dot')).not.toBeInTheDocument()
    expect(screen.getByLabelText('正文')).toHaveValue('第二章正文')
  })
})
