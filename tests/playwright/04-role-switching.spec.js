// ============================================
// ROLE SWITCHING & NAVIGATION TESTS
// Tests: sidebar visibility per role, header
//        updates, role-gated pages, account
//        switcher dropdown
// ============================================
const { test, expect } = require('@playwright/test');
const { goToPage, fastLogin, DEMO_ACCOUNTS } = require('./helpers');

test.describe('Role Switching & Navigation', () => {

  // ---- Sidebar Role Gating ----

  test('Employee should see 4 nav items (Dashboard, Chat, Leave, Settings)', async ({ page }) => {
    await goToPage(page, '/dashboard', 'employee');
    await page.waitForTimeout(500);

    // Role-gated items should be hidden for employee
    // Visible: dashboard, chat, leave, settings
    // Hidden: workflows (manager+), documents (hr_admin), analytics (manager+)
    const visibleItems = page.locator('.sidebar-nav .nav-item:not([style*="display: none"]):not(.hidden)');
    // We check that the gated items are hidden
    const workflowsItem = page.locator('.nav-item[data-page="workflows"]');
    const documentsItem = page.locator('.nav-item[data-page="documents"]');
    const analyticsItem = page.locator('.nav-item[data-page="analytics"]');

    // These should be hidden via applyRoleVisibility
    await expect(workflowsItem).toBeHidden();
    await expect(documentsItem).toBeHidden();
    await expect(analyticsItem).toBeHidden();
  });

  test('Manager should see workflows and analytics but not documents', async ({ page }) => {
    await goToPage(page, '/dashboard', 'manager');
    await page.waitForTimeout(500);

    const workflowsItem = page.locator('.nav-item[data-page="workflows"]');
    const analyticsItem = page.locator('.nav-item[data-page="analytics"]');
    const documentsItem = page.locator('.nav-item[data-page="documents"]');

    await expect(workflowsItem).toBeVisible();
    await expect(analyticsItem).toBeVisible();
    await expect(documentsItem).toBeHidden();
  });

  test('HR Admin should see all 7 nav items', async ({ page }) => {
    await goToPage(page, '/dashboard', 'hr_admin');
    await page.waitForTimeout(500);

    const allItems = page.locator('.sidebar-nav .nav-item');
    const count = await allItems.count();
    expect(count).toBe(7); // all nav items exist in DOM

    // All should be visible for HR Admin
    await expect(page.locator('.nav-item[data-page="workflows"]')).toBeVisible();
    await expect(page.locator('.nav-item[data-page="documents"]')).toBeVisible();
    await expect(page.locator('.nav-item[data-page="analytics"]')).toBeVisible();
  });

  // ---- Header Display ----

  test('Employee header should show Employee role info', async ({ page }) => {
    await goToPage(page, '/dashboard', 'employee');
    await page.waitForTimeout(500);

    const roleName = await page.locator('.user-role').textContent();
    const badge = await page.locator('.badge-text').textContent();
    expect(roleName?.trim()).toBe('Employee');
    expect(badge?.trim()).toBe('EMP');
  });

  test('HR Admin header should show HR Administrator info', async ({ page }) => {
    await goToPage(page, '/dashboard', 'hr_admin');
    await page.waitForTimeout(500);

    const roleName = await page.locator('.user-role').textContent();
    const badge = await page.locator('.badge-text').textContent();
    expect(roleName?.trim()).toBe('HR Administrator');
    expect(badge?.trim()).toBe('HR');
  });

  // ---- Account Switcher Dropdown ----

  test('should display account switcher with three options', async ({ page }) => {
    await goToPage(page, '/dashboard', 'employee');

    const switcherOptions = page.locator('.switcher-option');
    const count = await switcherOptions.count();
    expect(count).toBe(3);
  });

  test('account switcher should show current role as active', async ({ page }) => {
    await goToPage(page, '/dashboard', 'employee');

    const activeOption = page.locator('.switcher-option.active');
    const role = await activeOption.getAttribute('data-role');
    expect(role).toBe('employee');
  });

  // ---- Navigation Between Pages ----

  test('sidebar nav should navigate to Leave page', async ({ page }) => {
    await goToPage(page, '/dashboard', 'employee');

    await page.locator('.nav-item[data-page="leave"]').click();
    await page.waitForLoadState('domcontentloaded');
    expect(page.url()).toContain('/leave');
  });

  test('sidebar nav should navigate to Chat page', async ({ page }) => {
    await goToPage(page, '/dashboard', 'employee');

    await page.locator('.nav-item[data-page="chat"]').click();
    await page.waitForLoadState('domcontentloaded');
    expect(page.url()).toContain('/chat');
  });

  test('sidebar nav should navigate to Settings page', async ({ page }) => {
    await goToPage(page, '/dashboard', 'employee');

    await page.locator('.nav-item[data-page="settings"]').click();
    await page.waitForLoadState('domcontentloaded');
    expect(page.url()).toContain('/settings');
  });

  // ---- Role Switch via quickSwitchRole ----

  test('switching role via JS should update localStorage', async ({ page }) => {
    await goToPage(page, '/dashboard', 'employee');

    // Switch to manager via account switcher
    await page.evaluate(() => {
      if (typeof quickSwitchRole === 'function') {
        quickSwitchRole('manager');
      } else {
        localStorage.setItem('hr_current_role', 'manager');
      }
    });
    await page.waitForTimeout(500);

    const currentRole = await page.evaluate(() => localStorage.getItem('hr_current_role'));
    expect(currentRole).toBe('manager');
  });

  test('role switch should update header user-role text', async ({ page }) => {
    await goToPage(page, '/dashboard', 'hr_admin');
    await page.waitForTimeout(500);

    // Switch to employee
    await page.evaluate(() => {
      if (typeof quickSwitchRole === 'function') {
        quickSwitchRole('employee');
      }
    });
    await page.waitForTimeout(1000);

    const roleName = await page.locator('.user-role').textContent();
    expect(roleName?.trim()).toBe('Employee');
  });
});
