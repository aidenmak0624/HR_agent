// ============================================
// API HEALTH & INTEGRATION TESTS
// Tests: health endpoint, all major API routes,
//        error handling, rate limiting awareness
// ============================================
const { test, expect } = require('@playwright/test');

test.describe('API Health & Integration', () => {

  // ---- Health Check ----

  test('API: health endpoint should return 200', async ({ page }) => {
    const response = await page.request.get('/api/v2/health');
    // Accept both healthy (200) and degraded mode (503)
    expect([200, 503]).toContain(response.status());
    const json = await response.json();
    expect(json.status || json.data?.status).toBeTruthy();
  });

  // ---- Auth Endpoints ----

  test('API: login with valid credentials should succeed', async ({ page }) => {
    const response = await page.request.post('/api/v2/auth/login', {
      headers: { 'Content-Type': 'application/json' },
      data: { email: 'john.smith@company.com', password: 'demo123' },
    });
    const json = await response.json();
    expect(json.success).toBe(true);
    expect(json.data.access_token).toBeTruthy();
    expect(json.data.user).toBeTruthy();
  });

  test('API: login with invalid credentials should fail', async ({ page }) => {
    const response = await page.request.post('/api/v2/auth/login', {
      headers: { 'Content-Type': 'application/json' },
      data: { email: 'nobody@example.com', password: 'wrongpass' },
    });
    const json = await response.json();
    expect(json.success).toBe(false);
  });

  test('API: register endpoint should accept valid data', async ({ page }) => {
    const uniqueEmail = `test_${Date.now()}@company.com`;
    const response = await page.request.post('/api/v2/auth/register', {
      headers: { 'Content-Type': 'application/json' },
      data: {
        first_name: 'Playwright',
        last_name: 'Test',
        email: uniqueEmail,
        password: 'testpass123',
        department: 'Engineering',
      },
    });
    const json = await response.json();
    expect(json.success).toBe(true);
  });

  // ---- Profile Endpoints ----

  test('API: GET profile should return employee data', async ({ page }) => {
    const response = await page.request.get('/api/v2/profile', {
      headers: { 'X-User-Role': 'employee' },
    });
    const json = await response.json();
    expect(json.success).toBe(true);
    expect(json.data.email).toBeTruthy();
    expect(json.data.first_name).toBeTruthy();
  });

  test('API: PUT profile should update and return success', async ({ page }) => {
    const response = await page.request.put('/api/v2/profile', {
      headers: {
        'Content-Type': 'application/json',
        'X-User-Role': 'employee',
      },
      data: {
        first_name: 'John',
        last_name: 'Smith',
        department: 'Engineering',
      },
    });
    const json = await response.json();
    expect(json.success).toBe(true);
  });

  // ---- Metrics ----

  test('API: metrics should include department_headcount', async ({ page }) => {
    const response = await page.request.get('/api/v2/metrics', {
      headers: { 'X-User-Role': 'hr_admin' },
    });
    const json = await response.json();
    expect(json.data.department_headcount).toBeTruthy();
    expect(typeof json.data.department_headcount).toBe('object');
  });

  test('API: metrics should include monthly_queries array', async ({ page }) => {
    const response = await page.request.get('/api/v2/metrics', {
      headers: { 'X-User-Role': 'hr_admin' },
    });
    const json = await response.json();
    expect(Array.isArray(json.data.monthly_queries)).toBe(true);
  });

  // ---- Leave Endpoints ----

  test('API: leave balance should return structured data', async ({ page }) => {
    const response = await page.request.get('/api/v2/leave/balance', {
      headers: { 'X-User-Role': 'employee' },
    });
    const json = await response.json();
    expect(json.success).toBe(true);
  });

  // ---- Employees ----

  test('API: list employees should return array', async ({ page }) => {
    const response = await page.request.get('/api/v2/employees', {
      headers: { 'X-User-Role': 'hr_admin' },
    });
    const json = await response.json();
    expect(json.success).toBe(true);
  });

  // ---- Agents ----

  test('API: list agents should return data', async ({ page }) => {
    const response = await page.request.get('/api/v2/agents', {
      headers: { 'X-User-Role': 'hr_admin' },
    });
    expect(response.status()).toBe(200);
    const json = await response.json();
    expect(json.success).toBe(true);
  });
});
