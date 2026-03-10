import { defineConfig } from 'vitest/config'
import vue from '@vitejs/plugin-vue'

// https://vite.dev/config/
export default defineConfig({
  plugins: [vue() as any],
  test: {
    environment: 'jsdom',
    globals: true,
  },
})
