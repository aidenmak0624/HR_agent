// ============================================
// LOGIN PAGE TESTS
// Tests: page load, form validation, sign-in,
//        sign-up tab, demo quick-login, redirect
// ============================================
const { test, expect } = require('@playwright/test');
const { DEMO_ACCOUNTS, loginAs } = require('./helpers');

test.describe('Login Page', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/login');
    await page.evaluate(() => localStorage.clear());
    await page.goto('/login');
    await page.waitForLoadState('domcontentloaded');
  });

  // ---- Page Load ----

  test('should render the login page with sign-in form', async ({ page }) => {
    await expect(page).toHaveTitle(/HR Agent.*Sign In/i);
    await expect(page.locator('#signinEmail')).toBeVisible();
    await expect(page.locator('#signinPassword')).toBeVisible();
    await expect(page.locator('#signinBtn')).toBeVisible();
  });

  test('should display sign-in tab as active by default', async ({ page }) => {
    const signinTab = page.locator('.tab[data-tab="signin"]');
    await expect(signinTab).toHaveClass(/active/);
  });

  // ---- Tab Switching ----

  test('should switch to sign-up tab', async ({ page }) => {
    await page.locator('.tab[data-tab="signup"]').click();
    await expect(page.locator('#signup')).toHaveClass(/active/);
    await expect(page.locator('#firstName')).toBeVisible();
    await expect(page.locator('#signupEmail')).toBeVisible();
  });

  test('should switch back to sign-in tab from sign-up', async ({ page }) => {
    await page.locator('.tab[data-tab="signup"]').click();
    await expect(page.locator('#signup')).toHaveClass(/active/);
    await page.locator('.tab[data-tab="signin"]').click();
    await expect(page.locator('#signin')).toHaveClass(/active/);
  });

  // ---- Form Validation ----

  test('email field should have required attribute', async ({ page }) => {
    const isRequired = await page.locator('#signinEmail').evaluate(el => el.hasAttribute('required'));
    expect(isRequired).toBe(true);
  });

  test('password field should have required attribute', async ({ page }) => {
    const isRequired = await page.locator('#signinPassword').evaluate(el => el.hasAttribute('required'));
    expect(isRequired).toBe(true);
  });

  test('should show error for invalid credentials', async ({ page }) => {
    await page.fill('#signinEmail', 'wrong@example.com');
    await page.fill('#signinPassword', 'wrongpass');
    await page.click('#signinBtn');
    await page.waitForTimeout(1500);
    await expect(page.locator('#errorMessage')).toBeVisible();
  });

  // ---- Successful Login ----

  test('should login as Employee and redirect to dashboard', async ({ page }) => {
    await page.fill('#signinEmail', DEMO_ACCOUNTS.employee.email);
    await page.fill('#signinPassword', DEMO_ACCOUNTS.employee.password);
    await page.click('#signinBtn');
    await page.waitForURL('**/dashboard', { timeout: 10000 });
    expect(page.url()).toContain('/dashboard');
  });

  test('should login as Manager and redirect to dashboard', async ({ page }) => {
    await page.fill('#signinEmail', DEMO_ACCOUNTS.manager.email);
    await page.fill('#signinPassword', DEMO_ACCOUNTS.manager.password);
    await page.click('#signinBtn');
    await page.waitForURL('**/dashboard', { timeout: 10000 });
    expect(page.url()).toContain('/dashboard');
  });

  test('should login as HR Admin and redirect to dashboard', async ({ page }) => {
    await page.fill('#signinEmail', DEMO_ACCOUNTS.hr_admin.email);
    await page.fill('#signinPassword', DEMO_ACCOUNTS.hr_admin.password);
    await page.click('#signinBtn');
    await page.waitForURL('**/dashboard', { timeout: 10000 });
    expect(page.url()).toContain('/dashboard');
  });

  test('should store auth token in localStorage after login', async ({ page }) => {
    await page.fill('#signinEmail', DEMO_ACCOUNTS.employee.email);
    await page.fill('#signinPassword', DEMO_ACCOUNTS.employee.password);
    await page.click('#signinBtn');
    await page.waitForURL('**/dashboard', { timeout: 10000 });
    const token = await page.evaluate(() => localStorage.getItem('auth_token'));
    expect(token).toBeTruthy();
  });

  test('should store user role info in localStorage after login', async ({ page }) => {
    await page.fill('#signinEmail', DEMO_ACCOUNTS.employee.email);
    await page.fill('#signinPassword', DEMO_ACCOUNTS.employee.password);
    await page.click('#signinBtn');
    await page.waitForURL('**/dashboard', { timeout: 10000 });
    const role = await page.evaluate(() => localStorage.getItem('hr_current_role'));
    expect(role).toBe('employee');
  });

  // ---- Auto-redirect ----

  test('should redirect to dashboard if already logged in', async ({ page }) => {
    await loginAs(page, 'employee');
    expect(page.url()).toContain('/dashboard');
    await page.goto('/login');
    await page.waitForTimeout(2000);
    expect(page.url()).toContain('/dashboard');
  });

  // ---- Sign Up Validation ----

  test('should show error for short password on sign-up', async ({ page }) => {
    await page.locator('.tab[data-tab="signup"]').click();
    await page.fill('#firstName', 'Test');
    await page.fill('#lastName', 'User');
    await page.fill('#signupEmail', 'test@example.com');
    await page.fill('#signupPassword', '12345');
    await page.selectOption('#department', 'Engineering');
    await page.click('#signupBtn');
    await expect(page.locator('#errorMessage')).toContainText('Password must be at least 6 characters');
  });
});
