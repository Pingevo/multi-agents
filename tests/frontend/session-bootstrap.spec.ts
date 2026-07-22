import { test, expect } from '@playwright/test';
import { loginAndWaitForTeams, createTeamAndEnter } from './helpers';

/**
 * Golden Flow 1: Session Bootstrap
 * Load app → login → team select → chat window ready.
 * Catches session-wiring regressions like missing task_store in on_chat_start.
 */
test.describe('Session Bootstrap', () => {
  test('user can login, create a team, and see the chat window', async ({ page }) => {
    await loginAndWaitForTeams(page);

    // We should be on the team list page
    await expect(page.getByRole('heading', { name: 'Teams', exact: true })).toBeVisible();

    // Create a team and enter it
    await createTeamAndEnter(page, 'Bootstrap Test Team');

    // The chat window textarea should be visible and interactive
    const textarea = page.locator('textarea.ci-input');
    await expect(textarea).toBeVisible();
    await expect(textarea).toBeEnabled();

    // The Plan mode button should be visible
    await expect(page.locator('button:has-text("Plan")')).toBeVisible();
  });

  test('socket connection is established after login', async ({ page }) => {
    await loginAndWaitForTeams(page);
    await createTeamAndEnter(page, 'Socket Test Team');

    // The chat textarea being enabled indicates the socket connection is established
    const textarea = page.locator('textarea.ci-input');
    await expect(textarea).toBeVisible({ timeout: 15000 });
    await expect(textarea).toBeEnabled({ timeout: 10000 });

    // The send button should be present (disabled until text is entered)
    const sendBtn = page.locator('button:has-text("➤")');
    await expect(sendBtn).toBeVisible({ timeout: 5000 });
  });
});
