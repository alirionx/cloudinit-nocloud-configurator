import vue from '@vitejs/plugin-vue'
import { defineConfig } from 'vite'

// During development, API and health requests are proxied to the FastAPI backend.
const backend = 'http://127.0.0.1:8000'

export default defineConfig({
  plugins: [vue()],
  server: {
    proxy: {
      '/api': backend,
      '/healthz': backend,
      '/readyz': backend,
    },
  },
})
