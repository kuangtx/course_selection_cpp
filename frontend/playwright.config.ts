import { defineConfig, devices } from '@playwright/test';
import path from 'node:path';

export default defineConfig({
  testDir: './tests',
  testMatch: 'selection.spec.ts',
  fullyParallel: false,
  workers: 1,
  timeout: 90000,
  expect: { timeout: 20000 },
  reporter: [['list']],
  use: { baseURL: 'http://127.0.0.1:5185', trace: 'retain-on-failure', screenshot: 'only-on-failure' },
  projects: [
    {
      name: 'chromium',
      use: {
        ...devices['Desktop Chrome'],
        channel: process.env.PLAYWRIGHT_CHANNEL || undefined,
        launchOptions: { executablePath: process.env.PLAYWRIGHT_EXECUTABLE_PATH || undefined },
      },
    },
  ],
  webServer: [
    {
      command: 'python -m uvicorn backend.api.main:app --host 127.0.0.1 --port 8016',
      cwd: process.env.TEST_BACKEND_DIR || path.resolve('..'),
      url: 'http://127.0.0.1:8016/api/catalog',
      reuseExistingServer: false,
      timeout: 30000,
    },
    {
      command: 'npm run dev -- --port 5185',
      env: { API_PROXY_TARGET: 'http://127.0.0.1:8016' },
      url: 'http://127.0.0.1:5185',
      reuseExistingServer: false,
      timeout: 30000,
    },
  ],
});
