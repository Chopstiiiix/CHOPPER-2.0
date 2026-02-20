const { test, expect } = require('./fixtures/test-helpers');

test.describe('Authentication', () => {
  test('should show login page at /login', async ({ page }) => {
    await page.goto('/login');
    await expect(page).toHaveURL(/login/);
    await expect(page.locator('button[type="submit"]')).toBeVisible();
  });

  test('should load landing page at /', async ({ page }) => {
    await page.goto('/');
    await expect(page).toHaveURL(/\/(app|login)?$/);
  });

  test('should register a new user', async ({ page }) => {
    const ts = Date.now();
    await page.goto('/register');
    await page.fill('input[name="first_name"]', `First${ts}`);
    await page.fill('input[name="surname"]', 'User');
    await page.fill('input[name="email"]', `user_${ts}@test.com`);
    await page.fill('input[name="phone_number"]', '+15555550124');
    await page.fill('input[name="age"]', '24');
    await page.fill('input[name="password"]', 'SecurePass123!');
    await page.fill('input[name="confirm_password"]', 'SecurePass123!');
    await page.click('button[type="submit"]');
    await page.waitForURL('**/app', { timeout: 10000 });
    await expect(page).toHaveURL(/app/);
  });

  test('should reject invalid login', async ({ page }) => {
    await page.goto('/login');
    await page.fill('input[name="email"]', 'nonexistent_user@test.com');
    await page.fill('input[name="password"]', 'wrongpassword');
    await page.click('button[type="submit"]');
    await expect(page).toHaveURL(/login/);
  });

  test('should logout successfully', async ({ authenticatedPage }) => {
    await authenticatedPage.goto('/logout');
    await expect(authenticatedPage).toHaveURL(/\/(app|login)?$/, { timeout: 10000 });
  });

  test('/app should require authentication', async ({ page }) => {
    await page.goto('/app');
    await expect(page).toHaveURL(/login/);
  });
});
