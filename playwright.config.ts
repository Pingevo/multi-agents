import { defineConfig } from '@playwright/test';
import { writeFileSync, readFileSync, existsSync, mkdirSync } from 'fs';
import { join } from 'path';
import { createHash } from 'crypto';

const e2eDataDir = process.env.E2E_DATA_DIR || '/tmp/agent-e2e-data';
const fakeLlmPort = process.env.FAKE_LLM_PORT || '11435';
const backendPort = process.env.BACKEND_PORT || '8000';
const frontendPort = process.env.FRONTEND_PORT || '5173';

// Seed test user BEFORE webServer starts (Playwright starts webServer before globalSetup)
mkdirSync(e2eDataDir, { recursive: true });
const usersPath = join(e2eDataDir, 'users.json');
const salt = 'my_agent_app_2026';
const pwHash = createHash('sha256').update(`${salt}:test1234`).digest('hex');
let users: any[] = [];
if (existsSync(usersPath)) {
  try { users = JSON.parse(readFileSync(usersPath, 'utf-8')); } catch { users = []; }
}
if (!users.some((u) => u.user_id === 'dev_e2e-test')) {
  users.push({
    user_id: 'dev_e2e-test',
    username: 'e2e-test',
    email: '',
    provider: 'dev',
    avatar_url: '',
    password_hash: pwHash,
    created_at: '2026-01-01T00:00:00',
    last_login: '2026-01-01T00:00:00',
  });
  writeFileSync(usersPath, JSON.stringify(users, null, 2), 'utf-8');
}

export default defineConfig({
  testDir: './tests/frontend',
  timeout: 60000,
  retries: 1,
  globalSetup: './tests/global-setup.ts',
  use: {
    baseURL: `http://localhost:${frontendPort}`,
    headless: true,
    screenshot: 'only-on-failure',
    trace: 'on-first-retry',
  },
  webServer: [
    {
      command: `${process.env.PYTHON_PATH || 'venv/bin/python'} tests/fake_llm_server.py --port ${fakeLlmPort}`,
      port: Number(fakeLlmPort),
      timeout: 10000,
      reuseExistingServer: true,
    },
    {
      command: `${process.env.CHAINLIT_PATH || 'venv/bin/chainlit'} run app.py --port ${backendPort} --host 0.0.0.0`,
      port: Number(backendPort),
      timeout: 30000,
      reuseExistingServer: true,
      env: {
        LLM_PROVIDER: 'openrouter',
        LLM_API_KEY: 'test-key-fake',
        LLM_BASE_URL: `http://127.0.0.1:${fakeLlmPort}`,
        LOCAL_LLM_FALLBACK: 'false',
        USE_DEV_LOGIN: 'true',
        AGENT_APP_DATA_DIR: e2eDataDir,
      },
    },
    {
      command: `cd frontend && npm run dev -- --port ${frontendPort}`,
      port: Number(frontendPort),
      timeout: 30000,
      reuseExistingServer: true,
    },
  ],
});
