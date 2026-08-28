import { describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import PovChart from './PovChart'
import ForeshadowMap, { DOT_R, W as MAP_W } from './ForeshadowMap'
import RelationsGraph from './RelationsGraph'
import PacingBars from './PacingBars'
import VizPanel from './VizPanel'
import { useApi } from '../api'
import type {
  ForeshadowStatsResponse,
  PacingStatsResponse,
  PovStatsResponse,
  RelationsStatsResponse,
} from '../types'

// 统计图各自经 useApi 自取 /api/stats/*（与 ProposalList/FlowTree 同模式）
vi.mock('../api', () => ({
  useApi: vi.fn(),
  api: { get: vi.fn(), post: vi.fn() },
}))

const mockUseApi = vi.mocked(useApi)

function mockData<T>(data: T) {
  mockUseApi.mockReturnValue({ data, loading: false, error: null })
}

describe('PovChart（分卷 POV 堆叠条，W4）', () => {
  it('每卷一行堆叠条：段数 = POV 种数合计，语义色循环（accent/ok/warn/danger…）', () => {
    mockData<PovStatsResponse>({
      by_volume: [
        { volume_id: 'v1', volume_name: '卷一', counts: { 江晚: 2, 沈眠: 1 } },
        { volume_id: null, volume_name: null, counts: { 路人: 1 } },
      ],
    })
    render(<PovChart />)
    const svg = screen.getByTestId('pov-chart')
    const rects = svg.querySelectorAll('rect')
    expect(rects).toHaveLength(3) // 卷一 2 段 + 未分卷 1 段
    expect(rects[0]).toHaveClass('fill-accent')
    expect(rects[1]).toHaveClass('fill-ok')
    expect(rects[2]).toHaveClass('fill-accent') // 回绕到循环首色
    // 卷名轴标签；volume_name 为 null 聚合为"未分卷"
    expect(svg.textContent).toContain('卷一')
    expect(svg.textContent).toContain('未分卷')
  })

  it('空数据渲染"暂无 POV 数据"占位卡（ui-design-01 §5.2）', () => {
    mockData<PovStatsResponse>({ by_volume: [] })
    render(<PovChart />)
    expect(screen.getByText('暂无 POV 数据')).toBeInTheDocument()
  })
})

describe('ForeshadowMap（伏笔时间线，W4）', () => {
  it('paid/stale 画 planted→payoff 区间条（fill-ok / fill-danger），planted 画 warn 圆点', () => {
    mockData<ForeshadowStatsResponse>({
      items: [
        { id: 'f1', name: '怀表', planted_at: 'mb1', payoff_beat: null, status: 'planted' },
        { id: 'f2', name: '铜币', planted_at: 'mb1', payoff_beat: 'mb5', status: 'paid' },
        { id: 'f3', name: '钥匙', planted_at: 'mb1', payoff_beat: 'mb900001', status: 'stale' },
      ],
    })
    render(<ForeshadowMap />)
    const svg = screen.getByTestId('foreshadow-map')
    const rects = svg.querySelectorAll('rect')
    expect(rects).toHaveLength(2) // paid + stale 各一条区间条
    expect(rects[0]).toHaveClass('fill-ok')
    expect(rects[1]).toHaveClass('fill-danger')
    const dots = svg.querySelectorAll('circle')
    expect(dots).toHaveLength(1) // 仅 planted 的伏笔一个圆点
    expect(dots[0]).toHaveClass('fill-warn')
    // x 轴拍序标签（text-muted，长 id 截断）
    expect(svg.textContent).toContain('mb1')
    expect(svg.textContent).toContain('mb5')
    expect(svg.textContent).toContain('mb9000…')
    // §2.1 约定：语义色必配文字标签（图例）
    expect(screen.getByText('已种植')).toBeInTheDocument()
    expect(screen.getByText('已回收')).toBeInTheDocument()
    expect(screen.getByText('失效')).toBeInTheDocument()
  })

  it('空数据渲染"暂无伏笔"占位卡（§5.2）', () => {
    mockData<ForeshadowStatsResponse>({ items: [] })
    render(<ForeshadowMap />)
    expect(screen.getByText('暂无伏笔')).toBeInTheDocument()
  })

  it('35 拍不溢出画布宽：slot 上限化压缩，条/点末端 ≤ 画布宽（L22#5）', () => {
    const beats = Array.from({ length: 35 }, (_, i) => `mb${i + 1}`)
    mockData<ForeshadowStatsResponse>({
      items: beats.map((b, i) => ({
        id: `f${i + 1}`,
        name: `伏笔${i + 1}`,
        planted_at: b,
        // 偶数拍回收为下拍 → 区间条；尾拍仅种植 → 圆点，两类几何都覆盖
        payoff_beat: i % 2 === 0 && i + 1 < beats.length ? beats[i + 1] : null,
        status: i % 2 === 0 && i + 1 < beats.length ? 'paid' : 'planted',
      })),
    })
    render(<ForeshadowMap />)
    const host = screen.getByTestId('foreshadow-map')
    const svg = host.querySelector('svg') as SVGSVGElement
    const W = Number(svg.getAttribute('width'))
    // 画布宽与组件导出常量同源（W/DOT_R 解耦，minor 池）
    expect(W).toBe(MAP_W)
    // 区间条右端 = x + width 不超画布；圆点右缘 = cx + DOT_R 不超画布
    svg.querySelectorAll('rect').forEach((r) => {
      expect(Number(r.getAttribute('x')) + Number(r.getAttribute('width'))).toBeLessThanOrEqual(W)
    })
    svg.querySelectorAll('circle').forEach((c) => {
      expect(Number(c.getAttribute('cx')) + DOT_R).toBeLessThanOrEqual(W)
    })
  })
})

describe('RelationsGraph（角色关系圆环图，W4）', () => {
  it('节点圆点（accent）+ 关系连线（muted）+ 节点名标注', () => {
    mockData<RelationsStatsResponse>({
      nodes: [
        { id: 'a', types: '["Character"]', name: '江晚', props: {}, active: 1 },
        { id: 'b', types: '["Character"]', name: '沈眠', props: {}, active: 1 },
        { id: 'c', types: '["Character"]', name: '林晚', props: {}, active: 1 },
      ],
      edges: [
        { id: 'e1', src: 'a', dst: 'b', kind: 'KNOWS', props: {} },
        { id: 'e2', src: 'b', dst: 'c', kind: 'KNOWS', props: {} },
      ],
    })
    render(<RelationsGraph />)
    const svg = screen.getByTestId('relations-graph')
    const lines = svg.querySelectorAll('line')
    expect(lines).toHaveLength(2)
    expect(lines[0]).toHaveClass('stroke-muted')
    const dots = svg.querySelectorAll('circle')
    expect(dots).toHaveLength(3)
    expect(dots[0]).toHaveClass('fill-accent')
    expect(svg.textContent).toContain('江晚')
    expect(svg.textContent).toContain('沈眠')
    expect(svg.textContent).toContain('林晚')
  })

  it('空数据渲染"暂无角色关系"占位卡（§5.2）', () => {
    mockData<RelationsStatsResponse>({ nodes: [], edges: [] })
    render(<RelationsGraph />)
    expect(screen.getByText('暂无角色关系')).toBeInTheDocument()
  })
})

describe('PacingBars（章节节奏双条形，W4）', () => {
  it('每章拍数（fill-accent）与段落数（fill-ok）双条并排，章名轴标签', () => {
    mockData<PacingStatsResponse>({
      chapters: [
        { chapter_id: 'ch1', name: '第一章', beats: 2, paragraphs: 3 },
        { chapter_id: 'ch2', name: '第二章', beats: 1, paragraphs: 0 },
      ],
    })
    render(<PacingBars />)
    const svg = screen.getByTestId('pacing-bars')
    const rects = svg.querySelectorAll('rect')
    expect(rects).toHaveLength(4) // 每章两条
    const accents = [...rects].filter((r) => r.classList.contains('fill-accent'))
    const oks = [...rects].filter((r) => r.classList.contains('fill-ok'))
    expect(accents).toHaveLength(2)
    expect(oks).toHaveLength(2)
    expect(svg.textContent).toContain('第一章')
    expect(svg.textContent).toContain('第二章')
  })

  it('空数据渲染"暂无章节"占位卡（§5.2）', () => {
    mockData<PacingStatsResponse>({ chapters: [] })
    render(<PacingBars />)
    expect(screen.getByText('暂无章节')).toBeInTheDocument()
  })
})

describe('VizPanel（工作区标签页：提案/可视化互斥切换，ui-design-01 §3）', () => {
  it('提案 tab 渲染 children，不挂载统计图', () => {
    render(
      <VizPanel activeTab="proposals" onTabChange={() => {}}>
        <div data-testid="proposals-content">提案面板</div>
      </VizPanel>,
    )
    expect(screen.getByTestId('proposals-content')).toBeInTheDocument()
    expect(screen.queryByTestId('viz-sections')).not.toBeInTheDocument()
    expect(screen.getByRole('tab', { name: '提案' })).toHaveAttribute('aria-selected', 'true')
    expect(screen.getByRole('tab', { name: '可视化' })).toHaveAttribute('aria-selected', 'false')
  })

  it('可视化 tab 渲染四个统计图区段（互斥隐藏提案内容），空统计显示四空态', () => {
    // 四图各取各的 /api/stats/* 路径，空数据 → 各自空态
    mockUseApi.mockImplementation((path) => {
      if (path === '/api/stats/pov') return { data: { by_volume: [] } as PovStatsResponse, loading: false, error: null }
      if (path === '/api/stats/foreshadow') return { data: { items: [] } as ForeshadowStatsResponse, loading: false, error: null }
      if (path === '/api/stats/relations') return { data: { nodes: [], edges: [] } as RelationsStatsResponse, loading: false, error: null }
      if (path === '/api/stats/pacing') return { data: { chapters: [] } as PacingStatsResponse, loading: false, error: null }
      return { data: null, loading: false, error: null }
    })
    const { rerender } = render(
      <VizPanel activeTab="proposals" onTabChange={() => {}}>
        <div data-testid="proposals-content">提案面板</div>
      </VizPanel>,
    )
    rerender(
      <VizPanel activeTab="viz" onTabChange={() => {}}>
        <div data-testid="proposals-content">提案面板</div>
      </VizPanel>,
    )
    expect(screen.queryByTestId('proposals-content')).not.toBeInTheDocument()
    expect(screen.getByTestId('viz-sections')).toBeInTheDocument()
    expect(screen.getByText('POV 分布')).toBeInTheDocument()
    expect(screen.getByText('伏笔时间线')).toBeInTheDocument()
    expect(screen.getByText('角色关系')).toBeInTheDocument()
    expect(screen.getByText('章节节奏')).toBeInTheDocument()
    expect(screen.getByText('暂无 POV 数据')).toBeInTheDocument()
    expect(screen.getByText('暂无伏笔')).toBeInTheDocument()
    expect(screen.getByText('暂无角色关系')).toBeInTheDocument()
    expect(screen.getByText('暂无章节')).toBeInTheDocument()
  })
})
