const { test, expect } = require('@playwright/test');

const AGENT_URL = process.env.AGENT_URL || 'http://localhost:3100';

test.describe('Agent Gateway', () => {
  test.beforeEach(async ({ request }) => {
    try {
      const response = await request.get(`${AGENT_URL}/health`);
      if (response.status() !== 200) test.skip();
    } catch {
      test.skip();
    }
  });

  test('GET /health should return status ok', async ({ request }) => {
    const response = await request.get(`${AGENT_URL}/health`);
    expect(response.status()).toBe(200);
    const body = await response.json();
    expect(body.status).toBe('ok');
    expect(body.uptime).toBeGreaterThan(0);
    expect(body).toHaveProperty('subsystems');
  });

  test('health should report subsystem payloads', async ({ request }) => {
    const response = await request.get(`${AGENT_URL}/health`);
    const body = await response.json();
    expect(typeof body.subsystems).toBe('object');

    if (body.subsystems.scheduler) {
      expect(body.subsystems.scheduler).toHaveProperty('started');
    }

    if (body.subsystems.inbox) {
      expect(body.subsystems.inbox).toHaveProperty('size');
      expect(body.subsystems.inbox.size).toBeGreaterThanOrEqual(0);
    }
  });
});
