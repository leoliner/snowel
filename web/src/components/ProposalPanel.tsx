// 右栏工作区提案面板（ui-design-01 §4/§5）：payload 变更 diff 表 + 级联违规（major/minor
// 分色，L19 全量展开）+ retcon impact + 确认/否决（§5.4 二次确认）/改写 + W7 外部改动警告。
import { useEffect, useState } from 'react'
import { api, useApi } from '../api'
import type {
  CascadePreviewResult, CascadeResult, ConfirmResult, Proposal, ReconcileEntry,
  RewriteResult, Violation,
} from '../types'
import { KIND_LABELS } from './labels'
import ConfirmDialog from './ConfirmDialog'

interface ProposalPanelProps {
  proposalId: string | null
  readonly?: boolean
  // T12 遗留清偿：确认/否决/改写成功后通知父级刷新列表与流程树
  onMutated?: () => void
}

// retcon 提案 payload 内嵌影响清单（consistency/retcon.py propose_retcon）
interface RetconImpact {
  violations?: Violation[]
  affected_proposals?: string[]
}

function fmt(v: unknown): string {
  return typeof v === 'string' ? v : JSON.stringify(v)
}

// 级联违规列表（§5.5 分色渲染，T11 ProseEditor 抽取面板复用）
export function ViolationList({ violations }: { violations: Violation[] }) {
  return (
    <ul className="flex flex-col gap-1">
      {violations.map((v, i) => (
        <li
          key={i}
          className={`flex items-start gap-2 rounded-input border-l-2 px-2 py-1 ${
            v.level === 'major' ? 'border-danger bg-danger/10' : 'border-warn bg-warn/10'
          }`}
        >
          <span
            className={`shrink-0 rounded-chip px-1.5 py-0.5 text-xs ${
              v.level === 'major' ? 'bg-danger/20 text-danger' : 'bg-warn/20 text-warn'
            }`}
          >
            {v.level}
          </span>
          <span className="text-sm leading-relaxed text-primary">{v.message}</span>
        </li>
      ))}
    </ul>
  )
}

function ProposalPanelInner({ proposalId, readonly, onMutated }: {
  proposalId: string
  readonly: boolean
  onMutated?: () => void
}) {
  const { data: detail, loading, error } = useApi<Proposal>(`/api/proposals/${proposalId}`)
  const { data: preview } = useApi<CascadePreviewResult>(
    `/api/proposals/${proposalId}/cascade_preview`)
  const { data: reconcile } = useApi<ReconcileEntry[]>('/api/reconcile')

  const [cascade, setCascade] = useState<CascadeResult | null>(null)
  const [confirmed, setConfirmed] = useState(false)
  const [rejected, setRejected] = useState(false)
  const [busy, setBusy] = useState(false)
  const [actionError, setActionError] = useState<string | null>(null)
  const [dialog, setDialog] = useState<'retcon' | 'reject' | null>(null)
  const [instruction, setInstruction] = useState('')
  const [rewriteNote, setRewriteNote] = useState<string | null>(null)

  // 切换提案时清空上一提案的操作态（确认结果/对话框/改写）
  useEffect(() => {
    setCascade(null)
    setConfirmed(false)
    setRejected(false)
    setBusy(false)
    setActionError(null)
    setDialog(null)
    setInstruction('')
    setRewriteNote(null)
  }, [proposalId])

  if (loading) {
    return (
      <div data-testid="proposal-skeleton" className="flex flex-col gap-2">
        <div className="skeleton h-6" />
        <div className="skeleton h-20" />
        <div className="skeleton h-20" />
      </div>
    )
  }
  if (error || !detail) {
    return (
      <div role="alert" className="rounded-card bg-danger/15 px-3 py-2 text-sm text-danger">
        {error ?? '提案不存在'}
      </div>
    )
  }

  const kind = detail.kind
  const status = detail.status
  const stale = status === 'stale'
  const canAct = (status === 'pending' || stale) && !confirmed && !rejected
  const impact = kind === 'retcon' ? (detail.payload.impact as RetconImpact | undefined) : undefined
  const affected = impact?.affected_proposals ?? []
  // 级联违规：确认响应优先，其次 retcon impact（P5 propose 时全量级联），再次预演
  const violations = cascade?.violations ?? impact?.violations ?? preview?.violations ?? []
  const diffEntries = preview?.diff_preview ?? []
  // W7：prose 提案确认前，reconcile changed 非空 → 外部改动警告
  const reconcileChanged = kind === 'prose' ? (reconcile ?? []) : []
  const confirmLabel =
    reconcileChanged.length > 0 ? '确认并覆盖外部改动' : '确认提案'

  const run = async (fn: () => Promise<unknown>) => {
    setBusy(true)
    setActionError(null)
    try {
      await fn()
    } catch (err) {
      setActionError(err instanceof Error ? err.message : String(err))
    } finally {
      setBusy(false)
    }
  }

  const doConfirm = () => {
    void run(async () => {
      const res = await api.post<ConfirmResult>(`/api/proposals/${proposalId}/confirm`)
      setCascade(res.cascade)
      setConfirmed(true)
      onMutated?.()
    })
  }

  const doConfirmRetcon = () => {
    setDialog(null)
    void run(async () => {
      const res = await api.post<ConfirmResult>(`/api/proposals/${proposalId}/confirm_retcon`)
      setCascade(res.cascade)
      setConfirmed(true)
      onMutated?.()
    })
  }

  const doReject = () => {
    setDialog(null)
    void run(async () => {
      await api.post(`/api/proposals/${proposalId}/reject`)
      setRejected(true)
      onMutated?.()
    })
  }

  const doRewrite = () => {
    void run(async () => {
      const res = await api.post<RewriteResult>(`/api/proposals/${proposalId}/rewrite`, {
        instruction,
      })
      setRewriteNote(`新提案 ${res.proposal_id} 已入队`)
      setInstruction('')
      onMutated?.()
    })
  }

  const writeDisabled = busy || readonly || !canAct

  return (
    <div
      data-testid="proposal-panel"
      className={`flex flex-col gap-3 rounded-card border bg-raised/40 p-3 ${
        stale ? 'border-warn' : 'border-border'
      }`}
    >
      {/* 头行：kind + 状态 chip */}
      <div className="flex items-center gap-2">
        <span className="text-sm font-medium text-primary">{KIND_LABELS[kind] ?? kind}</span>
        <span
          className={`rounded-chip px-1.5 py-0.5 text-xs ${
            confirmed
              ? 'bg-ok/15 text-ok'
              : rejected
                ? 'bg-danger/15 text-danger'
                : stale
                  ? 'border border-warn text-warn'
                  : 'bg-raised text-muted'
          }`}
        >
          {confirmed ? '已确认' : rejected ? '已否决' : status}
        </span>
        {kind === 'retcon' && (
          <span className="ml-auto rounded-chip bg-raised px-1.5 py-0.5 text-xs text-muted">
            冻结线豁免
          </span>
        )}
      </div>

      {stale && detail.stale_hint && (
        <div className="rounded-input border border-warn bg-warn/10 px-2 py-1 text-xs text-warn">
          {detail.stale_hint}
        </div>
      )}

      {/* W7：prose + reconcile changed 非空 → 外部改动警告 + 明确确认文案 */}
      {reconcileChanged.length > 0 && (
        <div
          role="alert"
          className="rounded-input border border-warn bg-warn/10 px-2 py-1 text-xs leading-relaxed text-warn"
        >
          检测到外部改动：
          <span className="font-mono">
            {reconcileChanged.map((r) => r.chapter_id).join('、')}
          </span>
          ——确认将覆盖文件中的改动
        </div>
      )}

      {actionError && (
        <div
          role="alert"
          className="flex items-center justify-between gap-2 rounded-input bg-danger/15 px-2 py-1 text-xs text-danger"
        >
          <span>{actionError}</span>
          <button
            type="button"
            aria-label="关闭错误"
            onClick={() => setActionError(null)}
            className="shrink-0 rounded px-1 text-danger hover:bg-danger/10"
          >
            ×
          </button>
        </div>
      )}

      {/* diff 对照表（§4）：键名 muted / 旧值 danger 删除线 / 新值 ok */}
      {diffEntries.length > 0 && (
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left text-xs text-muted">
              <th className="py-1 pr-2 font-normal">节点 · 键</th>
              <th className="px-2 py-1 font-normal">变更前</th>
              <th className="px-2 py-1 font-normal">变更后</th>
            </tr>
          </thead>
          <tbody>
            {diffEntries.map((d, i) => (
              <tr key={i} className="align-top">
                <td className="py-1 pr-2 font-mono text-xs text-muted">
                  {d.node_id} · {d.key}
                </td>
                <td className="px-2 py-1">
                  <span className="rounded bg-danger/20 px-1 font-mono text-xs line-through">
                    {fmt(d.old)}
                  </span>
                </td>
                <td className="px-2 py-1">
                  <span className="rounded bg-ok/20 px-1 font-mono text-xs">{fmt(d.new)}</span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      {/* 级联违规（§5.5：major danger / minor warn，L19 全量展开） */}
      {violations.length > 0 && (
        <div className="flex flex-col gap-1">
          <div className="text-xs text-muted">
            {cascade ? '确认后级联检查' : kind === 'retcon' ? '影响清单（propose 时全量级联）' : '级联预演'}
          </div>
          <ViolationList violations={violations} />
        </div>
      )}

      {kind === 'retcon' && affected.length > 0 && (
        <div className="rounded-input bg-raised px-2 py-1 text-xs text-warn">
          影响 {affected.length} 个待确认提案
        </div>
      )}

      {cascade?.cascade_proposal_id && (
        <div className="rounded-input bg-raised px-2 py-1 text-xs text-muted">
          已入队级联修订提案：{cascade.cascade_proposal_id}
        </div>
      )}

      {/* 操作行：确认（retcon 走二次确认）/ 否决 */}
      <div className="flex gap-2">
        {kind === 'retcon' ? (
          <button
            type="button"
            disabled={writeDisabled}
            onClick={() => setDialog('retcon')}
            className="rounded-btn border border-danger bg-transparent px-3 py-1.5 text-sm text-danger hover:bg-danger/10 disabled:cursor-not-allowed disabled:opacity-40"
          >
            确认回溯
          </button>
        ) : (
          <button
            type="button"
            disabled={writeDisabled}
            onClick={doConfirm}
            className="rounded-btn bg-accent px-3 py-1.5 text-sm text-base hover:brightness-110 disabled:cursor-not-allowed disabled:opacity-40"
          >
            {busy ? '处理中…' : confirmLabel}
          </button>
        )}
        <button
          type="button"
          disabled={writeDisabled}
          onClick={() => setDialog('reject')}
          className="rounded-btn border border-border bg-raised px-3 py-1.5 text-sm text-primary hover:bg-border disabled:cursor-not-allowed disabled:opacity-40"
        >
          否决
        </button>
      </div>

      {/* 改写框（instruction 一等输入，D7） */}
      <div className="flex flex-col gap-1">
        <label htmlFor="rewrite-instruction" className="text-xs text-muted">
          改写指令
        </label>
        <textarea
          id="rewrite-instruction"
          value={instruction}
          disabled={writeDisabled}
          onChange={(e) => setInstruction(e.target.value)}
          placeholder="例如：把主角改成一只猫，并调整相关设定…"
          className="min-h-16 resize-y rounded-input border border-border bg-raised px-2 py-1 text-sm text-primary placeholder:text-muted focus:border-accent"
        />
        <div className="flex items-center gap-2">
          <button
            type="button"
            disabled={writeDisabled || instruction.trim() === ''}
            onClick={doRewrite}
            className="rounded-btn border border-border bg-raised px-3 py-1 text-xs text-primary hover:bg-border disabled:cursor-not-allowed disabled:opacity-40"
          >
            {busy ? '处理中…' : '提交改写'}
          </button>
          {rewriteNote && (
            <span className="text-xs text-ok" role="status">
              {rewriteNote}
            </span>
          )}
        </div>
      </div>

      {/* §5.4 危险操作二次确认（retcon 确认 / 否决） */}
      {dialog === 'retcon' && (
        <ConfirmDialog
          title="确认回溯（retcon）"
          consequence={
            affected.length > 0
              ? `将应用此回溯变更，影响 ${affected.length} 个待确认提案（标记为 stale）。`
              : '将应用此回溯变更，需确认其影响范围。'
          }
          busy={busy}
          onConfirm={doConfirmRetcon}
          onCancel={() => setDialog(null)}
        />
      )}
      {dialog === 'reject' && (
        <ConfirmDialog
          title="否决提案"
          consequence="提案将被否决并从待确认队列移除，此操作不可恢复。"
          busy={busy}
          onConfirm={doReject}
          onCancel={() => setDialog(null)}
        />
      )}
    </div>
  )
}

export default function ProposalPanel({ proposalId, readonly = false, onMutated }: ProposalPanelProps) {
  if (!proposalId) {
    return (
      // 空态同挂 proposal-panel testid：tour 第 4 步高亮目标在未选中提案时也存在
      <div
        data-testid="proposal-panel"
        className="rounded-card border border-border bg-raised/40 px-3 py-4 text-center text-sm text-muted"
      >
        在列表中选择提案查看详情
      </div>
    )
  }
  return <ProposalPanelInner proposalId={proposalId} readonly={readonly} onMutated={onMutated} />
}
