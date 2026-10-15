import { defineConfig } from '@playwright/test'

// End-to-end tests against the real backend serving the built frontend (`npm run build` first).
const PORT = Number(process.env.E2E_PORT ?? 8124)
const DB = `${process.env.TMPDIR ?? '/tmp'}/cnc-e2e-${process.pid}.json`

export default defineConfig({
  testDir: './e2e',
  fullyParallel: false,
  workers: 1,
  reporter: [['list']],
  use: {
    baseURL: `http://127.0.0.1:${PORT}`,
    browserName: 'chromium',
    viewport: { width: 1280, height: 900 },
  },
  webServer: {
    command: `rm -f ${DB} && cd ../backend && TINYDB_PATH=${DB} STATIC_DIR=../frontend/dist PORT=${PORT} uv run python -m app`,
    url: `http://127.0.0.1:${PORT}/readyz`,
    reuseExistingServer: false,
    timeout: 60_000,
  },
})
