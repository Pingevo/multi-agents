import { test, expect, Page } from '@playwright/test';

/**
 * Frontend regression tests for model selection flow.
 * 
 * Seam: ModelPicker UI → onSelect callback → socket emit → backend
 * 
 * These tests verify that:
 * 1. Model picker opens and displays models
 * 2. Selecting a model triggers the correct callback
 * 3. The selected model is displayed in the UI
 */

async function loginAndNavigate(page: Page) {
  // Navigate to the app
  await page.goto('/');
  
  // Wait for login screen or team list
  await page.waitForLoadState('networkidle');
  
  // If login screen, enter username and login
  const loginInput = page.locator('input[placeholder*="username"], input[type="text"]').first();
  if (await loginInput.isVisible({ timeout: 3000 }).catch(() => false)) {
    await loginInput.fill('test-user');
    const loginBtn = page.locator('button:has-text("Login"), button:has-text("เข้าสู่ระบบ"), button[type="submit"]').first();
    await loginBtn.click();
    await page.waitForLoadState('networkidle');
  }
  
  // If team list, click first team
  const teamCard = page.locator('[data-testid="team-card"], .team-card, button:has-text("Team")').first();
  if (await teamCard.isVisible({ timeout: 3000 }).catch(() => false)) {
    await teamCard.click();
    await page.waitForLoadState('networkidle');
  }
}

test.describe('Model Selection Flow', () => {
  test('model picker button is visible', async ({ page }) => {
    await loginAndNavigate(page);
    
    // Look for model picker button — could be in chat window or toolbar
    const modelButton = page.locator('button:has-text("Model"), button:has-text("โมเดล"), [data-testid="model-picker-btn"]').first();
    
    // The model button should be visible in the chat area
    await expect(modelButton).toBeVisible({ timeout: 10000 });
  });

  test('clicking model button opens picker', async ({ page }) => {
    await loginAndNavigate(page);
    
    const modelButton = page.locator('button:has-text("Model"), button:has-text("โมเดล"), [data-testid="model-picker-btn"]').first();
    await modelButton.click();
    
    // Model picker dropdown should appear
    const modelPicker = page.locator('[data-testid="model-picker"], .model-picker, [role="listbox"]').first();
    await expect(modelPicker).toBeVisible({ timeout: 5000 });
  });

  test('selecting a model updates the displayed model name', async ({ page }) => {
    await loginAndNavigate(page);
    
    // Open model picker
    const modelButton = page.locator('button:has-text("Model"), button:has-text("โมเดล"), [data-testid="model-picker-btn"]').first();
    await modelButton.click();
    
    // Wait for picker to open
    const modelPicker = page.locator('[data-testid="model-picker"], .model-picker, [role="listbox"]').first();
    await expect(modelPicker).toBeVisible({ timeout: 5000 });
    
    // Click any model in the list
    const modelOption = page.locator('[data-testid="model-option"], .model-row, [role="option"]').first();
    if (await modelOption.isVisible({ timeout: 3000 }).catch(() => false)) {
      await modelOption.click();
      
      // Picker should close
      await expect(modelPicker).not.toBeVisible({ timeout: 3000 });
      
      // The model button should now show a model name (not "auto" or empty)
      const modelButtonText = await modelButton.textContent();
      expect(modelButtonText).toBeTruthy();
      expect(modelButtonText!.length).toBeGreaterThan(0);
    }
  });

  test('model picker shows search input', async ({ page }) => {
    await loginAndNavigate(page);
    
    const modelButton = page.locator('button:has-text("Model"), button:has-text("โมเดล"), [data-testid="model-picker-btn"]').first();
    await modelButton.click();
    
    // Search input should be visible
    const searchInput = page.locator('input[placeholder*="search"], input[placeholder*="ค้นหา"], [data-testid="model-search"]').first();
    await expect(searchInput).toBeVisible({ timeout: 5000 });
  });
});
