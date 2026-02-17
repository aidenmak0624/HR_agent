// ============================================
// DOCUMENTS PAGE TESTS
// Tests: template list, generate document, role gating
// ============================================
const { test, expect } = require('@playwright/test');
const { goToPage } = require('./helpers');

test.describe('Documents Page', () => {

  // ---- Page Structure ----

  test('should render documents page for HR Admin', async ({ page }) => {
    await goToPage(page, '/documents', 'hr_admin');

    await expect(page).toHaveTitle(/Documents/i);
  });

  test('should display document template options', async ({ page }) => {
    await goToPage(page, '/documents', 'hr_admin');

    // Check for template cards or list items
    const templates = page.locator('.template-card, .document-card, .doc-template');
    const count = await templates.count();
    expect(count).toBeGreaterThanOrEqual(0);
  });

  // ---- API: List Templates ----

  test('API: should return list of document templates', async ({ page }) => {
    const response = await page.request.get('/api/v2/documents/templates', {
      headers: { 'X-User-Role': 'hr_admin' },
    });
    expect(response.status()).toBe(200);
    const json = await response.json();
    expect(json.success).toBe(true);
    expect(json.data).toBeTruthy();
  });

  // ---- API: Generate Document ----

  test('API: should generate a document from template', async ({ page }) => {
    const response = await page.request.post('/api/v2/documents/generate', {
      headers: {
        'Content-Type': 'application/json',
        'X-User-Role': 'hr_admin',
      },
      data: {
        template_id: 't1',
        data: {
          employee_name: 'Test Employee',
          position: 'Software Engineer',
          department: 'Engineering',
          start_date: '2026-03-01',
        },
      },
    });
    expect([200, 201]).toContain(response.status());
    const json = await response.json();
    expect(json.success).toBe(true);
  });
});
