import { expect, test, type Page } from '@playwright/test';

// Keep the mocked API in control across navigation. Live tests exercise the service worker.
test.use({ serviceWorkers: 'block' });

async function mockLocalAuth(page: Page, enabled: boolean) {
  let signedIn = false;
  const member = {
    id: 'test-owner',
    nickname: '測試旅人',
    email: null,
    account_type: 'local_test',
  };
  await page.route('**/api/v1/**', async (route) => {
    const req = route.request();
    const path = new URL(req.url()).pathname;
    if (path === '/api/v1/auth/local-test') {
      if (req.method() === 'GET') return route.fulfill({ json: { enabled } });
      const input = req.postDataJSON();
      if (enabled && input.username === 'traveler' && input.password === 'test fixture') {
        signedIn = true;
        return route.fulfill({ json: member });
      }
      return route.fulfill({ status: 401, json: { message: '帳號或密碼錯誤。' } });
    }
    if (path === '/api/v1/auth/me') {
      return route.fulfill({ status: signedIn ? 200 : 401, json: signedIn ? member : {} });
    }
    if (path === '/api/v1/trips' && req.method() === 'GET') return route.fulfill({ json: [] });
    if (path === '/api/v1/auth/logout') {
      signedIn = false;
      return route.fulfill({ status: 204 });
    }
    return route.continue();
  });
}

test('本機登入停用時保留 Google 與邀請入口', async ({ page }) => {
  await mockLocalAuth(page, false);
  await page.goto('/');
  const capability = page.waitForResponse('**/api/v1/auth/local-test');
  await page.getByRole('button', { name: '建立旅程', exact: true }).click();
  await capability;
  const dialog = page.getByRole('dialog');
  await expect(dialog.getByRole('button', { name: '使用 Google 登入' })).toBeVisible();
  await expect(dialog.getByRole('button', { name: '我有邀請碼' })).toBeVisible();
  await expect(dialog.getByRole('form', { name: '本機測試帳號登入' })).toHaveCount(0);
});

test('從建立旅程登入本機帳號後接續原操作', async ({ page }) => {
  await mockLocalAuth(page, true);
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto('/');
  await page.getByRole('button', { name: '建立旅程', exact: true }).click();
  const form = page.getByRole('form', { name: '本機測試帳號登入' });
  const username = form.getByLabel('測試帳號', { exact: true });
  const password = form.getByLabel('密碼', { exact: true });
  await expect(username).toHaveAttribute('autocomplete', 'username');
  await expect(password).toHaveAttribute('autocomplete', 'current-password');
  await expect(password).toHaveAttribute('type', 'password');
  await username.fill('traveler');
  await password.fill('incorrect');
  await form.getByRole('button', { name: '使用測試帳號登入' }).click();
  await expect(page.getByRole('alert')).toContainText('帳號或密碼錯誤');
  await password.fill('test fixture');
  await password.press('Enter');
  await expect(page.getByRole('dialog', { name: '建立旅程' }).getByLabel('旅程名稱')).toBeVisible();
  await page.getByRole('button', { name: '關閉', exact: true }).click();
  await page.reload();
  await expect(page.getByRole('heading', { name: /我的旅程/ })).toBeVisible();
  await page.getByRole('button', { name: '建立旅程', exact: true }).click();
  await expect(page.getByRole('dialog', { name: '建立旅程' })).toBeVisible();
});

test('從側欄登入顯示自己的工作空間與帳號', async ({ page }) => {
  await mockLocalAuth(page, true);
  await page.goto('/');
  await page.getByRole('button', { name: /登入你的帳號/ }).click();
  await page.getByLabel('測試帳號', { exact: true }).fill('traveler');
  await page.getByLabel('密碼', { exact: true }).fill('test fixture');
  await page.getByRole('button', { name: '使用測試帳號登入' }).click();
  await expect(page.getByRole('dialog')).toHaveCount(0);
  await expect(page.getByRole('heading', { name: /我的旅程/ })).toBeVisible();
  await page.getByRole('button', { name: '測試旅人 本機測試帳號' }).click();
  await expect(page.getByRole('dialog')).toContainText('本機測試帳號');
  await expect(page.getByLabel('顯示暱稱')).toHaveValue('測試旅人');
  await page.getByRole('button', { name: '登出' }).click();
  await expect(page.getByRole('button', { name: /登入你的帳號/ })).toBeVisible();
});
