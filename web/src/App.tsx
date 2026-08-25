// 三栏布局壳（ui-design-01 §3）：顶栏 + 左流程树 / 中正文 / 右工作区+聊天。
// 子栏内容为占位 stub（T10 FlowTree / T11 ProseEditor / T12 ChatSidebar 实现）；
// 数据获取统一走 useApi（§5.1 骨架屏 / §5.3 错误红条）。
import { useState } from 'react'
import { useApi } from './api'
import type { Session } from './types'
import SessionBanner from './components/SessionBanner'

function Skeleton({ className = 'h-4' }: { className?: string }) {
  return <div data-testid="skeleton" className={`skeleton ${className}`} />
}

export default function App() {
  const session = useApi<Session>('/api/session')
  const [chatCollapsed, setChatCollapsed] = useState(false)

  const data = session.data
  const readonly = data?.readonly ?? false
  // 当前卷·章占位：取 flow 首个卷章（T11 正文页接管真实选择）
  const currentVolume = data?.flow.volumes[0]
  const currentChapter = currentVolume?.chapters[0]

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
            <div className="text-sm text-muted">流程树（T10 实现）</div>
          )}
        </aside>

        {/* 中栏：正文编辑容器（T11） */}
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
            <div className="p-6 text-sm text-muted">正文编辑区（T11 实现）</div>
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
              <div className="text-sm text-muted">
                工作区 tab：提案 / 可视化（T10/T13 实现）
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
                <div className="min-h-0 flex-1 overflow-y-auto p-3 text-sm text-muted">
                  聊天侧栏（T12 实现）——在这里说出你的想法
                </div>
              )}
            </div>
          </div>
        </aside>
      </main>
    </div>
  )
}
