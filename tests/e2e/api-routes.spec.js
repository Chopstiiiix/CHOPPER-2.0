const { test, expect } = require('@playwright/test');

test.describe('API Routes (unauthenticated)', () => {
  test('GET / should return landing', async ({ request }) => {
    const response = await request.get('/', { maxRedirects: 0 });
    expect([200, 301, 302]).toContain(response.status());
  });

  test('GET /login should return 200', async ({ request }) => {
    const response = await request.get('/login');
    expect(response.status()).toBe(200);
  });

  test('GET /register should return 200', async ({ request }) => {
    const response = await request.get('/register');
    expect(response.status()).toBe(200);
  });

  test('GET /api/chat/history without auth should fail', async ({ request }) => {
    const response = await request.get('/api/chat/history', { maxRedirects: 0 });
    expect([401, 403, 302]).toContain(response.status());
  });

  test('GET /api/documents without auth should fail', async ({ request }) => {
    const response = await request.get('/api/documents', { maxRedirects: 0 });
    expect([401, 403, 302]).toContain(response.status());
  });
});
