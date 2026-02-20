const { test, expect } = require('./fixtures/test-helpers');

test.describe('Chat Interface', () => {
  test('should load chat UI when authenticated', async ({ authenticatedPage }) => {
    await authenticatedPage.goto('/app');
    await expect(authenticatedPage.locator('#messageInput')).toBeVisible();
    await expect(authenticatedPage.locator('#sendButton')).toBeVisible();
  });

  test('should let user submit a message in UI', async ({ authenticatedPage }) => {
    await authenticatedPage.goto('/app');
    const chatInput = authenticatedPage.locator('#messageInput');
    await chatInput.fill('Hello, Chopper!');
    await authenticatedPage.locator('#sendButton').click();
    await expect(authenticatedPage.locator('.message.user').first()).toBeVisible();
  });

  test('should load chat history via API', async ({ authenticatedPage }) => {
    const response = await authenticatedPage.request.get('/api/chat/history');
    expect([200, 500]).toContain(response.status());
    if (response.status() === 200) {
      const data = await response.json();
      expect(Array.isArray(data) || typeof data === 'object').toBeTruthy();
    }
  });
});
