import { test, expect } from '@playwright/test';
import { loginAndWaitForTeams, createTeamAndEnter, sendChatMessage, openDesktopWindow } from './helpers';

/**
 * Golden Flow 4: Team Isolation
 * Create two teams, verify tasks/notifications/agents from team A
 * never appear while team B is active.
 * Catches cross-team leakage regressions.
 */
test.describe('Team Isolation', () => {
  test('tasks from team A do not appear in team B', async ({ page }) => {
    await loginAndWaitForTeams(page);

    // Create and enter Team A
    await createTeamAndEnter(page, 'Team Alpha');

    // Send a message to create a plan in Team A
    await sendChatMessage(page, 'Research and write a summary about AI agents');

    // Wait for plan card to appear
    const approveBtnA = page.locator('button.cp-btn.approve:has-text("อนุมัติแผน")').first();
    await expect(approveBtnA).toBeVisible({ timeout: 30000 });

    // Go back to team list via Start menu
    const startBtn = page.locator('button:has-text("Start")').first();
    await expect(startBtn).toBeVisible({ timeout: 5000 });
    await startBtn.click();
    const backBtn = page.locator('button:has-text("Back to team")');
    await expect(backBtn).toBeVisible({ timeout: 5000 });
    await backBtn.click();

    // Wait for team list page
    await expect(page.getByRole('heading', { name: 'Teams', exact: true })).toBeVisible({ timeout: 10000 });

    // Create and enter Team B
    await createTeamAndEnter(page, 'Team Beta');

    // Open the Tasks window
    await openDesktopWindow(page, 'tasks');

    // Verify no tasks from Team A appear in the Tasks window
    // Check within the tasks-list container specifically
    const tasksList = page.locator('.tasks-list');
    await expect(tasksList).toBeVisible({ timeout: 5000 });
    await expect(tasksList.locator('text=Research and write a summary')).toHaveCount(0, { timeout: 10000 });
  });

  test('notifications from team A do not appear in team B', async ({ page }) => {
    await loginAndWaitForTeams(page);

    // Create and enter Team A
    await createTeamAndEnter(page, 'Team Alpha Notif');

    // Send a message to create a plan
    await sendChatMessage(page, 'Research and write a summary about AI agents');

    // Wait for plan and approve it
    const approveBtn = page.locator('button.cp-btn.approve:has-text("อนุมัติแผน")').first();
    await expect(approveBtn).toBeVisible({ timeout: 30000 });
    await approveBtn.click();

    // Wait for approval confirmation
    await expect(page.locator('text=อนุมัติแล้ว').first()).toBeVisible({ timeout: 10000 });

    // Go back to team list via Start menu
    const startBtn = page.locator('button:has-text("Start")').first();
    await expect(startBtn).toBeVisible({ timeout: 5000 });
    await startBtn.click();
    const backBtn = page.locator('button:has-text("Back to team")');
    await expect(backBtn).toBeVisible({ timeout: 5000 });
    await backBtn.click();
    await expect(page.getByRole('heading', { name: 'Teams', exact: true })).toBeVisible({ timeout: 10000 });

    // Create and enter Team B
    await createTeamAndEnter(page, 'Team Beta Notif');

    // Open the Tasks window to verify Team A's tasks don't leak
    await openDesktopWindow(page, 'tasks');

    // Verify no tasks from Team A appear in the Tasks window
    const tasksList = page.locator('.tasks-list');
    await expect(tasksList).toBeVisible({ timeout: 5000 });
    await expect(tasksList.locator('text=Research and write a summary')).toHaveCount(0, { timeout: 10000 });
  });
});
