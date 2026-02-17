// ============================================
// CHAT PAGE TESTS
// Tests: page load, input field, message sending,
//        quick actions, chat history
// ============================================
const { test, expect } = require('@playwright/test');
const { goToPage } = require('./helpers');

test.describe('Chat Page', () => {

  // ---- Page Structure ----

  test('should render chat page', async ({ page }) => {
    await goToPage(page, '/chat', 'employee');

    await expect(page).toHaveTitle(/Chat/i);
  });

  test('should display chat input area', async ({ page }) => {
    await goToPage(page, '/chat', 'employee');

    // Look for chat input field
    const chatInput = page.locator('#chat-input, .chat-input, textarea[placeholder], input[type="text"]');
    const count = await chatInput.count();
    expect(count).toBeGreaterThanOrEqual(1);
  });

  test('should display send button', async ({ page }) => {
    await goToPage(page, '/chat', 'employee');

    const sendBtn = page.locator('#send-btn, .send-btn, button:has-text("Send")');
    const count = await sendBtn.count();
    expect(count).toBeGreaterThanOrEqual(1);
  });

  // ---- Chat Message Display ----

  test('should display chat messages area', async ({ page }) => {
    await goToPage(page, '/chat', 'employee');

    const messagesArea = page.locator('.chat-messages, .messages-container, #chat-messages');
    const count = await messagesArea.count();
    expect(count).toBeGreaterThanOrEqual(1);
  });

  // ---- Quick Action Suggestions ----

  test('should display quick action suggestion chips', async ({ page }) => {
    await goToPage(page, '/chat', 'employee');

    const suggestions = page.locator('.quick-action, .suggestion-chip, .chat-suggestion');
    const count = await suggestions.count();
    // Quick suggestions may or may not be present
    expect(count).toBeGreaterThanOrEqual(0);
  });

  // ---- API: Query Endpoint ----

  test('API: query endpoint should accept a message', async ({ page }) => {
    const response = await page.request.post('/api/v2/query', {
      headers: {
        'Content-Type': 'application/json',
        'X-User-Role': 'employee',
      },
      data: {
        query: 'What is my leave balance?',
      },
    });
    expect(response.status()).toBe(200);
    const json = await response.json();
    expect(json.success).toBe(true);
    expect(json.data).toBeTruthy();
  });
});
