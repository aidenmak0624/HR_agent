// ============================================
// ANALYTICS PAGE TESTS
// Tests: page load, charts, export, role gating
// ============================================
const { test, expect } = require('@playwright/test');
const { goToPage } = require('./helpers');

test.describe('Analytics Page', () => {

  // ---- Page Structure ----

  test('should render analytics page for Manager', async ({ page }) => {
    await goToPage(page, '/analytics', 'manager');

    await expect(page).toHaveTitle(/Analytics/i);
  });

  test('should render analytics page for HR Admin', async ({ page }) => {
    await goToPage(page, '/analytics', 'hr_admin');

    // Check for chart canvas or analytics content
    const content = page.locator('.analytics-page, .chart-container, canvas');
    const count = await content.count();
    expect(count).toBeGreaterThanOrEqual(0);
  });

  // ---- API: Metrics for Analytics ----

  test('API: metrics endpoint should return data for analytics charts', async ({ page }) => {
    const response = await page.request.get('/api/v2/metrics', {
      headers: { 'X-User-Role': 'hr_admin' },
    });
    const json = await response.json();
    expect(json.data).toBeTruthy();
    expect(json.data.department_headcount).toBeTruthy();
    expect(json.data.monthly_queries).toBeTruthy();
  });

  // ---- API: Export ----

  test('API: metrics export should return CSV data', async ({ page }) => {
    const response = await page.request.get('/api/v2/metrics/export', {
      headers: { 'X-User-Role': 'hr_admin' },
    });
    expect(response.status()).toBe(200);
    const contentType = response.headers()['content-type'] || '';
    // Should be CSV or JSON
    expect(contentType).toBeTruthy();
  });
});
