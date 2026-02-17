const { test, expect } = require('@playwright/test');

test('smoke: can load login page', async ({ page }) => {
  await page.goto('/login');
  await expect(page).toHaveTitle(/HR Agent/i);
});
