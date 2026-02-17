// @ts-check
const { defineConfig, devices } = require('@playwright/test');

/**
 * Playwright Configuration for HR Intelligence Platform
 *
 * Prerequisites: Start the server first with `python run.py`
 *
 * Run all tests:     npx playwright test
 * Run specific file: npx playwright test tests/01-login.spec.js
 * Run with UI:       npx playwright test --ui
 * Debug mode:        npx playwright test --debug
 * HTML report:       npx playwright show-report
 */
module.exports = defineConfig({
  testDir: './tests/playwright',
  fullyParallel: false,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: 1,
  reporter: [
    ['html', { outputFolder: '/sessions/elegant-sharp-bohr/playwright-report', open: 'never' }],
    ['list'],
  ],

  outputDir: '/sessions/elegant-sharp-bohr/pw-test-results',

  use: {
    baseURL: 'http://localhost:5050',
    trace: 'on-first-retry',
    screenshot: 'only-on-failure',
    video: 'retain-on-failure',
    headless: true,
    actionTimeout: 10000,
    navigationTimeout: 15000,
    launchOptions: {
      args: ['--no-sandbox', '--disable-setuid-sandbox', '--disable-dev-shm-usage'],
    },
  },

  timeout: 30000,

  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
  ],
});
