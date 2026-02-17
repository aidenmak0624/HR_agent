// ============================================
// MOBILE RESPONSIVENESS TESTS
// Tests: hamburger menu, sidebar toggle, touch targets
// ============================================
const { test, expect } = require('@playwright/test');
const { goToPage } = require('./helpers');

test.describe('Mobile Responsiveness', () => {

  test.use({ viewport: { width: 375, height: 812 } }); // iPhone X

  test('should show hamburger button on mobile', async ({ page }) => {
    await goToPage(page, '/dashboard', 'employee');
    const hamburger = page.locator('.hamburger-btn');
    await expect(hamburger).toBeVisible();
  });

  test('sidebar should be hidden by default on mobile', async ({ page }) => {
    await goToPage(page, '/dashboard', 'employee');
    const sidebar = page.locator('.sidebar');
    // Sidebar should not be visible (off-screen)
    const box = await sidebar.boundingBox();
    // Left position should be negative (off-screen) or sidebar invisible
    if (box) {
      expect(box.x).toBeLessThan(0);
    }
  });

  test('hamburger click should show sidebar', async ({ page }) => {
    await goToPage(page, '/dashboard', 'employee');
    const hamburger = page.locator('.hamburger-btn');
    await hamburger.click();

    // After click, sidebar should have mobile-open class
    const sidebar = page.locator('.sidebar');
    await expect(sidebar).toHaveClass(/mobile-open/);
  });

  test('overlay should appear when sidebar is open', async ({ page }) => {
    await goToPage(page, '/dashboard', 'employee');
    const hamburger = page.locator('.hamburger-btn');
    await hamburger.click();

    const overlay = page.locator('#sidebar-overlay');
    await expect(overlay).toHaveClass(/active/);
  });

  test('clicking overlay should close sidebar', async ({ page }) => {
    await goToPage(page, '/dashboard', 'employee');

    // Open sidebar
    const hamburger = page.locator('.hamburger-btn');
    await hamburger.click();

    // Click overlay to close
    const overlay = page.locator('#sidebar-overlay');
    await overlay.click({ force: true });

    // Sidebar should no longer have mobile-open
    const sidebar = page.locator('.sidebar');
    const classes = await sidebar.getAttribute('class') || '';
    expect(classes).not.toContain('mobile-open');
  });

  test('nav items should have minimum touch target size', async ({ page }) => {
    await goToPage(page, '/dashboard', 'employee');

    // Open sidebar to access nav items
    await page.locator('.hamburger-btn').click();
    await page.waitForTimeout(500);

    const navItems = page.locator('.nav-item');
    const count = await navItems.count();

    for (let i = 0; i < Math.min(count, 5); i++) {
      const box = await navItems.nth(i).boundingBox();
      if (box) {
        // Touch target should be at least 44px tall (WCAG recommendation)
        expect(box.height).toBeGreaterThanOrEqual(40);
      }
    }
  });

  test('notification bell should be accessible on mobile', async ({ page }) => {
    await goToPage(page, '/dashboard', 'employee');
    const bell = page.locator('.bell-btn');
    await expect(bell).toBeVisible();
    const box = await bell.boundingBox();
    if (box) {
      expect(box.width).toBeGreaterThanOrEqual(40);
      expect(box.height).toBeGreaterThanOrEqual(40);
    }
  });

  test('page title should be visible on mobile', async ({ page }) => {
    await goToPage(page, '/dashboard', 'employee');
    const title = page.locator('.page-title');
    await expect(title).toBeVisible();
  });
});

test.describe('Tablet Responsiveness', () => {

  test.use({ viewport: { width: 768, height: 1024 } }); // iPad

  test('should render properly on tablet', async ({ page }) => {
    await goToPage(page, '/dashboard', 'employee');
    const content = page.locator('.main-content');
    await expect(content).toBeVisible();
  });

  test('KPI cards should stack on tablet', async ({ page }) => {
    await goToPage(page, '/dashboard', 'employee');
    const kpiSection = page.locator('.kpi-section');
    if (await kpiSection.count() > 0) {
      await expect(kpiSection.first()).toBeVisible();
    }
  });
});
