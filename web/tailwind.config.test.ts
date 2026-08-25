import { describe, expect, it } from 'vitest'
import config from './tailwind.config.ts'

// 防漂移锚（ui-design-01 §7 第一行）：tokens 演进先改设计文档，再改 config，
// 此测试断言关键语义 token 值存在，防止组件换肤路径意外丢失
describe('tailwind 语义 tokens（ui-design-01 §2）', () => {
  it('色板 §2.1：11 个语义色值逐一对应（类名 = bg|text|border-{key}）', () => {
    expect(config.theme?.extend?.colors).toMatchObject({
      base: '#16181D', // bg-base 页面底色
      panel: '#1E2128', // bg-panel 三栏面板、顶栏
      raised: '#262A33', // bg-raised 卡片、输入框、hover
      border: '#333845', // border-border 细边框、分隔线
      primary: '#D6D9DE', // text-primary 界面主文字
      prose: '#E8E4DC', // text-prose 正文编辑区暖白
      muted: '#8B909C', // text-muted 次要文字、占位符
      accent: '#E2A03F',
      danger: '#E05252',
      ok: '#5BB98B',
      warn: '#E5B93F',
    })
  })

  it('字体 §2.2：ui/prose/mono 三档家族', () => {
    const fontFamily = config.theme?.extend?.fontFamily
    const family = (name: 'ui' | 'prose' | 'mono') => {
      const v = fontFamily?.[name]
      return Array.isArray(v) ? v.join(',') : String(v)
    }
    expect(family('ui')).toContain('system-ui')
    expect(family('ui')).toContain('Microsoft YaHei')
    expect(family('prose')).toContain('Georgia')
    expect(family('prose')).toContain('Noto Serif SC')
    expect(family('mono')).toContain('ui-monospace')
    expect(family('mono')).toContain('Consolas')
  })

  it('圆角 §2.3：panel 10px / card·input 8px / btn·chip 6px', () => {
    expect(config.theme?.extend?.borderRadius).toMatchObject({
      panel: '10px',
      card: '8px',
      input: '8px',
      btn: '6px',
      chip: '6px',
    })
  })

  it('阴影 §6：面板 elevation 两档', () => {
    const shadow = config.theme?.extend?.boxShadow
    expect(shadow).toHaveProperty('elev1')
    expect(shadow).toHaveProperty('elev2')
  })
})
