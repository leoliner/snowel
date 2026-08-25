// 右栏工作区顶部标签页（ui-design-01 §3）：提案 / 可视化互斥切换。
// activeTab 状态提升到 App（T13：ChatSidebar 的 onGoProposals 可切回"提案"tab）；
// 提案 tab 渲染 children（GenerateForm/ProposalList/ProposalPanel 既有内容），
// 可视化 tab 渲染四个统计图区段（W4 纯统计区，各图自取 /api/stats/*）。
import PovChart from './PovChart'
import ForeshadowMap from './ForeshadowMap'
import RelationsGraph from './RelationsGraph'
import PacingBars from './PacingBars'

export type WorkspaceTab = 'proposals' | 'viz'

interface VizPanelProps {
  activeTab: WorkspaceTab
  onTabChange: (tab: WorkspaceTab) => void
  children: React.ReactNode
}

const TABS: { key: WorkspaceTab; label: string }[] = [
  { key: 'proposals', label: '提案' },
  { key: 'viz', label: '可视化' },
]

export default function VizPanel({ activeTab, onTabChange, children }: VizPanelProps) {
  return (
    <div data-testid="viz-panel" className="flex flex-col gap-3">
      <div role="tablist" className="flex gap-1">
        {TABS.map((t) => (
          <button
            key={t.key}
            type="button"
            role="tab"
            aria-selected={activeTab === t.key}
            onClick={() => onTabChange(t.key)}
            className={`rounded-chip px-2 py-1 text-xs ${
              activeTab === t.key
                ? 'bg-accent text-base'
                : 'bg-raised text-muted hover:text-primary'
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      {activeTab === 'proposals' ? (
        children
      ) : (
        <div data-testid="viz-sections" className="flex flex-col gap-4">
          <section data-testid="viz-pov" className="flex flex-col gap-1">
            <h3 className="text-xs text-muted">POV 分布</h3>
            <PovChart />
          </section>
          <section data-testid="viz-foreshadow" className="flex flex-col gap-1">
            <h3 className="text-xs text-muted">伏笔时间线</h3>
            <ForeshadowMap />
          </section>
          <section data-testid="viz-relations" className="flex flex-col gap-1">
            <h3 className="text-xs text-muted">角色关系</h3>
            <RelationsGraph />
          </section>
          <section data-testid="viz-pacing" className="flex flex-col gap-1">
            <h3 className="text-xs text-muted">章节节奏</h3>
            <PacingBars />
          </section>
        </div>
      )}
    </div>
  )
}
