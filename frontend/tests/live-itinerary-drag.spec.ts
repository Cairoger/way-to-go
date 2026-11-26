import { expect, type APIRequestContext, type Locator, type Page } from '@playwright/test';
import { hasDisposableOwner, test } from './disposable-owner';

test.skip(!hasDisposableOwner, '需要隔離服務與本機測試帳號');

async function itinerary(api: APIRequestContext) {
  async function post(path: string, data: object) {
    const response = await api.post('/api/v1' + path, {
      headers: { 'X-Requested-With': 'WayToGo' },
      data,
    });
    expect(response.ok(), await response.text()).toBeTruthy();
    return response.json();
  }
  const trip = await post('/trips', { title: '拖曳行程' });
  const daysPath = '/trips/' + trip.id + '/days';
  const [first] = await (await api.get('/api/v1' + daysPath)).json();
  const second = await post(daysPath, {});
  await post('/days/' + first.id + '/items', { title: '車站集合' });
  await post('/days/' + second.id + '/items', { title: '午餐' });
  return trip.id as string;
}

async function openItinerary(page: Page, trip: string) {
  await page.goto('/?trip=' + trip);
  await page.getByRole('button', { name: '每日行程', exact: true }).click();
  await expect(page.locator('.wp-timeline h4')).toHaveText(['車站集合']);
}

test('滑鼠跨日拖曳及同日排序在重載後保留', async ({ page }) => {
  const trip = await itinerary(page.request);
  await openItinerary(page, trip);
  const rows = page.locator('.wp-timeline li');
  const meeting = rows.filter({ hasText: '車站集合' });
  const dayTwo = page.getByRole('button', { name: /Day 02/ });
  await meeting.dragTo(dayTwo);
  await expect(page.locator('.wp-timeline h4')).toHaveText(['午餐', '車站集合']);
  const lunch = rows.filter({ hasText: '午餐' });
  await meeting.dragTo(lunch);
  await expect(page.locator('.wp-timeline h4')).toHaveText(['車站集合', '午餐']);

  const writes: string[] = [];
  page.on('request', (request) => {
    if (request.method() === 'POST' && /\/(edit-leases|move)$/.test(request.url()))
      writes.push(request.url());
  });
  await meeting.dragTo(lunch);
  await page.reload();
  expect(writes).toEqual([]);
  await dayTwo.click();
  await expect(page.locator('.wp-timeline h4')).toHaveText(['車站集合', '午餐']);
});

test('手機可長按活動跨日、使用把手排序與取消拖曳', async ({
  browser,
  browserName,
  baseURL,
  ownerCookies,
}) => {
  test.skip(browserName !== 'chromium', '使用 Chromium 的原生觸控事件注入');
  const context = await browser.newContext({
    baseURL,
    storageState: { cookies: ownerCookies, origins: [] },
    viewport: { width: 390, height: 844 },
    hasTouch: true,
    isMobile: true,
  });
  try {
    const page = await context.newPage();
    const trip = await itinerary(page.request);
    await openItinerary(page, trip);
    const session = await context.newCDPSession(page);
    async function point(element: Locator) {
      const bounds = await element.boundingBox();
      expect(bounds).not.toBeNull();
      return { x: bounds!.x + bounds!.width / 2, y: bounds!.y + bounds!.height / 2 };
    }
    async function gesture(source: Locator, target: Locator, hold: boolean, cancel = false) {
      const initial = await point(source),
        destination = await point(target);
      await page.evaluate(
        (y) => window.scrollBy(0, y - innerHeight / 2),
        (initial.y + destination.y) / 2,
      );
      const a = await point(source),
        b = await point(target);
      for (const [element, p] of [
        [source, a],
        [target, b],
      ] as const) {
        expect(
          await element.evaluate((el, p) => el.contains(document.elementFromPoint(p.x, p.y)), p),
        ).toBe(true);
      }
      await session.send('Input.dispatchTouchEvent', { type: 'touchStart', touchPoints: [a] });
      if (hold) await new Promise((resolve) => setTimeout(resolve, 650));
      for (let step = 1; step <= 6; step++) {
        await session.send('Input.dispatchTouchEvent', {
          type: 'touchMove',
          touchPoints: [
            {
              x: a.x + ((b.x - a.x) * step) / 6,
              y: a.y + ((b.y - a.y) * step) / 6,
            },
          ],
        });
      }
      await session.send('Input.dispatchTouchEvent', {
        type: cancel ? 'touchCancel' : 'touchEnd',
        touchPoints: [],
      });
    }
    const dayTwo = page.getByRole('button', { name: /Day 02/ });
    const title = page.getByRole('heading', { name: '車站集合', exact: true });
    const grip = page.getByRole('img', { name: '拖曳排序：車站集合' });
    await gesture(grip, dayTwo, false, true);
    await expect(dayTwo).toHaveAttribute('aria-pressed', 'false');
    await expect(page.locator('.wp-timeline h4')).toHaveText(['車站集合']);
    // A regular swipe on the activity must still scroll instead of changing its date.
    await gesture(title, dayTwo, false);
    await expect(dayTwo).toHaveAttribute('aria-pressed', 'false');
    await expect(page.locator('.wp-timeline h4')).toHaveText(['車站集合']);
    await gesture(title, dayTwo, true);
    await expect(page.locator('.wp-timeline h4')).toHaveText(['午餐', '車站集合']);
    await gesture(grip, page.getByRole('heading', { name: '午餐', exact: true }), false);
    await expect(page.locator('.wp-timeline h4')).toHaveText(['車站集合', '午餐']);
    await page.reload();
    await dayTwo.click();
    await expect(page.locator('.wp-timeline h4')).toHaveText(['車站集合', '午餐']);
  } finally {
    await context.close();
  }
});
