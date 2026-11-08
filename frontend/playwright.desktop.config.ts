import { defineConfig } from '@playwright/test';

export default defineConfig({
  testDir: './tests',
  testMatch: 'navigation.spec.ts',
  workers: 1,
  timeout: 30000,
  reporter: 'list',
  use: {
    viewport: { width: 1440, height: 1000 },
    channel: process.env.PLAYWRIGHT_CHANNEL || undefined,
    launchOptions: { executablePath: process.env.PLAYWRIGHT_EXECUTABLE_PATH || undefined },
    screenshot: 'only-on-failure',
  },
});
