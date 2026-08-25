// 三栏布局壳（ui-design-01 §3）：顶栏 + 左流程树 / 中正文 / 右工作区+聊天。
// 子栏内容：T10 FlowTree / ProposalList / ProposalPanel / GenerateForm 已接线，
// 中栏 ProseEditor（T11）与聊天 ChatSidebar（T12，SSE 流式 + 打字机）；
// 数据获取统一走 useApi（§5.1 骨架屏 / §5.3 错误红条）。
// refreshKey（T12 遗留清偿）：聊天入队提案/确认否决后递增，
// 驱动 ProposalList/FlowTree 以新 key 重拉（T10 遗留③）。
import { useState } from 'react'
import { useApi } from './api'
import type { Session } from './types'
import SessionBanner from './components/SessionBanner'
import FlowTree from './components/FlowTree'
import ProposalList from './components/ProposalList'
import ProposalPanel from './components/ProposalPanel'
import GenerateForm from './components/GenerateForm'
import ProseEditor from './components/ProseEditor'
import ChatSidebar from './components/ChatSidebar'

function Skeleton({ className = 'h-4' }: { className?: string }) {
  return <div data-testid="skeleton" className={`skeleton ${className}`} />
}

export default function App() {
  const session = useApi<Session>('/api/session')
  const [chatCollapsed, setChatCollapsed] = useState(false)
  const [selectedPid, setSelectedPid] = useState<string | null>(null)
  // 当前选中章（T11）：FlowTree / ProseEditor 章节点击双端经此联动，顶栏展示
  const [selectedChapterId, setSelectedChapterId] = useState<string | null>(null)
  // T12 遗留清偿：聊天/面板变更后递增，触发列表与流程树重拉
  const [refreshKey, setRefreshKey] = useState(0)

  const data = session.data
  const readonly = data?.readonly ?? false
  // 当前卷·章：优先选中章所在卷，未选中回落 flow 首个卷章
  const selectedVol = data?.flow.volumes.find(
    (v) => v.chapters.some((c) => c.id === selectedChapterId))
  const currentVolume = selectedVol ?? data?.flow.volumes[0]
  const currentChapter =
    currentVolume?.chapters.find((c) => c.id === selectedChapterId)
    ?? currentVolume?.chapters[0]

  return (
    <div className="flex h-screen flex-col bg-base text-primary">
      {/* 顶栏 48px（§3）：项目名 · 当前卷/章 · 会话状态点 */}
      <header className="flex h-12 shrink-0 items-center gap-4 border-b border-border bg-panel px-4">
        <div className="flex min-w-0 items-center gap-2">
          <span className="text-accent">●</span>
          <span className="truncate text-sm font-medium">{data?.project ?? 'Snowel'}</span>
        </div>
        <div className="flex-1 truncate text-center text-sm text-muted">
          {data && currentVolume
            ? `${currentVolume.name} · ${currentChapter?.name ?? ''}`
            : '卷 · 章'}
        </div>
        <div className="flex shrink-0 items-center gap-3">
          <span className="text-sm text-muted">⌘K</span>
          <span
            data-testid="session-dot"
            title={readonly ? '只读会话' : '写会话'}
            className={`h-2.5 w-2.5 rounded-full ${readonly ? 'bg-warn' : 'bg-ok'}`}
          />
        </div>
      </header>

      {/* 只读横幅 + 错误红条（§3/§5.3） */}
      <SessionBanner readonly={readonly} holder={data?.holder ?? null} />
      {session.error && (
        <div
          data-testid="error-bar"
          role="alert"
          className="shrink-0 border-b border-border bg-danger/15 px-4 py-1.5 text-sm text-danger"
        >
          {session.error}
        </div>
      )}

      {/* 三栏主体（§3）：左 240px / 中 flex（min 480px）/ 右 380px */}
      <main className="flex min-h-0 flex-1">
        {/* 左栏：流程树容器（T10） */}
        <aside
          data-testid="col-flow"
          className="w-60 shrink-0 overflow-y-auto border-r border-border bg-panel p-3"
        >
          {session.loading ? (
            <div className="flex flex-col gap-2">
              <Skeleton className="h-6" />
              <Skeleton />
              <Skeleton />
              <Skeleton />
            </div>
          ) : (
            <FlowTree
              readonly={readonly}
              refreshKey={refreshKey}
              onSelectChapter={(ch) => setSelectedChapterId(ch.id)}
            />
          )}
        </aside>

        {/* 中栏：正文编辑容器（T11 ProseEditor） */}
        <section
          data-testid="col-prose"
          className="min-w-[480px] flex-1 overflow-y-auto bg-base"
        >
          {session.loading ? (
            <div className="p-6">
              <Skeleton className="h-8 w-1/2" />
              <div className="mt-4 flex flex-col gap-2">
                <Skeleton />
                <Skeleton />
                <Skeleton className="w-3/4" />
              </div>
            </div>
          ) : (
            <ProseEditor
              readonly={readonly}
              chapterId={selectedChapterId}
              onSelectChapter={(ch) => setSelectedChapterId(ch.id)}
            />
          )}
        </section>

        {/* 右栏 380px：上工作区 tab / 下聊天侧栏（默认 40% 高，可折叠） */}
        <aside className="flex w-[380px] shrink-0 flex-col border-l border-border bg-panel">
          <div
            data-testid="col-workspace"
            className="min-h-0 flex-1 overflow-y-auto p-3"
          >
            {session.loading ? (
              <div className="flex flex-col gap-2">
                <Skeleton className="h-6" />
                <Skeleton className="h-16" />
                <Skeleton className="h-16" />
              </div>
            ) : (
              <div className="flex flex-col gap-3">
                <GenerateForm readonly={readonly} onGenerated={setSelectedPid} />
                <ProposalList
                  selectedId={selectedPid}
                  refreshKey={refreshKey}
                  onSelect={(p) => setSelectedPid(p.id)}
                />
                <ProposalPanel
                  proposalId={selectedPid}
                  readonly={readonly}
                  onMutated={() => setRefreshKey((k) => k + 1)}
                />
              </div>
            )}
          </div>

          <div
            data-testid="col-chat"
            className={`shrink-0 border-t border-border ${chatCollapsed ? 'h-12' : 'h-[40%]'}`}
          >
            <div className="flex h-full flex-col">
              <div className="flex h-9 shrink-0 items-center justify-between px-3">
                <span className="text-sm text-muted">聊天</span>
                <button
                  data-testid="chat-toggle"
                  type="button"
                  onClick={() => setChatCollapsed((v) => !v)}
                  className="rounded-btn border border-border bg-raised px-2 py-0.5 text-xs text-text-primary"
                >
                  {chatCollapsed ? '展开' : '收起'}
                </button>
              </div>
              {!chatCollapsed && (
                <ChatSidebar
                  readonly={readonly}
                  onGoProposals={() => setRefreshKey((k) => k + 1)}
                />
              )}
            </div>
          </div>
        </aside>
      </main>
    </div>
  )
}
