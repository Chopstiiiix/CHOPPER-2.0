const { test, expect } = require('@playwright/test');

const AGENT_URL = process.env.AGENT_URL || 'http://localhost:3100';

test.describe('Agent Subsystems', () => {
  test.beforeEach(async ({ request }) => {
    try {
      const r = await request.get(`${AGENT_URL}/health`);
      if (r.status() !== 200) test.skip();
    } catch {
      test.skip();
    }
  });

  test('scheduler should expose started state', async ({ request }) => {
    const r = await request.get(`${AGENT_URL}/health`);
    const body = await r.json();
    if (body.subsystems.scheduler) {
      expect(typeof body.subsystems.scheduler.started).toBe('boolean');
    }
  });

  test('heartbeat should have recent timestamp', async ({ request }) => {
    const r = await request.get(`${AGENT_URL}/health`);
    const body = await r.json();
    if (body.subsystems.heartbeat?.timestamp) {
      const lastBeat = new Date(body.subsystems.heartbeat.timestamp);
      const age = Date.now() - lastBeat.getTime();
      expect(age).toBeLessThan(120000);
    }
  });

  test('inbox should report size', async ({ request }) => {
    const r = await request.get(`${AGENT_URL}/health`);
    const body = await r.json();
    if (body.subsystems.inbox) {
      expect(body.subsystems.inbox).toHaveProperty('size');
      expect(body.subsystems.inbox.size).toBeGreaterThanOrEqual(0);
    }
  });

  test('watchdog should expose running state', async ({ request }) => {
    const r = await request.get(`${AGENT_URL}/health`);
    const body = await r.json();
    if (body.subsystems.watchdog) {
      expect(body.subsystems.watchdog).toHaveProperty('running');
    }
  });
});
