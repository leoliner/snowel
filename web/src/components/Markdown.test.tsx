// Markdown 渲染器子集逐项测试（TC-SH-13 / R1）：react-markdown + remark-gfm 映射后的元素产出
import { describe, expect, it } from 'vitest'
import { render, screen } from '@testing-library/react'
import Markdown from './Markdown'

describe('Markdown 渲染器子集（TC-SH-13 / R1）', () => {
  it('h2 / h3 标题层级', () => {
    render(<Markdown>{'## 章节标题\n\n### 小节标题'}</Markdown>)
    expect(screen.getByRole('heading', { level: 2, name: '章节标题' })).toBeInTheDocument()
    expect(screen.getByRole('heading', { level: 3, name: '小节标题' })).toBeInTheDocument()
  })

  it('无序列表渲染 ul + li', () => {
    const { container } = render(<Markdown>{'- 甲\n- 乙'}</Markdown>)
    expect(container.querySelector('ul')).not.toBeNull()
    expect(container.querySelectorAll('li')).toHaveLength(2)
  })

  it('有序列表渲染 ol + li', () => {
    const { container } = render(<Markdown>{'1. 甲\n2. 乙'}</Markdown>)
    expect(container.querySelector('ol')).not.toBeNull()
    expect(container.querySelectorAll('li')).toHaveLength(2)
  })

  it('围栏代码块渲染 pre > code（块级）', () => {
    const { container } = render(<Markdown>{'```bash\nsnowel init\nsnowel web\n```'}</Markdown>)
    const code = container.querySelector('pre > code')
    expect(code).not.toBeNull()
    expect(code).toHaveTextContent('snowel init')
  })

  it('行内代码渲染 code 且不在 pre 内', () => {
    const { container } = render(<Markdown>{'运行 `snowel init` 初始化'}</Markdown>)
    const code = container.querySelector('code')
    expect(code).not.toBeNull()
    expect(container.querySelector('pre')).toBeNull()
    expect(code).toHaveTextContent('snowel init')
  })

  it('粗体渲染 strong', () => {
    render(<Markdown>{'**写租约**是总闸'}</Markdown>)
    expect(screen.getByText('写租约').tagName).toBe('STRONG')
  })

  it('GFM 表格渲染 table / th / td', () => {
    const md = ['| 入口 | 方式 |', '|---|---|', '| Web | snowel web |'].join('\n')
    render(<Markdown>{md}</Markdown>)
    expect(screen.getByRole('table')).toBeInTheDocument()
    expect(screen.getByRole('columnheader', { name: '入口' })).toBeInTheDocument()
    expect(screen.getByRole('cell', { name: 'Web' })).toBeInTheDocument()
  })

  it('blockquote 渲染引用块', () => {
    const { container } = render(<Markdown>{'> 改可以，但要让全书知道'}</Markdown>)
    expect(container.querySelector('blockquote')).not.toBeNull()
  })

  it('普通段落渲染 p', () => {
    const { container } = render(<Markdown>{'Snowel 是 AI 小说创作辅助工具。'}</Markdown>)
    expect(container.querySelector('p')).toHaveTextContent('Snowel 是 AI 小说创作辅助工具。')
  })
})
