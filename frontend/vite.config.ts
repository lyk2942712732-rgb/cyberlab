import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  plugins: [vue()],
  server: { proxy: { '/api': { target: process.env.API_PROXY_TARGET || 'http://localhost:8000', ws: true } } },
  // noVNC uses top-level await for optional WebCodecs support. Keep that
  // syntax in the browser bundle instead of transpiling it to older targets.
  build: { target: 'esnext', chunkSizeWarningLimit: 1100 },
})
