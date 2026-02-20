// ============================================
// BENEFITS PAGE TESTS
// Tests: render, data load, enroll action,
//        role-scoped behavior, mobile layout
// ============================================
const { test, expect } = require('@playwright/test');
const { goToPage } = require('./helpers');

test.describe('Benefits Enrollment', () => {
  test('should render benefits page sections', async ({ page }) => {
    await goToPage(page, '/benefits', 'employee');

    await expect(page.locator('[data-testid="benefits-page"]')).toBeVisible();
    await expect(page.locator('[data-testid="benefits-enrollments-section"]')).toBeVisible();
    await expect(page.locator('[data-testid="benefits-plans-section"]')).toBeVisible();
    await expect(page.locator('#benefits-refresh-btn')).toBeVisible();
  });

  test('should load plans and enrollments from API', async ({ page }) => {
    const plansResp = await page.request.get('/api/v2/benefits/plans', {
      headers: { 'X-User-Role': 'employee' },
    });
    const enrollmentsResp = await page.request.get('/api/v2/benefits/enrollments', {
      headers: { 'X-User-Role': 'employee' },
    });

    expect(plansResp.status()).toBe(200);
    expect(enrollmentsResp.status()).toBe(200);

    const plansJson = await plansResp.json();
    const enrollmentsJson = await enrollmentsResp.json();
    expect(plansJson.success).toBe(true);
    expect(Array.isArray(plansJson.data)).toBe(true);
    expect(plansJson.data.length).toBeGreaterThan(0);
    expect(enrollmentsJson.success).toBe(true);
    expect(Array.isArray(enrollmentsJson.data)).toBe(true);

    await goToPage(page, '/benefits', 'employee');
    await page.waitForTimeout(1800);
    await expect(page.locator('[data-testid="benefit-plan-card"]').first()).toBeVisible();
  });

  test('enroll action should succeed and update active enrollment state', async ({ page }) => {
    await goToPage(page, '/benefits', 'employee');
    await page.waitForTimeout(1800);

    const firstAvailableButton = page.locator('[data-action="enroll-plan"]:not([disabled])').first();
    await expect(firstAvailableButton).toBeVisible();

    const planId = await firstAvailableButton.getAttribute('data-plan-id');
    expect(planId).toBeTruthy();

    const coverageSelect = page.locator(`#coverage-level-${planId}`);
    if (await coverageSelect.count()) {
      await coverageSelect.selectOption('family');
    }

    await firstAvailableButton.click();
    await page.waitForTimeout(1800);

    const enrollmentItems = page.locator('[data-testid="enrollment-item"]');
    expect(await enrollmentItems.count()).toBeGreaterThan(0);

    const activeBadges = page.locator('.status-badge.status-active');
    expect(await activeBadges.count()).toBeGreaterThan(0);
  });

  test('role switch should change scoped enrollments data', async ({ page }) => {
    const employeeResp = await page.request.get('/api/v2/benefits/enrollments', {
      headers: { 'X-User-Role': 'employee' },
    });
    const managerResp = await page.request.get('/api/v2/benefits/enrollments', {
      headers: { 'X-User-Role': 'manager' },
    });
    const employeeJson = await employeeResp.json();
    const managerJson = await managerResp.json();
    expect(employeeJson.success).toBe(true);
    expect(managerJson.success).toBe(true);

    await goToPage(page, '/benefits', 'employee');
    await page.evaluate(() => {
      if (typeof quickSwitchRole === 'function') {
        quickSwitchRole('manager');
      }
    });

    const enrollmentsRequestPromise = page.waitForRequest((request) =>
      request.url().includes('/api/v2/benefits/enrollments')
    );
    await page.click('#benefits-refresh-btn');
    const enrollmentsRequest = await enrollmentsRequestPromise;
    await page.waitForTimeout(1200);

    expect(enrollmentsRequest.headers()['x-user-role']).toBe('manager');
    const currentRole = await page.evaluate(() => localStorage.getItem('hr_current_role'));
    expect(currentRole).toBe('manager');

    const employeeSignature = (employeeJson.data || [])
      .map((row) => `${row.plan_id}:${row.coverage_level}:${row.status}:${row.enrolled_at}`)
      .join('|');
    const managerSignature = (managerJson.data || [])
      .map((row) => `${row.plan_id}:${row.coverage_level}:${row.status}:${row.enrolled_at}`)
      .join('|');
    if (employeeSignature && managerSignature) {
      expect(employeeSignature).not.toBe(managerSignature);
    }
  });

  test('mobile viewport should keep benefits cards usable', async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await goToPage(page, '/benefits', 'employee');
    await page.waitForTimeout(1800);

    await expect(page.locator('#benefits-plans')).toBeVisible();
    const firstCard = page.locator('[data-testid="benefit-plan-card"]').first();
    await expect(firstCard).toBeVisible();
    await expect(firstCard.locator('[data-action="enroll-plan"]')).toBeVisible();
    await expect(page.locator('#benefits-refresh-btn')).toBeVisible();
  });
});
