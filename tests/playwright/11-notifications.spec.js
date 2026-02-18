// ============================================
// NOTIFICATIONS TESTS
// Tests: SSE stream, notification bell, API polling
// ============================================
const { test, expect } = require('@playwright/test');
const { goToPage, DEMO_ACCOUNTS } = require('./helpers');

test.describe('Real-time Notifications', () => {

  // ---- API: Notification Endpoint ----

  test('API: should return notifications array', async ({ page }) => {
    // Login to get JWT
    const loginResp = await page.request.post('/api/v2/auth/login', {
      headers: { 'Content-Type': 'application/json' },
      data: { email: DEMO_ACCOUNTS.employee.email, password: DEMO_ACCOUNTS.employee.password },
    });
    const loginJson = await loginResp.json();
    const token = loginJson.data.access_token;

    const response = await page.request.get('/api/v2/notifications', {
      headers: { 'Authorization': `Bearer ${token}` },
    });
    expect(response.status()).toBe(200);
    const json = await response.json();
    expect(json.success).toBe(true);
    expect(json.data.notifications).toBeDefined();
    expect(Array.isArray(json.data.notifications)).toBe(true);
  });

  // ---- API: SSE Stream Endpoint ----

  test('SSE notification stream should connect via EventSource', async ({ page }) => {
    const loginResp = await page.request.post('/api/v2/auth/login', {
      headers: { 'Content-Type': 'application/json' },
      data: { email: DEMO_ACCOUNTS.employee.email, password: DEMO_ACCOUNTS.employee.password },
    });
    const loginJson = await loginResp.json();
    const token = loginJson.data.access_token;

    // Navigate to a page and test SSE from browser context
    await page.goto('/login');
    const connected = await page.evaluate(async (tkn) => {
      return new Promise((resolve) => {
        const url = `/api/v2/notifications/stream?token=${encodeURIComponent(tkn)}`;
        const es = new EventSource(url);
        const timeout = setTimeout(() => { es.close(); resolve(false); }, 5000);
        es.onmessage = () => { clearTimeout(timeout); es.close(); resolve(true); };
        es.onerror = () => { clearTimeout(timeout); es.close(); resolve(false); };
      });
    }, token);
    expect(connected).toBe(true);
  });

  // ---- Notification Bell UI ----

  test('should display notification bell in topbar', async ({ page }) => {
    await goToPage(page, '/dashboard', 'employee');
    const bell = page.locator('.bell-btn');
    await expect(bell).toBeVisible();
  });

  test('notification panel should toggle on bell click', async ({ page }) => {
    await goToPage(page, '/dashboard', 'employee');
    const bell = page.locator('.bell-btn');
    await bell.click();
    const panel = page.locator('#notification-panel');
    // Panel should be visible after clicking bell (wait for CSS transition)
    await expect(panel).toBeVisible({ timeout: 5000 });
  });

  // ---- Notification Flow: Submit Leave → Check Notification ----

  test('API: leave submission should create notification for employee', async ({ page }) => {
    const loginResp = await page.request.post('/api/v2/auth/login', {
      headers: { 'Content-Type': 'application/json' },
      data: { email: DEMO_ACCOUNTS.employee.email, password: DEMO_ACCOUNTS.employee.password },
    });
    const loginJson = await loginResp.json();
    const token = loginJson.data.access_token;

    // Submit leave request
    const leaveResp = await page.request.post('/api/v2/leave/request', {
      headers: {
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json',
      },
      data: {
        leave_type: 'vacation',
        start_date: '2026-05-01',
        end_date: '2026-05-02',
        reason: 'Notification test',
      },
    });
    expect([200, 201]).toContain(leaveResp.status());

    // Check notifications
    const notifResp = await page.request.get('/api/v2/notifications', {
      headers: { 'Authorization': `Bearer ${token}` },
    });
    const notifJson = await notifResp.json();
    expect(notifJson.success).toBe(true);
    const notifs = notifJson.data.notifications;
    expect(notifs.length).toBeGreaterThan(0);
    // Most recent notification should be about the leave request
    const lastNotif = notifs[notifs.length - 1];
    expect(lastNotif.title).toContain('Leave');
  });

  // ---- Notification Flow: Approve → Notification ----

  test('API: leave approval should notify employee', async ({ page }) => {
    // Login as employee and submit leave
    const empLogin = await page.request.post('/api/v2/auth/login', {
      headers: { 'Content-Type': 'application/json' },
      data: { email: DEMO_ACCOUNTS.employee.email, password: DEMO_ACCOUNTS.employee.password },
    });
    const empToken = (await empLogin.json()).data.access_token;

    await page.request.post('/api/v2/leave/request', {
      headers: {
        'Authorization': `Bearer ${empToken}`,
        'Content-Type': 'application/json',
      },
      data: {
        leave_type: 'sick',
        start_date: '2026-06-10',
        end_date: '2026-06-11',
        reason: 'Approval notification test',
      },
    });

    // Login as manager and approve
    const mgrLogin = await page.request.post('/api/v2/auth/login', {
      headers: { 'Content-Type': 'application/json' },
      data: { email: DEMO_ACCOUNTS.manager.email, password: DEMO_ACCOUNTS.manager.password },
    });
    const mgrToken = (await mgrLogin.json()).data.access_token;

    // Get pending approvals
    const pendingResp = await page.request.get('/api/v2/workflows/pending', {
      headers: { 'Authorization': `Bearer ${mgrToken}` },
    });
    const pendingJson = await pendingResp.json();
    const pending = pendingJson.data.pending || [];

    if (pending.length > 0) {
      // Approve the first pending request
      const approveResp = await page.request.post('/api/v2/workflows/approve', {
        headers: {
          'Authorization': `Bearer ${mgrToken}`,
          'Content-Type': 'application/json',
        },
        data: { request_id: pending[0].request_id },
      });
      expect(approveResp.status()).toBe(200);
      const approveJson = await approveResp.json();
      expect(approveJson.success).toBe(true);
      expect(approveJson.data.status).toBe('approved');

      // Check employee notifications
      const notifResp = await page.request.get('/api/v2/notifications', {
        headers: { 'Authorization': `Bearer ${empToken}` },
      });
      const notifJson = await notifResp.json();
      const approvalNotifs = notifJson.data.notifications.filter(n => n.title.includes('Approved'));
      expect(approvalNotifs.length).toBeGreaterThan(0);
    }
  });
});
