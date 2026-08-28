// 手册 Markdown 渲染器（TC-SH-13 / R1）：react-markdown 组件化渲染——产出 React 元素树，
// 不自造 HTML、无 dangerouslySetInnerHTML；prose 语义样式（Tailwind token）统一在此单处映射。
import ReactMarkdown, { type Components } from 'react-markdown'
import remarkGfm from 'remark-gfm'

// components 回调收到的 props 含 react-markdown 私有的 node 字段，禁止透传到 DOM
function stripNode<T extends { node?: unknown }>(props: T): Omit<T, 'node'> {
  const { node: _node, ...rest } = props
  return rest
}

const components: Components = {
  h2: (props) => (
    <h2
      {...stripNode(props)}
      className="mb-3 mt-2 border-b border-border pb-1.5 text-lg font-medium text-primary"
    />
  ),
  h3: (props) => (
    <h3 {...stripNode(props)} className="mb-2 mt-5 text-base font-medium text-primary" />
  ),
  p: (props) => (
    <p {...stripNode(props)} className="my-3 text-sm leading-relaxed text-prose" />
  ),
  ul: (props) => (
    <ul {...stripNode(props)} className="my-3 list-disc pl-6 marker:text-muted" />
  ),
  ol: (props) => (
    <ol {...stripNode(props)} className="my-3 list-decimal pl-6 marker:text-muted" />
  ),
  li: (props) => (
    <li {...stripNode(props)} className="my-1 text-sm leading-relaxed text-prose" />
  ),
  // 围栏代码块的文本值以换行结尾、行内代码不含换行（仓库 12 章源文均为单行行内码）——
  // 借此前缀区分块级/行内样式；块级容器底色由 pre 承担
  code: (props) => {
    const { children } = stripNode(props)
    if (typeof children === 'string' && children.includes('\n')) {
      return (
        <code
          {...stripNode(props)}
          className="block font-mono text-xs leading-relaxed text-primary"
        >
          {children}
        </code>
      )
    }
    return (
      <code
        {...stripNode(props)}
        className="rounded-btn bg-raised px-1 py-0.5 font-mono text-[0.8em] text-accent"
      >
        {children}
      </code>
    )
  },
  pre: (props) => (
    <pre
      {...stripNode(props)}
      className="my-3 overflow-x-auto rounded-card bg-raised p-3"
    />
  ),
  table: (props) => (
    <table {...stripNode(props)} className="my-3 w-full border-collapse text-sm" />
  ),
  th: (props) => (
    <th
      {...stripNode(props)}
      className="border border-border bg-raised px-2 py-1 text-left font-medium text-primary"
    />
  ),
  td: (props) => (
    <td {...stripNode(props)} className="border border-border px-2 py-1 align-top text-prose" />
  ),
  strong: (props) => (
    <strong {...stripNode(props)} className="font-semibold text-primary" />
  ),
  blockquote: (props) => (
    <blockquote
      {...stripNode(props)}
      className="my-3 border-l-2 border-border pl-3 text-sm leading-relaxed text-muted"
    />
  ),
}

export default function Markdown({ children }: { children: string }) {
  return (
    <ReactMarkdown remarkPlugins={[remarkGfm]} components={components}>
      {children}
    </ReactMarkdown>
  )
}
