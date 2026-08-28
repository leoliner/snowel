// 手册弹窗（TC-SH-13 / R3）：居中大窗 = 左目录树 + 右内容区；顶部关键词过滤
// （纯客户端 includes：标题+正文，目录与内容同步只留命中章，清空即复原）；
// esc / 遮罩点击关闭、焦点落过滤框（照 ConfirmDialog 先例）。
// 章节清单 = 构建期 glob 收集 manual/*.md raw 源，标题从源文首行 `## ` 解析——
// 新增章 = 增一个 md 文件目录自动跟进，无需另维护元数据数组。
import { useEffect, useRef, useState } from 'react'
import Markdown from './Markdown'
import { MANUAL_LABELS } from './labels'

interface ManualModalProps {
  open: boolean
  onClose: () => void
}

interface ManualChapter {
  slug: string
  title: string
  content: string
}

// vite 构建期把 md 以字符串打进 bundle（query '?raw'），vitest 走同一管线
const sources = import.meta.glob('../manual/*.md', {
  query: '?raw',
  import: 'default',
  eager: true,
})

// NN-slug.md 双位序号保证字典序即章序
const CHAPTERS: ManualChapter[] = Object.entries(sources)
  .sort(([a], [b]) => a.localeCompare(b))
  .map(([path, content]) => {
    const slug = (path.split('/').pop() ?? path).replace(/\.md$/, '')
    return { slug, title: content.match(/^##\s+(.+)$/m)?.[1]?.trim() ?? slug, content }
  })

export default function ManualModal({ open, onClose }: ManualModalProps) {
  const [query, setQuery] = useState('')
  const [activeSlug, setActiveSlug] = useState<string | null>(null)
  const contentRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!open) return
    // §5.4 / ConfirmDialog 先例：Esc 关闭
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [open, onClose])

  if (!open) return null

  // 过滤形态：目录与内容同步"仅渲染命中章"（感知变化最直接，清空即全量复原）
  const keyword = query.trim()
  const visible = keyword
    ? CHAPTERS.filter((ch) => ch.title.includes(keyword) || ch.content.includes(keyword))
    : CHAPTERS
  const active = visible.some((ch) => ch.slug === activeSlug)
    ? activeSlug
    : (visible[0]?.slug ?? null)

  const scrollToChapter = (slug: string) => {
    setActiveSlug(slug)
    const target = contentRef.current?.querySelector(`[data-testid="manual-chapter-${slug}"]`)
    // jsdom 不实现 scrollIntoView（测试以桩验证调用），真浏览器里负责滚动定位
    target?.scrollIntoView?.({ block: 'start' })
  }

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label={MANUAL_LABELS.openBtn}
      data-testid="manual-modal"
      className="fixed inset-0 z-50 flex items-center justify-center bg-base/70"
      onMouseDown={(e) => {
        if (e.target === e.currentTarget) onClose()
      }}
    >
      <div className="flex h-[80vh] w-full max-w-4xl flex-col overflow-hidden rounded-panel border border-border bg-panel shadow-elev2">
        {/* 顶部：关键词过滤 + 关闭 */}
        <div className="flex shrink-0 items-center gap-2 border-b border-border px-3 py-2">
          <input
            data-testid="manual-filter"
            aria-label={MANUAL_LABELS.filter}
            placeholder={MANUAL_LABELS.filterPlaceholder}
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            autoFocus
            className="h-7 flex-1 rounded-input border border-border bg-raised px-2 text-sm text-primary placeholder:text-muted focus:border-accent focus:outline-none"
          />
          <button
            data-testid="manual-close"
            type="button"
            aria-label={MANUAL_LABELS.close}
            onClick={onClose}
            className="rounded-btn border border-border bg-raised px-2 py-0.5 text-sm text-primary hover:bg-border"
          >
            ×
          </button>
        </div>

        <div className="flex min-h-0 flex-1">
          {/* 左：目录树（章节锚点，点击定位右侧内容） */}
          <nav
            data-testid="manual-toc"
            aria-label={MANUAL_LABELS.toc}
            className="w-44 shrink-0 overflow-y-auto border-r border-border p-2"
          >
            {visible.map((ch) => (
              <button
                key={ch.slug}
                type="button"
                data-testid={`manual-toc-${ch.slug}`}
                aria-current={ch.slug === active ? 'true' : undefined}
                onClick={() => scrollToChapter(ch.slug)}
                className={`block w-full truncate rounded-btn px-2 py-1 text-left text-sm ${
                  ch.slug === active ? 'bg-raised text-accent' : 'text-primary hover:bg-raised'
                }`}
              >
                {ch.title}
              </button>
            ))}
            {visible.length === 0 && (
              <p data-testid="manual-empty" className="px-2 py-1 text-sm text-muted">
                {MANUAL_LABELS.empty}
              </p>
            )}
          </nav>

          {/* 右：内容区（仅渲染命中章） */}
          <div
            ref={contentRef}
            data-testid="manual-content"
            className="min-w-0 flex-1 overflow-y-auto px-6 py-2"
          >
            {visible.map((ch) => (
              <section key={ch.slug} data-testid={`manual-chapter-${ch.slug}`}>
                <Markdown>{ch.content}</Markdown>
              </section>
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}
