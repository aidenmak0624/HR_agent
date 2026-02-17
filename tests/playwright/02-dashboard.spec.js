// ============================================
// DASHBOARD PAGE TESTS
// Tests: KPI cards, role-scoped labels, charts,
//        quick actions, activity feed
// ============================================
const { test, expect } = require('@playwright/test');
const { goToPage } = require('./helpers');

test.describe('Dashboard Page', () => {

  // ---- Page Structure ----

  test('should render dashboard with all KPI cards', async ({ page }) => {
    await goToPage(page, '/dashboard', 'employee');
    await expect(page.locator('#kpi-employees')).toBeVisible();
    await expect(page.locator('#kpi-leave-requests')).toBeVisible();
    await expect(page.locator('#kpi-approvals')).toBeVisible();
    await expect(page.locator('#kpi-queries')).toBeVisible();
  });

  test('should render charts section', async ({ page }) => {
    await goToPage(page, '/dashboard', 'employee');
    await expect(page.locator('#departmentChart')).toBeVisible();
    await expect(page.locator('#queryTrendChart')).toBeVisible();
  });

  test('should render quick action buttons', async ({ page }) => {
    await goToPage(page, '/dashboard', 'employee');
    const actionBtns = page.locator('.action-btn');
    const count = await actionBtns.count();
    expect(count).toBe(3);
  });

  // ---- KPI Values Load ----

  test('should load KPI values from API (not show placeholder)', async ({ page }) => {
    await goToPage(page, '/dashboard', 'hr_admin');
    await page.waitForTimeout(2500);
    const empValue = await page.locator('#kpi-employees').textContent();
    expect(empValue?.trim()).not.toBe('--');
  });

  // ---- Role-Scoped KPI Labels ----

  test('Employee: should show employee-specific KPI labels', async ({ page }) => {
    await goToPage(page, '/dashboard', 'employee');
    await page.waitForTimeout(2500);
    const labels = await page.locator('.kpi-label').allTextContents();
    expect(labels.some(l => l.includes('Dept. Headcount') || l.includes('My Leave'))).toBe(true);
  });

  test('Manager: should show manager-specific KPI labels', async ({ page }) => {
    await goToPage(page, '/dashboard', 'manager');
    await page.waitForTimeout(2500);
    const labels = await page.locator('.kpi-label').allTextContents();
    expect(labels.some(l => l.includes('Team Headcount') || l.includes('Team Leave'))).toBe(true);
  });

  test('HR Admin: should show company-wide KPI labels', async ({ page }) => {
    await goToPage(page, '/dashboard', 'hr_admin');
    await page.waitForTimeout(2500);
    const labels = await page.locator('.kpi-label').allTextContents();
    expect(labels.some(l => l.includes('Total Employees') || l.includes('Open Leave'))).toBe(true);
  });

  // ---- Role-Scoped KPI Values via API ----

  test('API: Employee metrics should return scoped employee count', async ({ page }) => {
    const response = await page.request.get('/api/v2/metrics', {
      headers: { 'X-User-Role': 'employee' },
    });
    const json = await response.json();
    expect(json.data.role).toBe('employee');
    expect(json.data.total_employees).toBeLessThan(100);
  });

  test('API: HR Admin metrics should return company-wide count', async ({ page }) => {
    const response = await page.request.get('/api/v2/metrics', {
      headers: { 'X-User-Role': 'hr_admin' },
    });
    const json = await response.json();
    expect(json.data.role).toBe('hr_admin');
    expect(json.data.total_employees).toBeGreaterThanOrEqual(50);
  });

  // ---- Quick Actions Navigation ----

  test('quick action "New Leave Request" should navigate to /leave', async ({ page }) => {
    await goToPage(page, '/dashboard', 'employee');
    await page.locator('.action-btn >> text=New Leave Request').click();
    await page.waitForLoadState('domcontentloaded');
    expect(page.url()).toContain('/leave');
  });

  test('quick action "Ask Agent" should navigate to /chat', async ({ page }) => {
    await goToPage(page, '/dashboard', 'employee');
    await page.locator('.action-btn >> text=Ask Agent').click();
    await page.waitForLoadState('domcontentloaded');
    expect(page.url()).toContain('/chat');
  });

  // ---- Sidebar Active State ----

  test('dashboard nav item should be marked active', async ({ page }) => {
    await goToPage(page, '/dashboard', 'employee');
    const dashLink = page.locator('.nav-item[data-page="dashboard"]');
    await expect(dashLink).toHaveClass(/active/);
  });
});
