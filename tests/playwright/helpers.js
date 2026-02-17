/**
 * Shared test helpers for HR Intelligence Platform Playwright tests
 */

/**
 * Demo account credentials used across tests
 */
const DEMO_ACCOUNTS = {
  employee: {
    email: 'john.smith@company.com',
    password: 'demo123',
    name: 'John Smith',
    role: 'employee',
    title: 'Employee',
    badge: 'EMP',
    department: 'Engineering',
  },
  manager: {
    email: 'sarah.chen@company.com',
    password: 'demo123',
    name: 'Sarah Chen',
    role: 'manager',
    title: 'Manager',
    badge: 'MGR',
    department: 'Engineering',
  },
  hr_admin: {
    email: 'emily.rodriguez@company.com',
    password: 'demo123',
    name: 'Emily Rodriguez',
    role: 'hr_admin',
    title: 'HR Administrator',
    badge: 'HR',
    department: 'Human Resources',
  },
};

/**
 * Login via the UI login form
 */
async function loginAs(page, role = 'employee') {
  const account = DEMO_ACCOUNTS[role];
  await page.goto('/login');
  await page.waitForLoadState('domcontentloaded');

  // Clear any existing token so we don't auto-redirect
  await page.evaluate(() => localStorage.clear());
  await page.goto('/login');
  await page.waitForLoadState('domcontentloaded');

  // Fill in credentials
  await page.fill('#signinEmail', account.email);
  await page.fill('#signinPassword', account.password);
  await page.click('#signinBtn');

  // Wait for redirect to dashboard
  await page.waitForURL('**/dashboard', { timeout: 10000 });
}

/**
 * Login by setting localStorage directly (faster, for tests that don't test login itself)
 */
async function fastLogin(page, role = 'employee') {
  const account = DEMO_ACCOUNTS[role];
  await page.goto('/login');
  await page.waitForLoadState('domcontentloaded');

  await page.evaluate((acc) => {
    localStorage.setItem('auth_token', 'demo-token-' + acc.role);
    localStorage.setItem('hr_current_role', acc.role);
    localStorage.setItem('hr_user_name', acc.name);
    localStorage.setItem('hr_user_role', acc.title);
    localStorage.setItem('hr_role_badge', acc.badge);
    localStorage.setItem('hr_user_email', acc.email);
  }, account);
}

/**
 * Navigate to a page after fast-login
 */
async function goToPage(page, path, role = 'employee') {
  await fastLogin(page, role);
  await page.goto(path);
  await page.waitForLoadState('domcontentloaded');
}

/**
 * Wait for API response on a given endpoint pattern
 */
async function waitForApi(page, urlPattern, options = {}) {
  return page.waitForResponse(
    (resp) => resp.url().includes(urlPattern) && resp.status() === 200,
    { timeout: options.timeout || 10000 }
  );
}

/**
 * Get text content of an element, trimmed
 */
async function getText(page, selector) {
  const el = page.locator(selector).first();
  return (await el.textContent())?.trim() || '';
}

/**
 * Count visible nav items in sidebar
 */
async function countVisibleNavItems(page) {
  return page.locator('.sidebar-nav .nav-item:visible').count();
}

module.exports = {
  DEMO_ACCOUNTS,
  loginAs,
  fastLogin,
  goToPage,
  waitForApi,
  getText,
  countVisibleNavItems,
};
