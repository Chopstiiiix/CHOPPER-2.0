const { defineConfig, devices } = require('@playwright/test');

const flaskUrl = process.env.FLASK_URL || 'http://localhost:8000';
const agentUrl = process.env.AGENT_URL || 'http://localhost:3100';

module.exports = defineConfig({
  testDir: './tests/e2e',
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: process.env.CI ? 1 : undefined,
  reporter: [
    ['html', { outputFolder: 'tests/e2e/report' }],
    ['list'],
  ],
  timeout: 30000,
  expect: { timeout: 5000 },

  use: {
    trace: 'on-first-retry',
    screenshot: 'only-on-failure',
    video: 'retain-on-failure',
  },

  projects: [
    {
      name: 'flask-ui',
      use: {
        ...devices['Desktop Chrome'],
        baseURL: flaskUrl,
      },
      testMatch: /flask.*\.spec\.js/,
    },
    {
      name: 'agent-api',
      use: {
        baseURL: agentUrl,
      },
      testMatch: /agent.*\.spec\.js/,
    },
    {
      name: 'api-only',
      use: {
        baseURL: flaskUrl,
      },
      testMatch: /(api|telegram).*.spec\.js/,
    },
  ],

  // Start Flask app; agent tests gracefully skip when agent is not running.
  webServer: {
    command: 'python3 app.py',
    url: flaskUrl,
    timeout: 30000,
    reuseExistingServer: !process.env.CI,
  },
});
