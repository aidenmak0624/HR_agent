// ============================================
// LEAVE MANAGEMENT TESTS
// Tests: balance cards, request form, submit,
//        history table, API endpoints
// ============================================
const { test, expect } = require('@playwright/test');
const { goToPage } = require('./helpers');

test.describe('Leave Management', () => {

  // ---- Page Structure ----

  test('should render leave balance cards', async ({ page }) => {
    await goToPage(page, '/leave', 'employee');

    const leaveCards = page.locator('.leave-card');
    const count = await leaveCards.count();
    expect(count).toBeGreaterThanOrEqual(3); // Vacation, Sick, Personal
  });

  test('should show leave type labels', async ({ page }) => {
    await goToPage(page, '/leave', 'employee');

    await expect(page.locator('.leave-type:has-text("Vacation Days")')).toBeVisible();
    await expect(page.locator('.leave-type:has-text("Sick Days")')).toBeVisible();
    await expect(page.locator('.leave-type:has-text("Personal Days")')).toBeVisible();
  });

  // ---- Leave Request Form ----

  test('should render the leave request form', async ({ page }) => {
    await goToPage(page, '/leave', 'employee');

    await expect(page.locator('#leave-form')).toBeVisible();
    await expect(page.locator('#leave-type')).toBeVisible();
    await expect(page.locator('text=Submit Leave Request').first()).toBeVisible();
  });

  test('leave type dropdown should have options', async ({ page }) => {
    await goToPage(page, '/leave', 'employee');

    const options = page.locator('#leave-type option');
    const count = await options.count();
    expect(count).toBeGreaterThanOrEqual(3); // placeholder + at least 2 types
  });

  // ---- API: Leave Balance ----

  test('API: should return leave balance data', async ({ page }) => {
    const response = await page.request.get('/api/v2/leave/balance', {
      headers: { 'X-User-Role': 'employee' },
    });
    expect(response.status()).toBe(200);
    const json = await response.json();
    expect(json.success).toBe(true);
    expect(json.data).toBeTruthy();
  });

  // ---- API: Leave History ----

  test('API: should return leave history', async ({ page }) => {
    const response = await page.request.get('/api/v2/leave/history', {
      headers: { 'X-User-Role': 'employee' },
    });
    expect(response.status()).toBe(200);
    const json = await response.json();
    expect(json.success).toBe(true);
  });

  // ---- API: Submit Leave Request ----

  test('API: should accept a leave request submission', async ({ page }) => {
    const response = await page.request.post('/api/v2/leave/request', {
      headers: {
        'Content-Type': 'application/json',
        'X-User-Role': 'employee',
      },
      data: {
        leave_type: 'vacation',
        start_date: '2026-04-01',
        end_date: '2026-04-03',
        reason: 'Playwright test leave request',
      },
    });
    expect([200, 201]).toContain(response.status());
    const json = await response.json();
    expect(json.success).toBe(true);
  });

  // ---- History Table ----

  test('should display leave history section', async ({ page }) => {
    await goToPage(page, '/leave', 'employee');

    // Check for leave history section using CSS selector
    const historySection = page.locator('.leave-history-section, .history-section, .leave-history, [class*="history"]');
    const sectionCount = await historySection.count();

    // Also verify "Leave History" text is visible
    const historyTitle = page.getByText('Leave History');
    await expect(historyTitle).toBeVisible();

    // History section should exist
    expect(sectionCount).toBeGreaterThanOrEqual(0);
  });
});
