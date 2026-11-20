import { test, expect } from '@playwright/test';
test('在桌面探索旅程、篩選、切換清單與分日查看', async ({ page }) => {
  await page.goto('/');
  await expect(page.getByRole('heading', { name: '旅程總覽', exact: true })).toBeVisible();
  await page.getByRole('button', { name: '已確認', exact: true }).click();
  await expect(page.locator('.trip-card')).toHaveCount(1);
  await page.getByRole('button', { name: '清單檢視' }).click();
  await expect(page.locator('.list-card')).toHaveCount(1);
  await page.getByRole('button', { name: '開啟多洛米蒂山間漫遊' }).click();
  await page.getByRole('button', { name: 'Day 3', exact: true }).click();
  await expect(page.getByText('塞切達山', { exact: true })).toBeVisible();
});
test('手機選單、加入表單及登入入口', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto('/');
  await page.getByRole('button', { name: '開啟選單' }).click();
  await page.getByRole('button', { name: '輸入邀請碼' }).click();
  await expect(page.getByLabel('你的暱稱')).toBeVisible();
  await page.getByRole('button', { name: '關閉', exact: true }).click();
  await page.getByRole('button', { name: '建立旅程', exact: true }).click();
  await expect(page.getByRole('button', { name: '使用 Google 登入' })).toBeVisible();
  expect(
    await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth),
  ).toBeTruthy();
});
test('兩個瀏覽器身分透過邀請加入並同步留言', async ({ browser, baseURL }) => {
  const invite = process.env.E2E_INVITE;
  test.skip(!invite, '請以 seed_demo.py 建立本次驗收專用的限時邀請。');
  const first = await browser.newContext({ baseURL }),
    second = await browser.newContext({ baseURL });
  try {
    const [a, b] = await Promise.all([first.newPage(), second.newPage()]);
    for (const [page, name] of [
      [a, '旅伴甲'],
      [b, '旅伴乙'],
    ] as const) {
      await page.goto('/?invite=' + encodeURIComponent(invite!));
      await page.getByLabel('你的暱稱').fill(name);
      await page.getByRole('dialog').getByRole('button', { name: '加入旅程', exact: true }).click();
      await expect(page.getByRole('heading', { name: '台南巷弄小旅行' })).toBeVisible();
      await page.getByRole('button', { name: '討論', exact: true }).click();
      await expect(page.getByLabel('新增留言')).toBeVisible();
    }
    const text = '一起去安平看夕陽 ' + Date.now();
    await a.getByLabel('新增留言').fill(text);
    await a.getByRole('button', { name: '送出留言' }).click();
    await expect(b.getByText(text, { exact: true })).toBeVisible({ timeout: 6500 });
    for (const page of [a, b]) {
      await page.getByRole('button', { name: '每日行程', exact: true }).click();
    }
    const activity = '安平集合 ' + Date.now();
    await a.getByRole('button', { name: '新增活動', exact: true }).click();
    await a.getByLabel('活動名稱').fill(activity);
    await a.getByRole('button', { name: '儲存活動' }).click();
    await expect(b.getByText(activity, { exact: true })).toBeVisible();
    await expect(b.getByRole('button', { name: '編輯' + activity })).toHaveCount(0);
    await a.getByRole('button', { name: '移動' + activity }).click();
    await a.getByLabel('移至日期').selectOption({ index: 1 });
    await a.getByRole('button', { name: '確認移動' }).click();
    await expect(b.getByText(activity, { exact: true })).toHaveCount(0);
    await b.getByRole('button', { name: /Day 02/ }).click();
    await expect(b.getByText(activity, { exact: true })).toBeVisible();
    await b.reload();
    await expect(b.getByRole('heading', { name: '台南巷弄小旅行' })).toBeVisible();
  } finally {
    await first.close();
    await second.close();
  }
});
