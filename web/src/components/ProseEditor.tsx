// 中栏正文编辑页（ui-design-01 §5.2/§5.9）：章节列表 + 正文编辑区。
// 保存 = 生成 prose 提案走确认（POST /api/prose → T10 提案面板确认后落盘镜像）；
// 未保存改动 = 编辑区章名旁 warn 圆点；外部改动（reconcile external_change）
// = 顶部 warn 条 + "重新登记"（聚焦该章后重新保存为提案）；抽取入口 →
// POST /api/writeback/extract 结果面板（appeared/warnings/cascade/偏差）。
// 拍侧栏（TC-SH-10 / R5）：右缘拍列表（story_order 序）+ 每拍合并/删除——
// 合并两段式（选源拍 → 点选目标拍 → ConfirmDialog 含伏笔迁移预览，预览 =
// stats/foreshadow 前端过滤 planted_at === source，取数失败不阻塞对话框）；
// 400 detail（拒绝文案）红条呈现；成功 onMutated 刷新（fix 3 范式防过期响应）。
// fix round 1（评审 Important×2）：①选中章经 GET /api/chapters/{id}/prose
// 加载正文（savedText 基线 = 已加载正文，防默认覆盖既有正文）；②未保存改动时
// 切章（列表/FlowTree/重新登记三入口）弹 ConfirmDialog 确认后丢弃；③保存/抽取
// 在途切章 → 过期响应丢弃（await 前后章 id 比对）。
import { useEffect, useRef, useState } from 'react'
import { api, useApi } from '../api'
import type { Chapter, ChapterBeat, FlowState, ForeshadowStatsResponse, ReconcileEntry } from '../types'
import { ViolationList } from './ProposalPanel'
import ConfirmDialog from './ConfirmDialog'
import { BEAT_LABELS } from './labels'

interface ProseEditorProps {
  readonly?: boolean
  // 外部选中章（App 经 FlowTree onSelectChapter 驱动）；null 时默认选首个章节
  chapterId?: string | null
  // 空态引导：切换 App 工作区"提案"tab（App 已接线 onGoGenerate，L22#3）
  onGoGenerate?: () => void
  // 编辑器内列表选中回调（App 同步顶栏卷·章 + FlowTree 高亮）
  onSelectChapter?: (chapter: Chapter) => void
  // 拍合并/删除成功回调（App 递增 refreshKey → FlowTree 等同步重拉，TC-SH-10）
  onMutated?: () => void
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

// 拍侧栏待确认操作（TC-SH-10）：合并（source 并入 target）/ 删除单拍
type BeatOp =
  | { kind: 'merge'; source: ChapterBeat; target: ChapterBeat }
  | { kind: 'delete'; beat: ChapterBeat }

export default function ProseEditor({
  readonly = false,
  chapterId = null,
  onGoGenerate = () => {},
  onSelectChapter,
  onMutated,
}: ProseEditorProps) {
  const { data, loading, error } = useApi<FlowState>('/api/flow')
  const { data: reconcile } = useApi<ReconcileEntry[]>('/api/reconcile')
  const [selectedId, setSelectedId] = useState<string | null>(chapterId ?? null)
  const [pendingChapter, setPendingChapter] = useState<Chapter | null>(null)
  // 选中章正文（fix 1 加载面）；selectedId 未定前的过渡帧用哨兵路径（无行 → null）
  const prosePath = selectedId
    ? `/api/chapters/${selectedId}/prose`
    : '/api/chapters/none/prose'
  // final review fix 2：proseError 消费 + proseRetry（错误条"重试"重拉）并入 key
  const [proseRetry, setProseRetry] = useState(0)
  const { data: prose, loading: proseLoading, error: proseError } =
    useApi<ChapterProse>(prosePath, proseRetry)

  // 拍侧栏数据面（TC-SH-10）：章内拍列表（story_order 稳定序，后端排好）+
  // 伏笔全集（R2：前端过滤 planted_at === source 得迁移预览，零后端改动）。
  // beatRefresh 成功合并/删除后递增重拉；selectedId 未定前用哨兵路径（同 prose）
  const [beatRefresh, setBeatRefresh] = useState(0)
  const beatsPath = selectedId
    ? `/api/chapters/${selectedId}/beats`
    : '/api/chapters/none/beats'
  const { data: beatsData, error: beatsError } =
    useApi<ChapterBeat[]>(beatsPath, beatRefresh)
  const { data: foreshadowData } = useApi<ForeshadowStatsResponse>('/api/stats/foreshadow')

  const volumes = data?.volumes ?? []
  const chapters = volumes.flatMap((v) => v.chapters)
  // 非数组兜底（App.test 全路径 mock 兜底同款）：beats 取数失败/未到达 → 空列表
  const beats = Array.isArray(beatsData) ? beatsData : []
  const foreshadows = foreshadowData?.items ?? []

  // 编辑区本地态：正文 / 已保存基线（未保存圆点 = text !== savedText）
  const [text, setText] = useState('')
  const [savedText, setSavedText] = useState('')
  const [saving, setSaving] = useState(false)
  const [saveError, setSaveError] = useState<string | null>(null)
  const [saveNote, setSaveNote] = useState<string | null>(null)
  const [extracting, setExtracting] = useState(false)
  const [extractError, setExtractError] = useState<string | null>(null)
  const [extractResult, setExtractResult] = useState<ExtractResult | null>(null)

  // 拍侧栏操作态（TC-SH-10）：busy 防重入（writeDisabled 模式）/ 错误红条 /
  // 成功提示 / 合并目标点选中的源拍 / 待确认操作（ConfirmDialog）
  const [beatBusy, setBeatBusy] = useState(false)
  const [beatError, setBeatError] = useState<string | null>(null)
  const [beatNote, setBeatNote] = useState<string | null>(null)
  const [mergeSource, setMergeSource] = useState<ChapterBeat | null>(null)
  const [beatOp, setBeatOp] = useState<BeatOp | null>(null)

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
    setBeatBusy(false)
    setBeatError(null)
    setBeatNote(null)
    setMergeSource(null)
    setBeatOp(null)
  }, [selectedId])

  // 正文加载（fix 1 + final review fix 2）：选中章正文到达后初始化 text/savedText
  // 基线（savedText 从"空串"改为"已加载正文"——作者打开既有正文的章不再默认覆盖）。
  // 加载失败（或 data 非当前章——切章过渡帧/哨兵）→ 清空基线：useApi 失败不清
  // data，旧章正文若残留新章下，作者保存即错章覆盖（评审 finding 2）
  useEffect(() => {
    if (proseError || !prose || prose.chapter_id !== selectedId) {
      setText('')
      setSavedText('')
      return
    }
    const loaded = prose.prose ?? ''
    setText(loaded)
    setSavedText(loaded)
  }, [prose, proseError, selectedId])

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

  // 伏笔迁移预览（R2）：stats/foreshadow 前端过滤 planted_at === source；
  // 取数失败（foreshadows 空）不阻塞对话框显示——N=0 文案兜底
  const foreshadowPreview = (sourceId: string) => {
    const list = foreshadows.filter((f) => f.planted_at === sourceId)
    if (list.length === 0) return BEAT_LABELS.noForeshadow
    return `将迁移 ${list.length} 个伏笔：${list.map((f) => f.name).join('、')}`
  }

  // 拍合并/删除（TC-SH-10）：确认后 POST，成功 → 提示 + 重拉拍列表 + onMutated；
  // 400 detail（拒绝文案/只读 409）红条呈现；切章后过期响应丢弃（fix 3 范式）
  const runBeatOp = async (op: BeatOp) => {
    const atId = selectedIdRef.current
    setBeatBusy(true)
    setBeatError(null)
    try {
      if (op.kind === 'merge') {
        await api.post('/api/beats/merge', { source: op.source.id, target: op.target.id })
        if (selectedIdRef.current !== atId) return
        setBeatNote(`已合并「${op.source.name}」→「${op.target.name}」`)
      } else {
        await api.post('/api/beats/delete', { beat_id: op.beat.id })
        if (selectedIdRef.current !== atId) return
        setBeatNote(`已删除拍「${op.beat.name}」`)
      }
      setMergeSource(null)
      setBeatOp(null)
      setBeatRefresh((k) => k + 1)
      onMutated?.()
    } catch (err) {
      if (selectedIdRef.current !== atId) return
      setBeatError(err instanceof Error ? err.message : String(err))
      setBeatOp(null)
    } finally {
      if (selectedIdRef.current === atId) setBeatBusy(false)
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
  const beatDisabled = readonly || beatBusy

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
              {/* 正文加载失败（final review fix 2）：错误条 + 重试；编辑区为空
                  基线（text/savedText 已清空），防旧章正文被误存进新章 */}
              {proseError && (
                <div
                  role="alert"
                  className="mb-3 flex flex-wrap items-center gap-2 rounded-input bg-danger/15 px-3 py-2 text-sm text-danger"
                >
                  <span className="min-w-0 flex-1">
                    正文加载失败：{proseError}
                  </span>
                  <button
                    type="button"
                    onClick={() => setProseRetry((n) => n + 1)}
                    className="shrink-0 rounded-chip border border-danger/40 px-2 py-0.5 text-xs hover:bg-danger/20"
                  >
                    重试
                  </button>
                </div>
              )}
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

      {/* 拍侧栏（TC-SH-10 / R5）：章内拍列表 + 合并/删除；合并两段式——
          选源拍后其余拍显示"并入此拍"，点选目标弹确认框（含伏笔迁移预览） */}
      <aside
        data-testid="beat-sidebar"
        className="flex w-56 shrink-0 flex-col gap-1 overflow-y-auto border-l border-border p-2"
      >
        <div className="flex items-center justify-between">
          <h3 className="text-xs font-medium text-muted">{BEAT_LABELS.panelTitle}</h3>
          {mergeSource && (
            <button
              type="button"
              onClick={() => setMergeSource(null)}
              className="rounded-chip border border-border px-1.5 py-0.5 text-xs text-muted hover:bg-raised"
            >
              {BEAT_LABELS.cancelMerge}
            </button>
          )}
        </div>
        {mergeSource && (
          <div
            data-testid="beat-pick-hint"
            className="rounded-input bg-raised px-2 py-1 text-xs text-muted"
          >
            为「{mergeSource.name}」{BEAT_LABELS.pickTarget}
          </div>
        )}
        {beatsError && (
          <div role="alert" className="rounded-input bg-danger/15 px-2 py-1 text-xs text-danger">
            {beatsError}
          </div>
        )}
        {beatError && (
          <div role="alert" className="rounded-input bg-danger/15 px-2 py-1 text-xs text-danger">
            {beatError}
          </div>
        )}
        {beatNote && (
          <div
            role="status"
            data-testid="beat-note"
            className="rounded-input bg-ok/10 px-2 py-1 text-xs text-ok"
          >
            {beatNote}
          </div>
        )}
        {beats.length === 0 ? (
          <p className="text-xs text-muted">{BEAT_LABELS.empty}</p>
        ) : (
          <ul className="flex flex-col gap-0.5">
            {beats.map((b) => (
              <li
                key={b.id}
                data-testid="beat-item"
                className="flex items-center gap-1 rounded-input px-1 py-0.5 text-xs"
              >
                <span
                  data-testid="beat-name"
                  title={b.name}
                  className={`min-w-0 flex-1 truncate ${
                    mergeSource?.id === b.id ? 'text-accent' : 'text-primary'
                  }`}
                >
                  {b.story_order}. {b.name}
                </span>
                {mergeSource ? (
                  mergeSource.id === b.id ? (
                    <span className="shrink-0 text-accent">{BEAT_LABELS.sourceBeat}</span>
                  ) : (
                    <button
                      type="button"
                      data-testid={`beat-target-${b.id}`}
                      disabled={beatDisabled}
                      onClick={() =>
                        setBeatOp({ kind: 'merge', source: mergeSource, target: b })}
                      className="shrink-0 rounded-chip border border-border px-1.5 py-0.5 text-muted hover:bg-raised disabled:cursor-not-allowed disabled:opacity-40"
                    >
                      {BEAT_LABELS.mergeInto}
                    </button>
                  )
                ) : (
                  <>
                    <button
                      type="button"
                      data-testid={`beat-merge-${b.id}`}
                      disabled={beatDisabled || beats.length < 2}
                      onClick={() => setMergeSource(b)}
                      title="合并到其他拍"
                      className="shrink-0 rounded-chip border border-border px-1.5 py-0.5 text-muted hover:bg-raised disabled:cursor-not-allowed disabled:opacity-40"
                    >
                      {BEAT_LABELS.merge}
                    </button>
                    <button
                      type="button"
                      data-testid={`beat-delete-${b.id}`}
                      disabled={beatDisabled}
                      onClick={() => setBeatOp({ kind: 'delete', beat: b })}
                      className="shrink-0 rounded-chip border border-danger/40 px-1.5 py-0.5 text-danger hover:bg-danger/10 disabled:cursor-not-allowed disabled:opacity-40"
                    >
                      {BEAT_LABELS.delete}
                    </button>
                  </>
                )}
              </li>
            ))}
          </ul>
        )}
      </aside>

      {/* 拍操作确认（TC-SH-10 / R5，doSeal 危险操作先例）：合并含伏笔迁移预览 */}
      {beatOp && (
        <ConfirmDialog
          title={beatOp.kind === 'merge' ? '合并拍' : '删除拍'}
          consequence={
            beatOp.kind === 'merge'
              ? `将把「${beatOp.source.name}」并入「${beatOp.target.name}」。${foreshadowPreview(beatOp.source.id)}`
              : `将删除拍「${beatOp.beat.name}」。`
          }
          busy={beatBusy}
          onConfirm={() => void runBeatOp(beatOp)}
          onCancel={() => {
            setBeatOp(null)
            setMergeSource(null)
          }}
        />
      )}

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
