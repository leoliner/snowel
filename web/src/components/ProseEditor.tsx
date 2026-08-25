// 中栏正文编辑页（ui-design-01 §5.2/§5.9）：章节列表 + 正文编辑区。
// 保存 = 生成 prose 提案走确认（POST /api/prose → T10 提案面板确认后落盘镜像）；
// 未保存改动 = 编辑区章名旁 warn 圆点；外部改动（reconcile external_change）
// = 顶部 warn 条 + "重新登记"（聚焦该章后重新保存为提案）；抽取入口 →
// POST /api/writeback/extract 结果面板（appeared/warnings/cascade/偏差）。
// fix round 1（评审 Important×2）：①选中章经 GET /api/chapters/{id}/prose
// 加载正文（savedText 基线 = 已加载正文，防默认覆盖既有正文）；②未保存改动时
// 切章（列表/FlowTree/重新登记三入口）弹 ConfirmDialog 确认后丢弃；③保存/抽取
// 在途切章 → 过期响应丢弃（await 前后章 id 比对）。
import { useEffect, useRef, useState } from 'react'
import { api, useApi } from '../api'
import type { Chapter, FlowState, ReconcileEntry } from '../types'
import { ViolationList } from './ProposalPanel'
import ConfirmDialog from './ConfirmDialog'

interface ProseEditorProps {
  readonly?: boolean
  // 外部选中章（App 经 FlowTree onSelectChapter 驱动）；null 时默认选首个章节
  chapterId?: string | null
  // 空态引导：切换 App 工作区生成 tab（v1 无 tab，App 可留默认 no-op）
  onGoGenerate?: () => void
  // 编辑器内列表选中回调（App 同步顶栏卷·章 + FlowTree 高亮）
  onSelectChapter?: (chapter: Chapter) => void
}

// GET /api/chapters/{id}/prose 响应（web_server 一比一透传 core chapter_prose）
interface ChapterProse {
  chapter_id: string
  prose: string | null
}

// POST /api/writeback/extract 响应（web_server 一比一透传 core extract_and_writeback）
interface ExtractResult {
  chapter_id: string
  proposal_id: string | null
  auto_event_seq: number | null
  warnings: string[]
  appeared: string[]
  cascade: {
    tier: string
    violations: { level: 'major' | 'minor'; rule: string; message: string; refs: string[] }[]
    cascade_proposal_id: string | null
  } | null
  deviation: {
    microbeat: { done: number; total: number } | null
    missing_elements: string[]
  } | null
}

export default function ProseEditor({
  readonly = false,
  chapterId = null,
  onGoGenerate = () => {},
  onSelectChapter,
}: ProseEditorProps) {
  const { data, loading, error } = useApi<FlowState>('/api/flow')
  const { data: reconcile } = useApi<ReconcileEntry[]>('/api/reconcile')
  const [selectedId, setSelectedId] = useState<string | null>(chapterId ?? null)
  const [pendingChapter, setPendingChapter] = useState<Chapter | null>(null)
  // 选中章正文（fix 1 加载面）；selectedId 未定前的过渡帧用哨兵路径（无行 → null）
  const prosePath = selectedId
    ? `/api/chapters/${selectedId}/prose`
    : '/api/chapters/none/prose'
  const { data: prose, loading: proseLoading } = useApi<ChapterProse>(prosePath)

  const volumes = data?.volumes ?? []
  const chapters = volumes.flatMap((v) => v.chapters)

  // 编辑区本地态：正文 / 已保存基线（未保存圆点 = text !== savedText）
  const [text, setText] = useState('')
  const [savedText, setSavedText] = useState('')
  const [saving, setSaving] = useState(false)
  const [saveError, setSaveError] = useState<string | null>(null)
  const [saveNote, setSaveNote] = useState<string | null>(null)
  const [extracting, setExtracting] = useState(false)
  const [extractError, setExtractError] = useState<string | null>(null)
  const [extractResult, setExtractResult] = useState<ExtractResult | null>(null)

  const selected = chapters.find((c) => c.id === selectedId) ?? null
  const entries = Array.isArray(reconcile) ? reconcile : []
  const statusByChapter = new Map(entries.map((r) => [r.chapter_id, r.status]))
  const externalChanged = entries.filter((r) => r.status === 'external_change')
  const unsaved = text !== savedText

  // 当前选中章 ref（fix 3）：doSave/doExtract 闭包里的 selectedId 是点击当帧
  // 的旧值，切章后过期响应需经 ref 与目标章比对丢弃
  const selectedIdRef = useRef(selectedId)
  useEffect(() => {
    selectedIdRef.current = selectedId
  }, [selectedId])

  // 选中章联动：外部 prop（App/FlowTree）优先；无选中时回落首个章节。
  // 有未保存改动时切章须过 ConfirmDialog（fix 2）——data 为 useApi 稳定引用，
  // deps 不落派生数组避免每渲染重跑
  useEffect(() => {
    if (chapterId && chapterId !== selectedId) {
      if (unsaved) {
        const target = data?.volumes?.flatMap((v) => v.chapters)
          .find((c) => c.id === chapterId) ?? null
        setPendingChapter(target)
      } else {
        setSelectedId(chapterId)
      }
    } else if (!selectedId) {
      const first = data?.volumes?.[0]?.chapters?.[0]
      if (first) setSelectedId(first.id)
    }
  }, [chapterId, selectedId, unsaved, data])

  // 切章重置操作态（正文 text/savedText 由 prose 加载 effect 初始化）
  useEffect(() => {
    setSaving(false)
    setExtracting(false)
    setSaveError(null)
    setSaveNote(null)
    setExtractError(null)
    setExtractResult(null)
  }, [selectedId])

  // 正文加载（fix 1）：选中章正文到达后初始化 text/savedText 基线（savedText
  // 从"空串"改为"已加载正文"——作者打开既有正文的章不再默认覆盖）
  useEffect(() => {
    if (!prose || prose.chapter_id !== selectedId) return
    const loaded = prose.prose ?? ''
    setText(loaded)
    setSavedText(loaded)
  }, [prose, selectedId])

  const doSelect = (ch: Chapter) => {
    setSelectedId(ch.id)
    onSelectChapter?.(ch)
  }

  // 切章统一入口（列表 / 重新登记）：未保存改动 → 弹确认框，确认后才切（fix 2）
  const requestSelect = (ch: Chapter) => {
    if (ch.id === selectedId) return
    if (unsaved) {
      setPendingChapter(ch)
    } else {
      doSelect(ch)
    }
  }

  const doSave = async () => {
    if (!selected || !unsaved) return
    const targetId = selected.id          // await 前捕获章 id（fix 3）
    setSaving(true)
    setSaveError(null)
    try {
      const res = await api.post<{ proposal_id: string }>('/api/prose', {
        chapter_id: targetId, content: text,
      })
      if (selectedIdRef.current !== targetId) return   // 切章后过期响应：丢弃
      setSavedText(text)
      setSaveNote(`已创建提案待确认（提案 ${res.proposal_id}）——确认后写入镜像文件`)
    } catch (err) {
      if (selectedIdRef.current !== targetId) return
      setSaveError(err instanceof Error ? err.message : String(err))
    } finally {
      if (selectedIdRef.current === targetId) setSaving(false)
    }
  }

  const doExtract = async () => {
    if (!selected) return
    const targetId = selected.id          // await 前捕获章 id（fix 3）
    setExtracting(true)
    setExtractError(null)
    try {
      const res = await api.post<ExtractResult>('/api/writeback/extract', {
        chapter_id: targetId,
      })
      if (selectedIdRef.current !== targetId) return
      setExtractResult(res)
    } catch (err) {
      if (selectedIdRef.current !== targetId) return
      setExtractError(err instanceof Error ? err.message : String(err))
    } finally {
      if (selectedIdRef.current === targetId) setExtracting(false)
    }
  }

  if (loading) {
    return (
      <div data-testid="prose-skeleton" className="flex flex-col gap-2 p-6">
        <div className="skeleton h-6 w-1/2" />
        <div className="skeleton h-4" />
        <div className="skeleton h-4" />
        <div className="skeleton h-4" />
      </div>
    )
  }
  if (error) {
    return (
      <div role="alert" className="m-4 rounded-card bg-danger/15 px-3 py-2 text-sm text-danger">
        {error}
      </div>
    )
  }

  // 无章空态（§5.2）：引导去生成第一个场景提案
  if (chapters.length === 0) {
    return (
      <div className="flex h-full flex-col items-center justify-center gap-3 p-6">
        <p className="text-sm text-muted">还没有章节——生成第一个场景提案</p>
        <button
          type="button"
          onClick={onGoGenerate}
          className="rounded-btn bg-accent px-3 py-1.5 text-sm text-base hover:brightness-110"
        >
          去生成
        </button>
      </div>
    )
  }

  const writeDisabled = readonly || saving || extracting

  return (
    <div data-testid="prose-editor" className="flex h-full">
      {/* 章节列表（含对账状态 chip） */}
      <nav className="flex w-40 shrink-0 flex-col gap-0.5 overflow-y-auto border-r border-border p-2">
        {chapters.map((ch) => {
          const status = statusByChapter.get(ch.id)
          return (
            <button
              key={ch.id}
              type="button"
              onClick={() => requestSelect(ch)}
              className={`flex w-full items-center gap-1 truncate rounded-input px-2 py-1 text-left text-sm hover:bg-raised ${
                selectedId === ch.id ? 'bg-raised text-primary' : 'text-muted'
              }`}
            >
              <span className="min-w-0 flex-1 truncate">{ch.name}</span>
              {status === 'missing_file' && (
                <span className="shrink-0 rounded-chip bg-warn/15 px-1 py-0.5 text-xs text-warn">
                  镜像缺失
                </span>
              )}
              {status === 'external_change' && (
                <span className="shrink-0 rounded-chip bg-warn/15 px-1 py-0.5 text-xs text-warn">
                  外部改动
                </span>
              )}
            </button>
          )
        })}
      </nav>

      {/* 编辑区 */}
      <div className="flex min-w-0 flex-1 flex-col">
        {/* 外部改动 warn 条（§5.9）：列出变更文件 + "重新登记"聚焦该章 */}
        {externalChanged.length > 0 && (
          <div
            role="alert"
            className="flex flex-wrap items-center gap-2 border-b border-warn bg-warn/10 px-4 py-1.5 text-xs text-warn"
          >
            <span>检测到外部改动（镜像文件在编辑器外被修改）：</span>
            <span className="font-mono">{externalChanged.map((r) => r.chapter_id).join('、')}</span>
            <button
              type="button"
              onClick={() => {
                const first = chapters.find((c) => c.id === externalChanged[0]?.chapter_id)
                if (first) requestSelect(first)
              }}
              className="ml-auto rounded-chip border border-warn px-2 py-0.5 hover:bg-warn/20"
            >
              重新登记
            </button>
          </div>
        )}

        {/* 编辑区头：章名 + 未保存 warn 圆点 + 操作（保存为提案 / 抽取事实） */}
        <header className="flex items-center gap-2 border-b border-border px-4 py-2">
          <h2 data-testid="editor-chapter" className="truncate text-sm font-medium text-primary">
            {selected?.name ?? ''}
          </h2>
          {unsaved && (
            <span
              data-testid="unsaved-dot"
              title="有未保存改动"
              className="h-2 w-2 shrink-0 rounded-full bg-warn"
            />
          )}
          <div className="ml-auto flex shrink-0 gap-2">
            <button
              type="button"
              disabled={writeDisabled || !unsaved}
              onClick={doSave}
              className="rounded-btn border border-border bg-raised px-3 py-1 text-xs text-primary hover:bg-border disabled:cursor-not-allowed disabled:opacity-40"
            >
              {saving ? '处理中…' : '保存为提案'}
            </button>
            <button
              type="button"
              disabled={writeDisabled}
              onClick={doExtract}
              className="rounded-btn border border-border bg-raised px-3 py-1 text-xs text-primary hover:bg-border disabled:cursor-not-allowed disabled:opacity-40"
            >
              {extracting ? '处理中…' : '抽取事实'}
            </button>
          </div>
        </header>

        {/* 正文编辑区（§5.9：font-prose + text-prose + 42em 行宽居中） */}
        <div className="min-h-0 flex-1 overflow-y-auto p-6">
          {proseLoading ? (
            <div className="flex flex-col gap-2" data-testid="prose-loading">
              <div className="skeleton h-6 w-2/3" />
              <div className="skeleton h-4" />
              <div className="skeleton h-4" />
              <div className="skeleton h-4 w-3/4" />
            </div>
          ) : (
            <>
              <textarea
                id="prose-text"
                aria-label="正文"
                value={text}
                disabled={readonly}
                onChange={(e) => setText(e.target.value)}
                placeholder="正文草稿——段落之间以空行分隔…"
                className="font-prose text-prose mx-auto block min-h-[24em] w-full max-w-[42em] resize-y rounded-input border border-border bg-base px-4 py-3 leading-relaxed placeholder:text-muted focus:border-accent"
              />

              {saveError && (
                <div role="alert" className="mt-3 rounded-input bg-danger/15 px-3 py-2 text-sm text-danger">
                  {saveError}
                </div>
              )}
              {saveNote && (
                <div role="status" className="mt-3 rounded-input bg-ok/10 px-3 py-2 text-sm text-ok">
                  {saveNote}
                </div>
              )}
              {extractError && (
                <div role="alert" className="mt-3 rounded-input bg-danger/15 px-3 py-2 text-sm text-danger">
                  {extractError}
                </div>
              )}

              {/* 抽取结果面板（appeared/warnings/cascade/偏差 deviation） */}
              {extractResult && (
                <div
                  data-testid="extract-panel"
                  className="mt-3 flex flex-col gap-2 rounded-card border border-border bg-raised/40 p-3"
                >
                  <div className="text-xs text-muted">抽取结果（{extractResult.chapter_id}）</div>
                  {extractResult.appeared.length > 0 && (
                    <div className="text-sm text-primary">
                      出现：{extractResult.appeared.join('、')}
                    </div>
                  )}
                  {extractResult.warnings.length > 0 && (
                    <ul className="flex flex-col gap-1">
                      {extractResult.warnings.map((w, i) => (
                        <li key={i} className="rounded-input border-l-2 border-warn bg-warn/10 px-2 py-1 text-sm text-warn">
                          {w}
                        </li>
                      ))}
                    </ul>
                  )}
                  {extractResult.cascade && extractResult.cascade.violations.length > 0 && (
                    <ViolationList violations={extractResult.cascade.violations} />
                  )}
                  {extractResult.cascade?.cascade_proposal_id && (
                    <div className="rounded-input bg-raised px-2 py-1 text-xs text-muted">
                      已入队级联修订提案：{extractResult.cascade.cascade_proposal_id}
                    </div>
                  )}
                  {extractResult.deviation && (
                    <div className="flex flex-col gap-0.5 text-xs text-muted">
                      {extractResult.deviation.microbeat && (
                        <div>
                          微节拍覆盖 {extractResult.deviation.microbeat.done}/{extractResult.deviation.microbeat.total}
                        </div>
                      )}
                      {extractResult.deviation.missing_elements.length > 0 && (
                        <div>缺失要素：{extractResult.deviation.missing_elements.join('、')}</div>
                      )}
                    </div>
                  )}
                </div>
              )}
            </>
          )}
        </div>
      </div>

      {/* 切章确认（fix 2）：有未保存改动时丢弃草稿须二次确认 */}
      {pendingChapter && (
        <ConfirmDialog
          title="切换章节"
          consequence="有未保存的改动，切换章节将丢弃。"
          onConfirm={() => {
            doSelect(pendingChapter)
            setPendingChapter(null)
          }}
          onCancel={() => setPendingChapter(null)}
        />
      )}
    </div>
  )
}
