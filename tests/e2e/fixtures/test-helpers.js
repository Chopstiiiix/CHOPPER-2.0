const { test: base, expect } = require('@playwright/test');

const test = base.extend({
  authenticatedPage: async ({ page }, use) => {
    const timestamp = Date.now();
    const testUser = {
      firstName: `Test${timestamp}`,
      surname: 'User',
      email: `test_${timestamp}@test.com`,
      phone: '+15555550123',
      age: '25',
      password: 'TestPass123!',
    };

    await page.goto('/register');
    await page.fill('input[name="first_name"]', testUser.firstName);
    await page.fill('input[name="surname"]', testUser.surname);
    await page.fill('input[name="email"]', testUser.email);
    await page.fill('input[name="phone_number"]', testUser.phone);
    await page.fill('input[name="age"]', testUser.age);
    await page.fill('input[name="password"]', testUser.password);
    await page.fill('input[name="confirm_password"]', testUser.password);
    await page.click('button[type="submit"]');
    await page.waitForURL('**/app', { timeout: 10000 });

    page.testUser = testUser;
    await use(page);
  },

  apiContext: async ({ playwright, baseURL }, use) => {
    const context = await playwright.request.newContext({
      baseURL,
      extraHTTPHeaders: { 'Content-Type': 'application/json' },
    });
    await use(context);
    await context.dispose();
  },
});

module.exports = { test, expect };
