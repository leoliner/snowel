// 危险操作二次确认对话框（ui-design-01 §5.4）：后果文案 + Esc/取消退出，
// 键盘焦点默认落在"取消"（防误确认）；封卷 / retcon 确认 / 否决共用。
import { useEffect, useRef } from 'react'

interface ConfirmDialogProps {
  title: string
  consequence: string
  confirmLabel?: string
  busy?: boolean
  onConfirm: () => void
  onCancel: () => void
}

export default function ConfirmDialog({
  title, consequence, confirmLabel = '确认', busy = false,
  onConfirm, onCancel,
}: ConfirmDialogProps) {
  const cancelRef = useRef<HTMLButtonElement>(null)

  useEffect(() => {
    // §5.4 / §5.7：Esc 关闭对话框
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onCancel()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onCancel])

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label={title}
      className="fixed inset-0 z-50 flex items-center justify-center bg-base/70"
      onMouseDown={(e) => {
        if (e.target === e.currentTarget) onCancel()
      }}
    >
      <div className="w-80 rounded-panel border border-border bg-panel p-4 shadow-elev2">
        <div className="text-sm font-medium text-danger">{title}</div>
        <p className="mt-2 text-sm leading-relaxed text-primary">{consequence}</p>
        <div className="mt-4 flex justify-end gap-2">
          <button
            ref={cancelRef}
            type="button"
            autoFocus
            onClick={onCancel}
            disabled={busy}
            className="rounded-btn border border-border bg-raised px-3 py-1.5 text-sm text-primary hover:bg-border"
          >
            取消
          </button>
          <button
            type="button"
            onClick={onConfirm}
            disabled={busy}
            className="rounded-btn border border-danger bg-transparent px-3 py-1.5 text-sm text-danger hover:bg-danger/10"
          >
            {busy ? '处理中…' : confirmLabel}
          </button>
        </div>
      </div>
    </div>
  )
}
