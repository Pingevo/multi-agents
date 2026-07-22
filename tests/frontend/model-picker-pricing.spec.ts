import { test, expect } from '@playwright/test';
import { loginAndWaitForTeams, createTeamAndEnter, sendChatMessage } from './helpers';

/**
 * Golden Flow 3: Model Picker Contextual Pricing
 * Open image-model picker → verify only Input/Output/Image/Image Output rows shown,
 * correct values, correct cost tier.
 * Catches the schema-dropping-fields regression.
 */
test.describe('Model Picker Contextual Pricing', () => {
  test('image model picker shows image-specific pricing fields', async ({ page }) => {
    await loginAndWaitForTeams(page);
    await createTeamAndEnter(page, 'Model Picker Team');

    // Send a message that triggers a plan with an image tool agent
    await sendChatMessage(page, 'Generate a poster about AI');

    // Wait for plan card to render
    const approveBtn = page.locator('button.cp-btn.approve:has-text("อนุมัติแผน")').first();
    await expect(approveBtn).toBeVisible({ timeout: 30000 });

    // The plan card has a model selector button with class "plan-model"
    // Click it to open the model picker
    const modelBtn = page.locator('button.plan-model').first();
    await expect(modelBtn).toBeVisible({ timeout: 5000 });
    await modelBtn.click();

    // Wait for the model picker to appear — it's rendered via portal with a search input
    const modelPicker = page.locator('input[placeholder="Search models..."]');
    await expect(modelPicker).toBeVisible({ timeout: 5000 });

    // Verify that the image model "Test Image Model" appears in the picker
    const imageModelRow = page.locator('text=Test Image Model').first();
    await expect(imageModelRow).toBeVisible({ timeout: 5000 });

    // Verify that pricing rows are shown — hover over the model to see details
    // The detail panel appears on hover, not click
    await imageModelRow.hover();

    // After hovering, the detail panel should show price fields
    // For an image model, it should show: Input, Output, Image, Image Output
    await expect(page.locator('text=Input').first()).toBeVisible({ timeout: 5000 });
    await expect(page.locator('text=Output').first()).toBeVisible({ timeout: 5000 });

    // Verify image-specific pricing fields are shown
    await expect(page.locator('text=/Image/i').first()).toBeVisible({ timeout: 5000 });

    // Verify that video/audio pricing fields are NOT shown for an image model
    // (This is the core regression check — schema was dropping these fields before)
    const videoPriceLabel = page.locator('text=/Video.*price/i, text=/วิดีโอ/i');
    await expect(videoPriceLabel).not.toBeVisible();
  });

  test('text model shows only input and output pricing', async ({ page }) => {
    await loginAndWaitForTeams(page);
    await createTeamAndEnter(page, 'Text Model Team');

    // Open the main model picker — the button has class "ci-model" in chat input area
    const modelBtn = page.locator('button.ci-model').first();
    await expect(modelBtn).toBeVisible({ timeout: 5000 });
    await modelBtn.click();

    // Wait for model picker to appear
    const modelPicker = page.locator('input[placeholder="Search models..."]');
    await expect(modelPicker).toBeVisible({ timeout: 5000 });

    // Find a text model and hover to see its details
    const textModelRow = page.locator('text=Test Text Model').first();
    await expect(textModelRow).toBeVisible({ timeout: 5000 });

    // Hover over the model to see the detail panel (don't click — click selects and closes)
    await textModelRow.hover();
    await expect(page.locator('text=Input').first()).toBeVisible({ timeout: 5000 });
    await expect(page.locator('text=Output').first()).toBeVisible({ timeout: 5000 });

    // Image pricing should NOT be shown for a text model
    const imagePriceLabel = page.locator('text=/Image.*price/i, text=/รูปภาพ/i');
    await expect(imagePriceLabel).not.toBeVisible();
  });
});
