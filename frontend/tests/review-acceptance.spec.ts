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

test('雙分頁暱稱衝突保留輸入，重讀後可儲存並在重登和旅伴名單看到新值', async ({
  page,
  browser,
  baseURL,
}) => {
  test.skip(process.env.E2E_DISPOSABLE !== '1', '使用獨立帳號與旅程測試。');
  const headers = { 'X-Requested-With': 'WayToGo' };
  const signIn = () =>
    page.request.post('/api/v1/auth/local-test', {
      headers,
      data: { username: process.env.E2E_LOCAL_USERNAME, password: process.env.E2E_LOCAL_PASSWORD },
    });
  const original = await (await signIn()).json();
  const otherTab = await page.context().newPage();
  const guest = await browser.newContext({ baseURL });
  const firstName = '顯示名稱甲';
  const secondName = '顯示名稱乙';
  async function save(tab: Page) {
    const [response] = await Promise.all([
      tab.waitForResponse((r) => r.url().endsWith('/auth/me') && r.request().method() === 'PATCH'),
      tab.getByRole('button', { name: '儲存暱稱' }).click(),
    ]);
    return response;
  }
  try {
    const trip = await (
      await page.request.post('/api/v1/trips', { headers, data: { title: '旅程建立者驗收' } })
    ).json();
    const invite = await (
      await page.request.post(`/api/v1/trips/${trip.id}/invitations`, { headers, data: {} })
    ).json();
    expect(
      (
        await guest.request.post('/api/v1/auth/guest', {
          headers,
          data: { code: invite.code, nickname: '獨立查看的旅伴' },
        })
      ).ok(),
    ).toBeTruthy();
    for (const tab of [page, otherTab]) {
      await tab.goto('/');
      await expect(tab.locator('button.profile')).toContainText(original.nickname);
      await tab.locator('button.profile').click();
      await expect(tab.getByLabel('顯示暱稱')).toHaveValue(original.nickname);
    }
    await page.getByLabel('顯示暱稱').fill(firstName);
    await otherTab.getByLabel('顯示暱稱').fill(secondName);
    const first = await save(page);
    expect(first.status()).toBe(200);
    expect(await first.json()).toMatchObject({
      nickname: firstName,
      version: original.version + 1,
    });
    await expect(page.getByText('暱稱已儲存。')).toBeVisible();
    const stale = await save(otherTab);
    expect(stale.status()).toBe(409);
    expect(await stale.json()).toMatchObject({ code: 'VERSION_CONFLICT' });
    expect(await (await page.request.get('/api/v1/auth/me')).json()).toMatchObject({
      nickname: firstName,
      version: original.version + 1,
    });
    await expect(otherTab.getByLabel('顯示暱稱')).toHaveValue(secondName);
    await expect(otherTab.getByRole('button', { name: '儲存暱稱' })).toBeDisabled();
    const observer = await guest.newPage();
    await observer.goto('/?trip=' + trip.id);
    await observer
      .getByRole('navigation', { name: '旅程功能' })
      .getByRole('button', { name: '旅伴', exact: true })
      .click();
    await expect(observer.locator('.member-row b', { hasText: firstName })).toBeVisible();
    await expect(observer.locator('.member-list p')).toContainText(firstName);
    await otherTab.getByRole('button', { name: '重新讀取最新暱稱' }).click();
    await expect(otherTab.getByRole('status')).toContainText(firstName);
    await expect(otherTab.getByLabel('顯示暱稱')).toHaveValue(secondName);
    const retry = await save(otherTab);
    expect(retry.status()).toBe(200);
    expect(await retry.json()).toMatchObject({
      nickname: secondName,
      version: original.version + 2,
    });
    await expect(observer.locator('.member-row b', { hasText: secondName })).toBeVisible();
    await page.getByRole('button', { name: '登出', exact: true }).click();
    await expect(page.getByText('訪客模式', { exact: true })).toBeVisible();
    const signedIn = await signIn();
    expect(signedIn.ok()).toBeTruthy();
    expect(await signedIn.json()).toMatchObject({
      nickname: secondName,
      version: original.version + 2,
    });
    await page.goto('/?trip=' + trip.id);
    await page
      .getByRole('navigation', { name: '旅程功能' })
      .getByRole('button', { name: '旅伴', exact: true })
      .click();
    await expect(page.locator('.member-list p')).toContainText(secondName);
    await expect(page.locator('button.profile')).toContainText(secondName);
  } finally {
    await guest.close();
    const latest = await (await signIn()).json();
    expect(
      (
        await page.request.patch('/api/v1/auth/me', {
          headers,
          data: { nickname: original.nickname, version: latest.version },
        })
      ).ok(),
    ).toBeTruthy();
  }
});
