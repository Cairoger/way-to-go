import { expect, test, type Page } from '@playwright/test';
import { createRequire } from 'node:module';
import { resolve } from 'node:path';

declare global {
  interface Window {
    axe: typeof import('axe-core');
  }
}
const axeSource = createRequire(resolve('package.json')).resolve('axe-core/axe.min.js');

async function checkAccessibility(page: Page) {
  await page.addScriptTag({ path: axeSource });
  const failures = await page.evaluate(async () => {
    const { violations } = await window.axe.run({
      runOnly: {
        type: 'tag',
        values: ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'wcag22a', 'wcag22aa'],
      },
    });
    return violations.map((v) => ({
      rule: v.id,
      nodes: v.nodes.map((n) => ({ target: n.target, issue: n.failureSummary })),
    }));
  });
  expect(failures).toEqual([]);
}

test('旅程卡、導覽和每日行程在桌機與手機通過無障礙檢查', async ({ page }) => {
  test.skip(process.env.E2E_DISPOSABLE !== '1', '使用獨立帳號與旅程測試。');
  test.setTimeout(120_000);
  await page.goto('/');
  await page.getByRole('button', { name: /開啟.*京都秋日散策/ }).focus();
  await expect(page.getByRole('button', { name: /開啟.*京都秋日散策/ })).toBeFocused();
  for (const width of [1280, 390]) {
    await page.setViewportSize({ width, height: 860 });
    await checkAccessibility(page);
  }
  const headers = { 'X-Requested-With': 'WayToGo' };
  const signIn = await page.request.post('/api/v1/auth/local-test', {
    headers,
    data: { username: process.env.E2E_LOCAL_USERNAME, password: process.env.E2E_LOCAL_PASSWORD },
  });
  expect(signIn.ok()).toBeTruthy();
  const response = await page.request.post('/api/v1/trips', {
    headers,
    data: { title: '海邊行程無障礙驗證', day_count: 2 },
  });
  const trip = await response.json();
  expect(response.status()).toBe(201);
  const days = await (await page.request.get('/api/v1/trips/' + trip.id + '/days')).json();
  expect(
    (
      await page.request.post('/api/v1/days/' + days[0].id + '/items', {
        headers,
        data: { title: '海岸散步', item_type: 'custom', start_time: '09:00' },
      })
    ).ok(),
  ).toBeTruthy();
  await page.goto('/?trip=' + trip.id);
  await expect(page.getByText('海岸散步', { exact: true })).toBeVisible();
  for (const width of [1280, 390]) {
    await page.setViewportSize({ width, height: 860 });
    await checkAccessibility(page);
  }
});

test('儲存自己的暱稱並在重登後保留，原始建立者可見', async ({ page }) => {
  test.skip(process.env.E2E_DISPOSABLE !== '1', '使用獨立帳號與旅程測試。');
  const headers = { 'X-Requested-With': 'WayToGo' };
  const signIn = () =>
    page.request.post('/api/v1/auth/local-test', {
      headers,
      data: { username: process.env.E2E_LOCAL_USERNAME, password: process.env.E2E_LOCAL_PASSWORD },
    });
  const original = await (await signIn()).json();
  const nickname = '顯示名稱驗收';
  try {
    await page.goto('/');
    await expect(page.locator('button.profile')).toContainText(original.nickname);
    await page.locator('button.profile').click();
    await page.getByLabel('顯示暱稱').fill(nickname);
    await page.getByRole('button', { name: '儲存暱稱' }).click();
    await expect(page.getByText('暱稱已儲存。')).toBeVisible();
    await page.getByRole('button', { name: '登出', exact: true }).click();
    await expect(page.getByText('訪客模式', { exact: true })).toBeVisible();
    expect((await signIn()).ok()).toBeTruthy();
    const trip = await (
      await page.request.post('/api/v1/trips', { headers, data: { title: '旅程建立者驗收' } })
    ).json();
    await page.goto('/?trip=' + trip.id);
    await page
      .getByRole('navigation', { name: '旅程功能' })
      .getByRole('button', { name: '旅伴', exact: true })
      .click();
    await expect(page.locator('.member-list p')).toContainText(nickname);
    await expect(page.locator('button.profile')).toContainText(nickname);
  } finally {
    await signIn();
    await page.request.patch('/api/v1/auth/me', { headers, data: { nickname: original.nickname } });
  }
});
