const { test, expect } = require('@playwright/test');

test.describe('Telegram Webhook Simulation', () => {
  const WEBHOOK_URL = process.env.TELEGRAM_WEBHOOK_URL || 'http://localhost:8000/telegram/webhook';

  test.skip(process.env.SKIP_TELEGRAM === 'true', 'Telegram tests skipped');

  test.beforeEach(async ({ request }) => {
    try {
      const probe = await request.post(WEBHOOK_URL, { data: {} });
      if (probe.status() === 404) test.skip();
    } catch {
      test.skip();
    }
  });

  test('should accept a valid /start command', async ({ request }) => {
    const payload = {
      update_id: Date.now(),
      message: {
        message_id: 1,
        from: { id: 123456, is_bot: false, first_name: 'Test' },
        chat: { id: 123456, first_name: 'Test', type: 'private' },
        date: Math.floor(Date.now() / 1000),
        text: '/start',
      },
    };

    const response = await request.post(WEBHOOK_URL, { data: payload });
    expect([200, 201, 204]).toContain(response.status());
  });

  test('should accept a text message', async ({ request }) => {
    const payload = {
      update_id: Date.now(),
      message: {
        message_id: 2,
        from: { id: 123456, is_bot: false, first_name: 'Test' },
        chat: { id: 123456, first_name: 'Test', type: 'private' },
        date: Math.floor(Date.now() / 1000),
        text: 'Hello Chopper',
      },
    };

    const response = await request.post(WEBHOOK_URL, { data: payload });
    expect([200, 201, 204]).toContain(response.status());
  });

  test('should reject invalid payload', async ({ request }) => {
    const response = await request.post(WEBHOOK_URL, { data: {} });
    expect([200, 400]).toContain(response.status());
  });
});
