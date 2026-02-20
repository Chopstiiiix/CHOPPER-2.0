const { test, expect } = require('./fixtures/test-helpers');

test.describe('Support Chat', () => {
  test('POST /api/support-chat should accept a message', async ({ authenticatedPage }) => {
    const response = await authenticatedPage.request.post('/api/support-chat', {
      data: { message: 'I need help with my account' },
    });
    expect([200, 201]).toContain(response.status());
  });

  test('GET /api/support-chat/unread should return unread count', async ({ authenticatedPage }) => {
    const response = await authenticatedPage.request.get('/api/support-chat/unread');
    expect(response.status()).toBe(200);
  });
});
