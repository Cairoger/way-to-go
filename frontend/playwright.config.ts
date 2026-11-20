import { defineConfig } from '@playwright/test';
export default defineConfig({
  testDir: './tests',
  testMatch: '**/*.spec.ts',
  timeout: 35000,
  workers: 1,
  use: {
    baseURL: process.env.E2E_ORIGIN || 'http://localhost:3000',
    locale: 'zh-TW',
    trace: 'retain-on-failure',
    launchOptions: process.env.CHROME_EXECUTABLE
      ? { executablePath: process.env.CHROME_EXECUTABLE }
      : {},
  },
});
