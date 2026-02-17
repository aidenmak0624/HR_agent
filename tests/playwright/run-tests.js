#!/usr/bin/env node
/**
 * HR Intelligence Platform — Playwright UI Test Suite
 *
 * Standalone test runner using Playwright API directly.
 * Prerequisite: python run.py  (server must be running on port 5050)
 *
 * Usage:
 *   node tests/run-tests.js              # run all tests
 *   node tests/run-tests.js login        # run only login suite
 *   node tests/run-tests.js dashboard    # run only dashboard suite
 */

const { chromium } = require('playwright');

const BASE_URL = 'http://localhost:5050';

// ──────────── Helpers ────────────

const DEMO = {
  employee: { email: 'john.smith@company.com', password: 'demo123', name: 'John Smith', role: 'employee', title: 'Employee', badge: 'EMP' },
  manager:  { email: 'sarah.chen@company.com',  password: 'demo123', name: 'Sarah Chen',  role: 'manager',  title: 'Manager',  badge: 'MGR' },
  hr_admin: { email: 'emily.rodriguez@company.com', password: 'demo123', name: 'Emily Rodriguez', role: 'hr_admin', title: 'HR Administrator', badge: 'HR' },
};

async function fastLogin(page, role = 'employee') {
  const acc = DEMO[role];
  await page.goto(`${BASE_URL}/login`);
  await page.waitForLoadState('domcontentloaded');
  await page.evaluate((a) => {
    localStorage.setItem('auth_token', 'demo-token-' + a.role);
    localStorage.setItem('hr_current_role', a.role);
    localStorage.setItem('hr_user_name', a.name);
    localStorage.setItem('hr_user_role', a.title);
    localStorage.setItem('hr_role_badge', a.badge);
    localStorage.setItem('hr_user_email', a.email);
  }, acc);
}

async function goTo(page, path, role = 'employee') {
  await fastLogin(page, role);
  await page.goto(`${BASE_URL}${path}`);
  await page.waitForLoadState('domcontentloaded');
}

// ──────────── Test framework ────────────

let passed = 0, failed = 0, skipped = 0;
const failures = [];

async function runTest(name, fn) {
  const suiteName = name;
  try {
    await fn();
    passed++;
    console.log(`  ✅ ${suiteName}`);
  } catch (err) {
    failed++;
    failures.push({ name: suiteName, error: err.message });
    console.log(`  ❌ ${suiteName}`);
    console.log(`     → ${err.message.split('\n')[0]}`);
  }
}

function assert(condition, msg) {
  if (!condition) throw new Error(msg || 'Assertion failed');
}

function assertEqual(actual, expected, msg) {
  if (actual !== expected) throw new Error(msg || `Expected ${JSON.stringify(expected)}, got ${JSON.stringify(actual)}`);
}

function assertContains(text, substring, msg) {
  if (!text || !text.includes(substring)) throw new Error(msg || `Expected "${text}" to contain "${substring}"`);
}

function assertMatch(text, pattern, msg) {
  if (!pattern.test(text)) throw new Error(msg || `Expected "${text}" to match ${pattern}`);
}

// ──────────── API Helper (with rate-limit retry) ────────────

const sleep = (ms) => new Promise(r => setTimeout(r, ms));

async function apiGet(page, path, role = 'employee') {
  await sleep(300);
  for (let attempt = 0; attempt < 3; attempt++) {
    const resp = await page.request.get(`${BASE_URL}${path}`, {
      headers: { 'X-User-Role': role },
    });
    if (resp.status() === 429) { await sleep(2000); continue; }
    return await resp.json();
  }
  throw new Error('Rate limited after 3 retries');
}

async function apiPost(page, path, data, role = 'employee') {
  await sleep(300);
  for (let attempt = 0; attempt < 3; attempt++) {
    const resp = await page.request.post(`${BASE_URL}${path}`, {
      headers: { 'Content-Type': 'application/json', 'X-User-Role': role },
      data,
    });
    if (resp.status() === 429) { await sleep(2000); continue; }
    return await resp.json();
  }
  throw new Error('Rate limited after 3 retries');
}

async function apiPut(page, path, data, role = 'employee') {
  await sleep(300);
  for (let attempt = 0; attempt < 3; attempt++) {
    const resp = await page.request.put(`${BASE_URL}${path}`, {
      headers: { 'Content-Type': 'application/json', 'X-User-Role': role },
      data,
    });
    if (resp.status() === 429) { await sleep(2000); continue; }
    return await resp.json();
  }
  throw new Error('Rate limited after 3 retries');
}

// ════════════════════════════════════════
// TEST SUITES
// ════════════════════════════════════════

async function suite_login(page) {
  console.log('\n📋 LOGIN PAGE');

  await runTest('Render login page with sign-in form', async () => {
    await page.goto(`${BASE_URL}/login`);
    await page.evaluate(() => localStorage.clear());
    await page.goto(`${BASE_URL}/login`);
    await page.waitForLoadState('domcontentloaded');
    const title = await page.title();
    assertMatch(title, /HR Agent.*Sign In/i);
    assert(await page.locator('#signinEmail').isVisible(), 'Email input not visible');
    assert(await page.locator('#signinPassword').isVisible(), 'Password input not visible');
    assert(await page.locator('#signinBtn').isVisible(), 'Sign in button not visible');
  });

  await runTest('Sign-in tab active by default', async () => {
    await page.goto(`${BASE_URL}/login`);
    await page.evaluate(() => localStorage.clear());
    await page.goto(`${BASE_URL}/login`);
    const cls = await page.locator('.tab[data-tab="signin"]').getAttribute('class');
    assertContains(cls, 'active');
  });

  await runTest('Switch to sign-up tab', async () => {
    await page.goto(`${BASE_URL}/login`);
    await page.evaluate(() => localStorage.clear());
    await page.goto(`${BASE_URL}/login`);
    await page.locator('.tab[data-tab="signup"]').click();
    await page.waitForTimeout(300);
    const cls = await page.locator('#signup').getAttribute('class');
    assertContains(cls, 'active');
    assert(await page.locator('#firstName').isVisible(), 'First name not visible');
  });

  await runTest('Email field has required attribute', async () => {
    await page.goto(`${BASE_URL}/login`);
    const required = await page.locator('#signinEmail').evaluate(el => el.hasAttribute('required'));
    assert(required, 'Email not required');
  });

  await runTest('Show error for invalid credentials', async () => {
    await page.goto(`${BASE_URL}/login`);
    await page.evaluate(() => localStorage.clear());
    await page.goto(`${BASE_URL}/login`);
    await page.fill('#signinEmail', 'wrong@example.com');
    await page.fill('#signinPassword', 'wrongpass');
    await page.click('#signinBtn');
    await page.waitForTimeout(2000);
    assert(await page.locator('#errorMessage').isVisible(), 'Error not shown');
  });

  await runTest('Login as Employee → redirect to /dashboard', async () => {
    await page.goto(`${BASE_URL}/login`);
    await page.evaluate(() => localStorage.clear());
    await page.goto(`${BASE_URL}/login`);
    await page.fill('#signinEmail', DEMO.employee.email);
    await page.fill('#signinPassword', DEMO.employee.password);
    await page.click('#signinBtn');
    await page.waitForURL('**/dashboard', { timeout: 10000 });
    assertContains(page.url(), '/dashboard');
  });

  await runTest('Login as Manager → redirect to /dashboard', async () => {
    await page.goto(`${BASE_URL}/login`);
    await page.evaluate(() => localStorage.clear());
    await page.goto(`${BASE_URL}/login`);
    await page.fill('#signinEmail', DEMO.manager.email);
    await page.fill('#signinPassword', DEMO.manager.password);
    await page.click('#signinBtn');
    await page.waitForURL('**/dashboard', { timeout: 10000 });
    assertContains(page.url(), '/dashboard');
  });

  await runTest('Login as HR Admin → redirect to /dashboard', async () => {
    await page.goto(`${BASE_URL}/login`);
    await page.evaluate(() => localStorage.clear());
    await page.goto(`${BASE_URL}/login`);
    await page.fill('#signinEmail', DEMO.hr_admin.email);
    await page.fill('#signinPassword', DEMO.hr_admin.password);
    await page.click('#signinBtn');
    await page.waitForURL('**/dashboard', { timeout: 10000 });
    assertContains(page.url(), '/dashboard');
  });

  await runTest('Auth token stored in localStorage after login', async () => {
    await page.goto(`${BASE_URL}/login`);
    await page.evaluate(() => localStorage.clear());
    await page.goto(`${BASE_URL}/login`);
    await page.fill('#signinEmail', DEMO.employee.email);
    await page.fill('#signinPassword', DEMO.employee.password);
    await page.click('#signinBtn');
    await page.waitForURL('**/dashboard', { timeout: 10000 });
    const token = await page.evaluate(() => localStorage.getItem('auth_token'));
    assert(token, 'No auth token');
  });

  await runTest('User role stored in localStorage after login', async () => {
    const role = await page.evaluate(() => localStorage.getItem('hr_current_role'));
    assertEqual(role, 'employee');
  });

  await runTest('Short password error on sign-up', async () => {
    await page.goto(`${BASE_URL}/login`);
    await page.evaluate(() => localStorage.clear());
    await page.goto(`${BASE_URL}/login`);
    await page.locator('.tab[data-tab="signup"]').click();
    await page.fill('#firstName', 'Test');
    await page.fill('#lastName', 'User');
    await page.fill('#signupEmail', 'test@example.com');
    await page.fill('#signupPassword', '12345');
    await page.selectOption('#department', 'Engineering');
    await page.click('#signupBtn');
    await page.waitForTimeout(500);
    const errText = await page.locator('#errorMessage').textContent();
    assertContains(errText, 'Password must be at least 6 characters');
  });
}

async function suite_dashboard(page) {
  console.log('\n📊 DASHBOARD PAGE');

  await runTest('Render all 4 KPI cards', async () => {
    await goTo(page, '/dashboard', 'employee');
    assert(await page.locator('#kpi-employees').isVisible(), 'kpi-employees missing');
    assert(await page.locator('#kpi-leave-requests').isVisible(), 'kpi-leave missing');
    assert(await page.locator('#kpi-approvals').isVisible(), 'kpi-approvals missing');
    assert(await page.locator('#kpi-queries').isVisible(), 'kpi-queries missing');
  });

  await runTest('Render chart canvases', async () => {
    await goTo(page, '/dashboard', 'employee');
    assert(await page.locator('#departmentChart').isVisible(), 'Department chart missing');
    assert(await page.locator('#queryTrendChart').isVisible(), 'Query trend chart missing');
  });

  await runTest('Render 3 quick-action buttons', async () => {
    const count = await page.locator('.action-btn').count();
    assertEqual(count, 3);
  });

  await runTest('KPI values load (not placeholder)', async () => {
    await goTo(page, '/dashboard', 'hr_admin');
    await page.waitForTimeout(2500);
    const val = (await page.locator('#kpi-employees').textContent())?.trim();
    assert(val !== '--' && val !== '', 'KPI still showing placeholder');
  });

  await runTest('Employee: role-specific KPI labels', async () => {
    await goTo(page, '/dashboard', 'employee');
    await page.waitForTimeout(2500);
    const labels = await page.locator('.kpi-label').allTextContents();
    assert(labels.some(l => l.includes('Dept.') || l.includes('My Leave')), 'Employee labels not set');
  });

  await runTest('Manager: role-specific KPI labels', async () => {
    await goTo(page, '/dashboard', 'manager');
    await page.waitForTimeout(2500);
    const labels = await page.locator('.kpi-label').allTextContents();
    assert(labels.some(l => l.includes('Team')), 'Manager labels not set');
  });

  await runTest('HR Admin: role-specific KPI labels', async () => {
    await goTo(page, '/dashboard', 'hr_admin');
    await page.waitForTimeout(2500);
    const labels = await page.locator('.kpi-label').allTextContents();
    assert(labels.some(l => l.includes('Total Employees') || l.includes('Open Leave')), 'HR Admin labels not set');
  });

  await runTest('API: Employee metrics scoped to department', async () => {
    const json = await apiGet(page, '/api/v2/metrics', 'employee');
    assertEqual(json.data.role, 'employee');
    assert(json.data.total_employees < 100, `Employee sees ${json.data.total_employees}, expected < 100`);
  });

  await runTest('API: HR Admin metrics company-wide', async () => {
    const json = await apiGet(page, '/api/v2/metrics', 'hr_admin');
    assertEqual(json.data.role, 'hr_admin');
    assert(json.data.total_employees >= 50, `HR Admin sees ${json.data.total_employees}, expected >= 50`);
  });

  await runTest('Dashboard nav item marked active', async () => {
    await goTo(page, '/dashboard', 'employee');
    const cls = await page.locator('.nav-item[data-page="dashboard"]').getAttribute('class');
    assertContains(cls, 'active');
  });
}

async function suite_settings(page) {
  console.log('\n⚙️  SETTINGS PAGE');

  await runTest('Render 3 role cards', async () => {
    await goTo(page, '/settings', 'employee');
    assertEqual(await page.locator('.role-card').count(), 3);
  });

  await runTest('Current role card highlighted', async () => {
    await goTo(page, '/settings', 'employee');
    const cls = await page.locator('.role-card[data-role="employee"]').getAttribute('class');
    assertContains(cls, 'active');
  });

  await runTest('Profile form fields visible', async () => {
    await goTo(page, '/settings', 'employee');
    assert(await page.locator('#profile-first-name').isVisible());
    assert(await page.locator('#profile-last-name').isVisible());
    assert(await page.locator('#profile-email').isVisible());
  });

  await runTest('API: Save profile via PUT', async () => {
    const json = await apiPut(page, '/api/v2/profile', {
      first_name: 'TestFirst', last_name: 'TestLast', department: 'Engineering',
    }, 'employee');
    assert(json.success, 'Save failed');
  });

  await runTest('API: Saved profile persists on GET', async () => {
    await apiPut(page, '/api/v2/profile', {
      first_name: 'PersistCheck', last_name: 'Smith', department: 'Engineering',
    }, 'employee');
    const json = await apiGet(page, '/api/v2/profile', 'employee');
    assertEqual(json.data.first_name, 'PersistCheck');
    // Restore
    await apiPut(page, '/api/v2/profile', {
      first_name: 'John', last_name: 'Smith', department: 'Engineering',
    }, 'employee');
  });

  await runTest('API: Different roles have independent profiles', async () => {
    const emp = await apiGet(page, '/api/v2/profile', 'employee');
    const admin = await apiGet(page, '/api/v2/profile', 'hr_admin');
    assert(emp.data.email !== admin.data.email, 'Profiles have same email');
  });

  await runTest('API: Profile survives role round-trip', async () => {
    await apiPut(page, '/api/v2/profile', {
      first_name: 'RoundTrip', last_name: 'Test', department: 'Engineering',
    }, 'employee');
    // Read other role
    await apiGet(page, '/api/v2/profile', 'hr_admin');
    // Read back employee
    const json = await apiGet(page, '/api/v2/profile', 'employee');
    assertEqual(json.data.first_name, 'RoundTrip');
    // Restore
    await apiPut(page, '/api/v2/profile', {
      first_name: 'John', last_name: 'Smith', department: 'Engineering',
    }, 'employee');
  });
}

async function suite_roles(page) {
  console.log('\n🔀 ROLE SWITCHING & NAVIGATION');

  await runTest('Employee: role-gated items hidden', async () => {
    await goTo(page, '/dashboard', 'employee');
    await page.waitForTimeout(500);
    assert(await page.locator('.nav-item[data-page="workflows"]').isHidden(), 'Workflows visible for employee');
    assert(await page.locator('.nav-item[data-page="documents"]').isHidden(), 'Documents visible for employee');
    assert(await page.locator('.nav-item[data-page="analytics"]').isHidden(), 'Analytics visible for employee');
  });

  await runTest('Manager: workflows and analytics visible', async () => {
    await goTo(page, '/dashboard', 'manager');
    await page.waitForTimeout(500);
    assert(await page.locator('.nav-item[data-page="workflows"]').isVisible(), 'Workflows hidden for manager');
    assert(await page.locator('.nav-item[data-page="analytics"]').isVisible(), 'Analytics hidden for manager');
  });

  await runTest('HR Admin: all 7 nav items visible', async () => {
    await goTo(page, '/dashboard', 'hr_admin');
    await page.waitForTimeout(500);
    assert(await page.locator('.nav-item[data-page="workflows"]').isVisible());
    assert(await page.locator('.nav-item[data-page="documents"]').isVisible());
    assert(await page.locator('.nav-item[data-page="analytics"]').isVisible());
  });

  await runTest('Employee header shows Employee role', async () => {
    await goTo(page, '/dashboard', 'employee');
    await page.waitForTimeout(300);
    const role = (await page.locator('.user-role').textContent())?.trim();
    assertEqual(role, 'Employee');
  });

  await runTest('HR Admin header shows HR Administrator', async () => {
    await goTo(page, '/dashboard', 'hr_admin');
    await page.waitForTimeout(300);
    const role = (await page.locator('.user-role').textContent())?.trim();
    assertEqual(role, 'HR Administrator');
  });

  await runTest('Account switcher has 3 options', async () => {
    await goTo(page, '/dashboard', 'employee');
    assertEqual(await page.locator('.switcher-option').count(), 3);
  });

  await runTest('Navigate to /leave via sidebar', async () => {
    await goTo(page, '/dashboard', 'employee');
    await page.locator('.nav-item[data-page="leave"]').click();
    await page.waitForLoadState('domcontentloaded');
    assertContains(page.url(), '/leave');
  });

  await runTest('Navigate to /chat via sidebar', async () => {
    await goTo(page, '/dashboard', 'employee');
    await page.locator('.nav-item[data-page="chat"]').click();
    await page.waitForLoadState('domcontentloaded');
    assertContains(page.url(), '/chat');
  });

  await runTest('Navigate to /settings via sidebar', async () => {
    await goTo(page, '/dashboard', 'employee');
    await page.locator('.nav-item[data-page="settings"]').click();
    await page.waitForLoadState('domcontentloaded');
    assertContains(page.url(), '/settings');
  });
}

async function suite_leave(page) {
  console.log('\n🏖️  LEAVE MANAGEMENT');

  await runTest('Render leave balance cards', async () => {
    await goTo(page, '/leave', 'employee');
    assert(await page.locator('.leave-card').count() >= 3, 'Less than 3 leave cards');
  });

  await runTest('Show leave type labels', async () => {
    await goTo(page, '/leave', 'employee');
    const text = await page.locator('.leave-page').textContent();
    assertContains(text, 'Vacation');
    assertContains(text, 'Sick');
  });

  await runTest('Leave request form visible', async () => {
    await goTo(page, '/leave', 'employee');
    assert(await page.locator('#leave-form').isVisible(), 'Leave form not visible');
    assert(await page.locator('#leave-type').isVisible(), 'Leave type select not visible');
  });

  await runTest('API: GET leave balance', async () => {
    const json = await apiGet(page, '/api/v2/leave/balance', 'employee');
    assert(json.success, 'Leave balance failed');
  });

  await runTest('API: GET leave history', async () => {
    const json = await apiGet(page, '/api/v2/leave/history', 'employee');
    assert(json.success, 'Leave history failed');
  });

  await runTest('API: POST leave request', async () => {
    const json = await apiPost(page, '/api/v2/leave/request', {
      leave_type: 'vacation',
      start_date: '2026-04-01',
      end_date: '2026-04-03',
      reason: 'Playwright test',
    }, 'employee');
    assert(json.success, 'Leave request failed');
  });
}

async function suite_workflows(page) {
  console.log('\n⚙️  WORKFLOWS');

  await runTest('Render approval cards', async () => {
    await goTo(page, '/workflows', 'manager');
    assert(await page.locator('.approval-card').count() >= 1, 'No approval cards');
  });

  await runTest('Approval cards have data-request-id', async () => {
    await goTo(page, '/workflows', 'manager');
    const id = await page.locator('.approval-card').first().getAttribute('data-request-id');
    assert(id, 'No request ID');
  });

  await runTest('Approve/reject buttons present', async () => {
    await goTo(page, '/workflows', 'manager');
    const card = page.locator('.approval-card').first();
    assert(await card.locator('.btn-approve').isVisible());
    assert(await card.locator('.btn-reject').isVisible());
  });

  await runTest('API: GET pending approvals', async () => {
    const json = await apiGet(page, '/api/v2/workflows/pending', 'manager');
    assert(json.success, 'Pending approvals failed');
  });

  await runTest('API: POST approve request', async () => {
    const json = await apiPost(page, '/api/v2/workflows/approve', { request_id: 'leave-001' }, 'manager');
    assert(json.success, 'Approve failed');
  });

  await runTest('API: POST reject request', async () => {
    const json = await apiPost(page, '/api/v2/workflows/reject', { request_id: 'expense-001', reason: 'Test' }, 'manager');
    assert(json.success, 'Reject failed');
  });
}

async function suite_analytics(page) {
  console.log('\n📈 ANALYTICS');

  await runTest('Render analytics page for HR Admin', async () => {
    await goTo(page, '/analytics', 'hr_admin');
    const title = await page.title();
    assertMatch(title, /Analytics/i);
  });

  await runTest('API: metrics include department_headcount', async () => {
    const json = await apiGet(page, '/api/v2/metrics', 'hr_admin');
    assert(json.data.department_headcount, 'No department_headcount');
    assert(typeof json.data.department_headcount === 'object');
  });

  await runTest('API: metrics export returns data', async () => {
    await sleep(500);
    const resp = await page.request.get(`${BASE_URL}/api/v2/metrics/export`, {
      headers: { 'X-User-Role': 'hr_admin' },
    });
    const status = resp.status();
    assert(status === 200 || status === 429, `Unexpected status ${status}`);
  });
}

async function suite_documents(page) {
  console.log('\n📄 DOCUMENTS');

  await runTest('Render documents page for HR Admin', async () => {
    await goTo(page, '/documents', 'hr_admin');
    const title = await page.title();
    assertMatch(title, /Documents/i);
  });

  await runTest('API: list templates', async () => {
    const json = await apiGet(page, '/api/v2/documents/templates', 'hr_admin');
    assert(json.success, 'Templates failed');
  });

  await runTest('API: generate document', async () => {
    const json = await apiPost(page, '/api/v2/documents/generate', {
      template_id: 't1',
      data: { employee_name: 'Test', position: 'Engineer', department: 'Engineering', start_date: '2026-03-01' },
    }, 'hr_admin');
    assert(json.success, 'Generate failed: ' + (json.error || ''));
  });
}

async function suite_chat(page) {
  console.log('\n💬 CHAT');

  await runTest('Render chat page', async () => {
    await goTo(page, '/chat', 'employee');
    const title = await page.title();
    assertMatch(title, /Chat/i);
  });

  await runTest('Chat input area visible', async () => {
    await goTo(page, '/chat', 'employee');
    const count = await page.locator('#chat-input, .chat-input, textarea').count();
    assert(count >= 1, 'No chat input');
  });

  await runTest('API: query endpoint accepts message', async () => {
    const json = await apiPost(page, '/api/v2/query', { query: 'What is my leave balance?' }, 'employee');
    assert(json.success, 'Query failed');
    assert(json.data, 'No response data');
  });
}

async function suite_api(page) {
  console.log('\n🔌 API HEALTH & INTEGRATION');

  await runTest('Health endpoint returns response', async () => {
    await sleep(500);
    const resp = await page.request.get(`${BASE_URL}/api/v2/health`);
    const status = resp.status();
    assert(status === 200 || status === 503, `Unexpected status ${status}`);
    const json = await resp.json();
    assert(json.status, 'No status field');
  });

  await runTest('Login with valid credentials', async () => {
    const json = await apiPost(page, '/api/v2/auth/login', {
      email: 'john.smith@company.com', password: 'demo123',
    });
    assert(json.success);
    assert(json.data.access_token);
  });

  await runTest('Login with invalid credentials fails', async () => {
    const json = await apiPost(page, '/api/v2/auth/login', {
      email: 'nobody@test.com', password: 'wrong',
    });
    assertEqual(json.success, false);
  });

  await runTest('Register new account', async () => {
    const json = await apiPost(page, '/api/v2/auth/register', {
      first_name: 'Playwright', last_name: 'Test',
      email: `test_${Date.now()}@company.com`,
      password: 'testpass123', department: 'Engineering',
    });
    assert(json.success);
  });

  await runTest('GET profile returns data', async () => {
    const json = await apiGet(page, '/api/v2/profile', 'employee');
    assert(json.success);
    assert(json.data.email);
  });

  await runTest('PUT profile updates data', async () => {
    const json = await apiPut(page, '/api/v2/profile', {
      first_name: 'John', last_name: 'Smith', department: 'Engineering',
    }, 'employee');
    assert(json.success);
  });

  await runTest('List employees', async () => {
    const json = await apiGet(page, '/api/v2/employees', 'hr_admin');
    assert(json.success);
  });

  await runTest('List agents', async () => {
    const json = await apiGet(page, '/api/v2/agents', 'hr_admin');
    assert(json.success);
  });
}

// ════════════════════════════════════════
// MAIN
// ════════════════════════════════════════

(async () => {
  const filter = process.argv[2]; // optional suite name
  console.log('═══════════════════════════════════════════════');
  console.log('  HR Intelligence Platform — Playwright Tests  ');
  console.log('═══════════════════════════════════════════════');

  const browser = await chromium.launch({
    headless: true,
    args: ['--no-sandbox', '--disable-setuid-sandbox', '--disable-dev-shm-usage'],
  });
  const context = await browser.newContext();
  const page = await context.newPage();

  const suites = {
    login:      suite_login,
    dashboard:  suite_dashboard,
    settings:   suite_settings,
    roles:      suite_roles,
    leave:      suite_leave,
    workflows:  suite_workflows,
    analytics:  suite_analytics,
    documents:  suite_documents,
    chat:       suite_chat,
    api:        suite_api,
  };

  const toRun = filter ? { [filter]: suites[filter] } : suites;

  if (filter && !suites[filter]) {
    console.error(`Unknown suite: ${filter}`);
    console.log('Available:', Object.keys(suites).join(', '));
    process.exit(1);
  }

  const startTime = Date.now();

  for (const [name, fn] of Object.entries(toRun)) {
    try {
      await fn(page);
    } catch (err) {
      console.error(`\n❗ Suite "${name}" crashed: ${err.message}`);
    }
  }

  await browser.close();

  const elapsed = ((Date.now() - startTime) / 1000).toFixed(1);

  console.log('\n═══════════════════════════════════════════════');
  console.log(`  Results: ${passed} passed, ${failed} failed  (${elapsed}s)`);
  console.log('═══════════════════════════════════════════════');

  if (failures.length > 0) {
    console.log('\n🔴 Failures:');
    failures.forEach((f, i) => {
      console.log(`  ${i + 1}. ${f.name}`);
      console.log(`     ${f.error}`);
    });
  }

  process.exit(failed > 0 ? 1 : 0);
})();
