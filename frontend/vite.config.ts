/// <reference types="vitest/config" />
import vue from '@vitejs/plugin-vue'
import { defineConfig } from 'vite'
import vuetify from 'vite-plugin-vuetify'

// During development, API and health requests are proxied to the FastAPI backend.
const backend = 'http://127.0.0.1:8000'

export default defineConfig({
  plugins: [vue(), vuetify({ autoImport: true })],
  server: {
    proxy: {
      '/api': backend,
      '/healthz': backend,
      '/readyz': backend,
      '/docs': backend,
      '/openapi.json': backend,
    },
  },
  build: {
    chunkSizeWarningLimit: 1500,
  },
  test: {
    environment: 'jsdom',
    include: ['src/**/*.test.ts'],
    setupFiles: ['./src/test/setup.ts'],
    server: { deps: { inline: ['vuetify'] } },
  },
})
