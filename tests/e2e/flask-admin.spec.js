const { test, expect } = require('./fixtures/test-helpers');

test.describe('Admin Panel', () => {
  test('GET /admin should be protected or accessible', async ({ page }) => {
    const response = await page.goto('/admin');
    expect([200, 302]).toContain(response.status());
  });

  test('GET /api/admin/unread-count should return auth-related status', async ({ apiContext }) => {
    const response = await apiContext.get('/api/admin/unread-count');
    expect([200, 302, 401, 403]).toContain(response.status());
  });
});
