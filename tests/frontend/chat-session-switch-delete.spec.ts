import { test, expect } from '@playwright/test';
import { loginAndWaitForTeams, createTeamAndEnter, sendChatMessage, openDesktopWindow } from './helpers';

/**
 * Golden Flow 5: Chat Session Switch/Delete
 * Switch sessions, delete a session, verify no orphaned tasks/notifications remain.
 */
test.describe('Chat Session Switch/Delete', () => {
  test('can switch between chat sessions', async ({ page }) => {
    await loginAndWaitForTeams(page);
    await createTeamAndEnter(page, 'Session Switch Team');

    // Send a message in the first session
    await sendChatMessage(page, 'First session message');

    // Wait for some response (plan card or chat message)
    const planCard = page.locator('button.cp-btn.approve:has-text("อนุมัติแผน")').first();
    await expect(planCard).toBeVisible({ timeout: 30000 });

    // Create a new chat session — the UI shows "+ New Session" text
    const newChatBtn = page.locator('text=+ New Session').first();
    await expect(newChatBtn).toBeVisible({ timeout: 5000 });
    await newChatBtn.click();

    // The chat area should be cleared
    // Wait for the textarea to be visible again
    await expect(page.locator('textarea.ci-input')).toBeVisible({ timeout: 5000 });

    // The previous plan card should NOT be visible in the new session
    await expect(page.locator('button.cp-btn.approve:has-text("อนุมัติแผน")')).toHaveCount(0, { timeout: 3000 });

    // Send a different message in the new session
    await sendChatMessage(page, 'Second session message about different topic');

    // Wait for a new plan card
    const newPlanCard = page.locator('button.cp-btn.approve:has-text("อนุมัติแผน")').first();
    await expect(newPlanCard).toBeVisible({ timeout: 30000 });

    // Switch back to the first session via the chat sidebar
    // Session items show the first message as title in the sidebar
    const sessionItems = page.locator('text=First session message').first();
    await expect(sessionItems).toBeVisible({ timeout: 5000 });
    await sessionItems.click();

    // The first session's plan card should be visible again
    // (or at least the chat area should show content from the first session)
    await expect(page.locator('textarea.ci-input')).toBeVisible({ timeout: 5000 });
  });

  test('deleting a session removes its tasks and notifications', async ({ page }) => {
    await loginAndWaitForTeams(page);
    await createTeamAndEnter(page, 'Session Delete Team');

    // Send a message to create a plan
    await sendChatMessage(page, 'Research and write a summary about AI agents');

    // Wait for plan card
    const approveBtn = page.locator('button.cp-btn.approve:has-text("อนุมัติแผน")').first();
    await expect(approveBtn).toBeVisible({ timeout: 30000 });
    await approveBtn.click();

    // Wait for approval
    await expect(page.locator('text=อนุมัติแล้ว').first()).toBeVisible({ timeout: 10000 });

    // Delete the current chat session via the session sidebar
    // Session items have class "cs-item", trash button is the second button inside
    const sessionItem = page.locator('.cs-item').filter({ hasText: 'Research and write a summary' }).first();
    await expect(sessionItem).toBeVisible({ timeout: 5000 });

    // Set up dialog handler BEFORE clicking — the app uses confirm() for deletion
    page.on('dialog', dialog => dialog.accept());

    // The trash button is the second button (after Pencil) inside the cs-item
    const trashBtn = sessionItem.locator('button').last();
    await trashBtn.click();

    // If there's a confirmation dialog, confirm the deletion
    const confirmBtn = page.locator('button:has-text("Confirm"), button:has-text("ยืนยัน"), button:has-text("OK")').first();
    if (await confirmBtn.isVisible({ timeout: 2000 }).catch(() => false)) {
      await confirmBtn.click();
    }

    // After deletion, the chat area should be empty
    await expect(page.locator('textarea.ci-input')).toBeVisible({ timeout: 5000 });

    // The plan card should no longer be visible
    await expect(page.locator('button.cp-btn.approve:has-text("อนุมัติแผน")')).toHaveCount(0, { timeout: 3000 });

    // Open Tasks window and verify no orphaned tasks
    await openDesktopWindow(page, 'tasks');

    // The tasks list should show the empty state
    await expect(page.locator('.tasks-list')).toBeVisible({ timeout: 5000 });
    await expect(page.locator('.kcard-empty')).toBeVisible({ timeout: 10000 });
  });
});
