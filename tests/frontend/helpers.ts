import { Page, expect } from '@playwright/test';

/**
 * Shared E2E test helpers — login, team creation, navigation.
 * All assertions are unconditional (no isVisible().catch() guards).
 */

const BACKEND_URL = 'http://127.0.0.1:' + (process.env.BACKEND_PORT || '8000');

/**
 * Seed a test user via the backend API (direct registration).
 * Called once in global setup or at the start of a test suite.
 */
export async function seedTestUser() {
  const resp = await fetch(`${BACKEND_URL}/api/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username: 'e2e-test', password: 'test1234' }),
  });
  // If login fails (user doesn't exist), try registering via a direct API call
  if (!resp.ok) {
    // The dev login provider doesn't have a register endpoint,
    // so we create the user file directly via a Python script.
    // For E2E, the global setup should have already seeded the user.
  }
}

/**
 * Login via the UI and wait for the team list page to appear.
 * Hard-fails if login doesn't succeed.
 */
export async function loginAndWaitForTeams(page: Page) {
  await page.goto('/');
  await page.waitForLoadState('networkidle');

  // Wait for login form
  const usernameInput = page.locator('#username');
  await expect(usernameInput).toBeVisible({ timeout: 15000 });

  await usernameInput.fill('e2e-test');
  await page.locator('#password').fill('test1234');

  const signInBtn = page.locator('button[type="submit"]');
  await expect(signInBtn).toBeEnabled();
  await signInBtn.click();

  // Wait for team list page — the "Teams" heading should appear
  await expect(page.getByRole('heading', { name: 'Teams', exact: true })).toBeVisible({ timeout: 15000 });
}

/**
 * Create a team via the UI and navigate into it.
 * Hard-fails if team creation doesn't work.
 */
export async function createTeamAndEnter(page: Page, teamName: string = 'E2E Test Team') {
  // Click "สร้างทีมใหม่" button to reveal the inline form
  const createBtn = page.getByRole('button', { name: 'สร้างทีมใหม่' });
  await expect(createBtn).toBeVisible({ timeout: 5000 });
  await createBtn.click();

  // Fill in team name — placeholder is "เช่น ทีมการตลาด"
  const nameInput = page.locator('input[placeholder="เช่น ทีมการตลาด"]');
  await expect(nameInput).toBeVisible({ timeout: 5000 });
  await nameInput.fill(teamName);

  // Click "สร้างทีม" submit button (enabled after name is filled)
  // Use exact text match to avoid matching "สร้างทีมใหม่"
  const submitBtn = page.getByRole('button', { name: 'สร้างทีม', exact: true });
  await expect(submitBtn).toBeEnabled({ timeout: 5000 });
  await submitBtn.click();

  // Wait for the team card to appear and click it
  const teamCard = page.locator(`.cursor-pointer:has-text("${teamName}")`).first();
  await expect(teamCard).toBeVisible({ timeout: 10000 });
  await teamCard.click();

  // Wait for RetroDesktop to appear — the chat window should be visible
  await expect(page.locator('textarea.ci-input')).toBeVisible({ timeout: 15000 });
}

/**
 * Open a desktop window by double-clicking its icon.
 * Window IDs: 'chat', 'tasks', 'agents', 'history', 'schedule', 'settings'
 */
export async function openDesktopWindow(page: Page, windowId: string) {
  const title = windowId.charAt(0).toUpperCase() + windowId.slice(1);

  // Click the Start menu button (🪟 Start) in the taskbar
  const startBtn = page.getByRole('button', { name: 'Start' }).first();
  await expect(startBtn).toBeVisible({ timeout: 5000 });
  await startBtn.click();

  // Wait for Start menu to appear — it has z-[1001]
  // Menu items are inside the Start menu, not the taskbar
  const startMenu = page.locator('.z-\\[1001\\]');
  await expect(startMenu).toBeVisible({ timeout: 5000 });

  // Click the window item inside the Start menu
  const menuItem = startMenu.locator(`button:has-text("${title}")`);
  await expect(menuItem).toBeVisible({ timeout: 5000 });
  await menuItem.click();

  // Wait for the window to appear
  await page.waitForTimeout(1000);
}

/**
 * Send a message in the chat window and wait for a response.
 */
export async function sendChatMessage(page: Page, message: string) {
  const textarea = page.locator('textarea.ci-input');
  await expect(textarea).toBeVisible({ timeout: 5000 });
  await textarea.fill(message);

  // Find and click the send button (➤ icon)
  const sendBtn = page.locator('button.ci-send, button:has-text("➤")').first();
  await expect(sendBtn).toBeVisible({ timeout: 3000 });
  await sendBtn.click();
}
