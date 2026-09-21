import { defineConfig } from '@playwright/test'
export default defineConfig({
  testDir: './e2e',
  use: { baseURL: process.env.CYBERLAB_E2E_URL || 'http://localhost:8080', headless: true, trace: 'retain-on-failure' },
  timeout: 60000,
  // Intentionally no webServer: this suite runs only against an explicitly prepared deployment.
})
