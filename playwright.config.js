const { defineConfig } = require('@playwright/test');
const { existsSync } = require('node:fs');
const chrome = process.env.NOMARK_TEST_CHROMIUM || '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';
const python = process.env.NOMARK_TEST_PYTHON || '.venv/bin/python';

module.exports = defineConfig({
  testDir: 'tests/e2e',
  timeout: 30000,
  workers: 1,
  use: { baseURL: 'http://127.0.0.1:8000', locale: 'en-US', launchOptions: existsSync(chrome) ? { executablePath: chrome } : {}, screenshot: 'only-on-failure' },
  webServer: { command: `${python} -m uvicorn nomark.app:app --port 8000 --no-access-log --no-proxy-headers`, url: 'http://127.0.0.1:8000/health', reuseExistingServer: !process.env.CI },
});
