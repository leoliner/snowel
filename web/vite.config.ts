import react from '@vitejs/plugin-react'
import { defineConfig } from 'vitest/config'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    // dev 代理：/api → 本地后端（snowel web，127.0.0.1:8642）
    proxy: {
      '/api': 'http://127.0.0.1:8642',
    },
  },
  build: {
    // 产物 web/dist，由后端 FastAPI 静态 serve（SPA fallback）
    outDir: 'dist',
  },
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: ['./src/test/setup.ts'],
    css: false,
  },
})
