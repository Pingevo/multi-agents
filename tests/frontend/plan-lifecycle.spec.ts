import { test, expect } from '@playwright/test';
import { loginAndWaitForTeams, createTeamAndEnter, sendChatMessage, openDesktopWindow } from './helpers';

/**
 * Golden Flow 2: Plan Lifecycle
 * Send message → plan card renders → approve → task appears in Tasks window → notification appears.
 * Catches reply_notifications and team_id regressions.
 */
test.describe('Plan Lifecycle', () => {
  test('send plan message, approve plan, verify task and notification appear', async ({ page }) => {
    await loginAndWaitForTeams(page);
    await createTeamAndEnter(page, 'Plan Lifecycle Team');

    // Send a message that will trigger a plan response from the fake LLM
    await sendChatMessage(page, 'Research and write a summary about AI agents');

    // Wait for the plan card to render — it has "อนุมัติแผน" (approve) and "ปฏิเสธ" (reject) buttons
    const approveBtn = page.locator('button.cp-btn.approve:has-text("อนุมัติแผน")').first();
    await expect(approveBtn).toBeVisible({ timeout: 30000 });

    // Verify reject button is also present
    const rejectBtn = page.locator('button.cp-btn.reject:has-text("ปฏิเสธ")').first();
    await expect(rejectBtn).toBeVisible();

    // Approve the plan
    await approveBtn.click();

    // After approval, the plan card should show "✅ อนุมัติแล้ว"
    await expect(page.locator('text=อนุมัติแล้ว').first()).toBeVisible({ timeout: 10000 });

    // Open the Tasks window and verify a task appears
    await openDesktopWindow(page, 'tasks');

    // The tasks list should be visible
    await expect(page.locator('.tasks-list')).toBeVisible({ timeout: 5000 });

    // After plan approval, the Tasks window should show the run with agent info
    // The tasks list shows the user message text and agent names like "Worker1"
    const taskContent = page.locator('.tasks-list').locator('text=Worker1').first();
    await expect(taskContent).toBeVisible({ timeout: 15000 });

    // Verify a notification appeared — check the notification badge (🔔) in the taskbar
    // After plan approval, a notification should be generated
    await expect(page.locator('text=🔔').first()).toBeVisible({ timeout: 10000 });
  });

  test('reject plan shows rejected state', async ({ page }) => {
    await loginAndWaitForTeams(page);
    await createTeamAndEnter(page, 'Plan Reject Team');

    await sendChatMessage(page, 'Research and write a summary about AI agents');

    const rejectBtn = page.locator('button.cp-btn.reject:has-text("ปฏิเสธ")').first();
    await expect(rejectBtn).toBeVisible({ timeout: 30000 });

    await rejectBtn.click();

    // After rejection, the plan card should show "❌ ปฏิเสธแล้ว"
    await expect(page.locator('text=ปฏิเสธแล้ว').first()).toBeVisible({ timeout: 10000 });
  });
});
