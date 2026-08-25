// 只读横幅（ui-design-01 §3）：readonly=true 时顶栏下常驻 warn 黄条，
// 文案直显后端 holder（C10 单写者独占）
interface SessionBannerProps {
  readonly: boolean
  holder: string | null
}

export default function SessionBanner({ readonly, holder }: SessionBannerProps) {
  if (!readonly) return null
  return (
    <div
      data-testid="session-banner"
      role="alert"
      className="shrink-0 border-b border-border bg-warn/15 px-4 py-1.5 text-sm text-warn"
    >
      只读模式：写租约由 {holder} 持有
    </div>
  )
}
