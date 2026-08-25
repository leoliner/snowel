import type { Config } from 'tailwindcss'

// ui-design-01 §2 语义 tokens 唯一映射源（§6）：改风格先改设计文档，再改本文件，
// 组件内一律使用语义类名、禁止裸十六进制色值
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      // §2.1 色板（key 即语义名：类名 = bg|text|border-{key}，如 bg-base / text-primary / border-border）
      colors: {
        base: '#16181D', // → bg-base 页面底色
        panel: '#1E2128', // → bg-panel 三栏面板、顶栏
        raised: '#262A33', // → bg-raised 卡片、输入框、代码块、hover
        border: '#333845', // → border-border 细边框、分隔线
        primary: '#D6D9DE', // → text-primary 界面主文字
        prose: '#E8E4DC', // → text-prose 正文编辑区暖白
        muted: '#8B909C', // → text-muted 次要文字、占位符
        accent: '#E2A03F', // → accent 强调：主按钮、选中态、current_layer
        danger: '#E05252', // → danger 冲突、否决、危险操作
        ok: '#5BB98B', // → ok 确认成功、done 层
        warn: '#E5B93F', // → warn stale 提案、只读横幅、外部改动
      },
      // §2.2 字体
      fontFamily: {
        ui: ['system-ui', '"Segoe UI"', '"Microsoft YaHei"', '"PingFang SC"', 'sans-serif'],
        prose: ['Georgia', '"Noto Serif SC"', '"Songti SC"', 'serif'],
        mono: ['ui-monospace', 'Consolas', 'monospace'],
      },
      // §2.3 圆角：面板 10px / 卡片·输入 8px / 按钮·chip 6px
      borderRadius: {
        panel: '10px',
        card: '8px',
        input: '8px',
        btn: '6px',
        chip: '6px',
      },
      // §6 面板 elevation 两档
      boxShadow: {
        elev1: '0 1px 3px rgba(0, 0, 0, 0.4)',
        elev2: '0 4px 12px rgba(0, 0, 0, 0.5)',
      },
      // §2.3 骨架屏 shimmer 1.2s 循环（配合 index.css .skeleton 渐变底）
      keyframes: {
        shimmer: {
          '0%': { backgroundPosition: '200% 0' },
          '100%': { backgroundPosition: '-200% 0' },
        },
      },
      animation: {
        shimmer: 'shimmer 1.2s linear infinite',
      },
    },
  },
  plugins: [],
} satisfies Config
