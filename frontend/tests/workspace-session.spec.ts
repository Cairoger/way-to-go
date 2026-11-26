import { expect, test, type Page } from '@playwright/test';
import { samples } from '../lib/samples';
import { hasDisposableOwner, test as ownerTest } from './disposable-owner';

test.use({ serviceWorkers: 'block' });

const owner = { id: 'owner', account_type: 'local_test', nickname: '慢速旅人', version: 1 };

for (const signedIn of [true, false]) {
  test(`首頁在確認身分後提供正確的建立與帳號入口（${signedIn ? '已登入' : '未登入'}）`, async ({
    page,
  }) => {
    let resumeSession!: () => void;
    const pending = new Promise<void>((resolve) => {
      resumeSession = resolve;
    });
    await page.route('**/api/v1/auth/me', async (route) => {
      await pending;
      await route.fulfill({
        status: signedIn ? 200 : 401,
        json: signedIn ? owner : {},
      });
    });
    await page.route('**/api/v1/trips', (route) => route.fulfill({ json: [] }));
    const requested = page.waitForRequest('**/api/v1/auth/me');
    await page.goto('/');
    await requested;
    const create = page.getByRole('button', { name: '建立旅程', exact: true });
    const profile = page.locator('button.profile');
    try {
      await expect(create).toBeDisabled();
      await expect(profile).toBeDisabled();
    } finally {
      resumeSession();
    }

    await create.click();
    const login = page.getByRole('dialog', { name: '登入 WayToGo' });
    await expect(signedIn ? page.getByRole('dialog', { name: '建立旅程' }) : login).toBeVisible();
    await page.getByRole('button', { name: '關閉', exact: true }).click();
    await profile.click();
    await expect(signedIn ? page.getByRole('dialog', { name: '帳號' }) : login).toBeVisible();
  });
}

test('已登入時可在清單載入中開啟建立表單；清單失敗保留帳號並可重試', async ({ page }) => {
  let release!: () => void;
  const pending = new Promise<void>((resolve) => {
    release = resolve;
  });
  let first = true;
  await page.route('**/api/v1/auth/me', (r) => r.fulfill({ json: owner }));
  await page.route('**/api/v1/trips', async (r) => {
    if (!first) return r.fulfill({ json: [] });
    first = false;
    await pending;
    await r.fulfill({ status: 503, json: {} });
  });

  const requested = page.waitForRequest('**/api/v1/trips');
  await page.goto('/');
  await requested;
  try {
    await page.getByRole('button', { name: '建立旅程', exact: true }).click();
    await expect(page.getByRole('dialog', { name: '建立旅程' })).toBeVisible();
  } finally {
    release();
  }
  await page.getByRole('button', { name: '關閉', exact: true }).click();
  const error = page.getByRole('alert').filter({ hasText: '無法載入旅程清單' });
  await expect(error).toBeVisible();
  await page.getByRole('button', { name: /慢速旅人/ }).click();
  await expect(page.getByRole('dialog', { name: '帳號' })).toBeVisible();
  await page.getByRole('button', { name: '關閉', exact: true }).click();
  const refreshed = page.waitForResponse('**/api/v1/trips');
  await error.getByRole('button', { name: '重新載入' }).click();
  expect((await refreshed).status()).toBe(200);
  await expect(error).toHaveCount(0);
});

test('帳號查詢失敗不採用訪客身分，重試後以原帳號繼續邀請', async ({ page }) => {
  let attempts = 0;
  await page.route('**/api/v1/auth/me', (r) =>
    ++attempts === 1 ? r.fulfill({ status: 503, json: {} }) : r.fulfill({ json: owner }),
  );
  await page.route('**/api/v1/trips', (r) => r.fulfill({ json: [] }));
  await page.goto('/?invite=example');
  const error = page.getByRole('alert').filter({ hasText: '無法確認登入狀態' });
  await expect(error).toBeVisible();
  await expect(page.getByRole('dialog')).toHaveCount(0);
  await expect(page.getByRole('button', { name: '建立旅程', exact: true })).toBeDisabled();
  await expect(page.getByRole('button', { name: '無法確認帳號' })).toBeDisabled();
  await error.getByRole('button', { name: '重新載入' }).click();
  const form = page.getByRole('dialog', { name: '加入旅程' });
  await expect(form.getByLabel('邀請碼或連結')).toHaveValue('example');
  await expect(form.getByLabel('你的暱稱')).toHaveCount(0);
});

test('重新整理時換了帳號，清單失敗也不會顯示上一個帳號的旅程', async ({ page }) => {
  const oldTrip = { ...samples[0].trip, id: 'previous-trip', title: '前帳號私人旅程' };
  const newOwner = { ...owner, id: 'next-owner', nickname: '下一位旅人' };
  let account = owner;
  await page.route('**/api/v1/auth/me', (r) => r.fulfill({ json: account }));
  await page.route('**/api/v1/trips', (r) =>
    account === owner ? r.fulfill({ json: [oldTrip] }) : r.fulfill({ status: 503, json: {} }),
  );
  await page.route('**/api/v1/invitations/accept', (r) => {
    account = newOwner;
    return r.fulfill({ json: { ...oldTrip, id: 'joined', joined_user_id: owner.id } });
  });
  await page.goto('/');
  await expect(page.getByRole('button', { name: oldTrip.title, exact: true })).toBeVisible();
  await page.getByRole('button', { name: '輸入邀請碼' }).click();
  const join = page.getByRole('dialog', { name: '加入旅程' });
  await join.getByLabel('邀請碼或連結').fill('example');
  await join.getByRole('button', { name: '加入旅程' }).click();
  await expect(page.getByRole('alert').filter({ hasText: '無法載入旅程清單' })).toBeVisible();
  await expect(page.getByRole('button', { name: /下一位旅人/ })).toBeVisible();
  await expect(page.getByText(oldTrip.title, { exact: true })).toHaveCount(0);
  await expect(page).not.toHaveURL(/[?&]trip=/);
  await expect(page.getByText('已加入旅程。', { exact: true })).toHaveCount(0);
});

ownerTest.describe('真實旅程建立', () => {
  ownerTest.skip(!hasDisposableOwner, '需要隔離服務與本機測試帳號');

  ownerTest('快速建立成功後，稍晚返回的舊清單仍會保留新旅程', async ({ page }) => {
    let release!: () => void;
    const pending = new Promise<void>((resolve) => {
      release = resolve;
    });
    let first = true;
    await page.route('**/api/v1/trips', async (route) => {
      if (route.request().method() !== 'GET' || !first) return route.continue();
      first = false;
      await pending;
      await route.fulfill({ json: [], headers: { 'X-Trip-Snapshot': 'before-save' } });
    });
    const loading = page.waitForRequest('**/api/v1/trips');
    await page.goto('/');
    await loading;
    const title = '快速建立 ' + Date.now();
    try {
      await page.getByRole('button', { name: '建立旅程', exact: true }).click();
      const form = page.getByRole('dialog', { name: '建立旅程' });
      await form.getByLabel('旅程名稱').fill(title);
      await form.getByRole('button', { name: '建立旅程', exact: true }).click();
      await expect(page.getByRole('heading', { name: title, exact: true })).toBeVisible();
    } finally {
      const stale = page.waitForResponse(
        (response) => response.headers()['x-trip-snapshot'] === 'before-save',
      );
      release();
      await (await stale).finished();
    }
    await page.getByRole('main').getByRole('button', { name: '旅程總覽', exact: true }).click();
    await expect(page.getByRole('button', { name: '開啟 ' + title })).toBeVisible();
  });
});

async function joinWhileListUnavailable(page: Page, newGuest: boolean) {
  let release!: () => void;
  const pending = new Promise<void>((resolve) => {
    release = resolve;
  });
  let submitting = false;
  await page.route('**/api/v1/trips', async (r) => {
    const beforeJoin = !submitting;
    await pending;
    await r.fulfill(beforeJoin ? { json: [] } : { status: 503, json: {} });
  });

  const initialList = !newGuest && page.waitForRequest('**/api/v1/trips');
  await page.goto('/?invite=' + encodeURIComponent(process.env.E2E_INVITE!));
  if (initialList) await initialList;
  const join = page.getByRole('dialog', { name: '加入旅程' });
  if (newGuest) await join.getByLabel('你的暱稱').fill('新加入的旅人');
  const accepted = page.waitForResponse(
    newGuest ? '**/api/v1/auth/guest' : '**/api/v1/invitations/accept',
  );
  submitting = true;
  await join.getByRole('button', { name: '加入旅程', exact: true }).click();
  const response = await accepted;
  expect(response.status()).toBe(200);
  const trip = await response.json();
  const heading = page.getByRole('heading', { name: trip.title, exact: true });
  try {
    const me = await page.request.get('/api/v1/auth/me');
    await expect(me).toBeOK();
    expect(trip.joined_user_id).toBe((await me.json()).id);
    await expect(heading).toBeVisible();
  } finally {
    release();
  }
  await expect(page.getByRole('alert').filter({ hasText: '無法載入旅程清單' })).toBeVisible();
  await expect(heading).toBeVisible();
  await expect(page.getByRole('heading', { name: '無法開啟此旅程' })).toHaveCount(0);
  await page.getByRole('main').getByRole('button', { name: '旅程總覽', exact: true }).click();
  await expect(page.getByRole('button', { name: '開啟 ' + trip.title })).toBeVisible();
}

test('接受邀請成為訪客後，旅程清單 503 仍可開啟剛加入的旅程', async ({ page }) => {
  test.skip(!process.env.E2E_INVITE, '需要隔離服務的限時邀請');
  await joinWhileListUnavailable(page, true);
});

ownerTest.describe('已登入帳號接受邀請', () => {
  ownerTest.skip(!hasDisposableOwner || !process.env.E2E_INVITE, '需要隔離服務、帳號與限時邀請');

  ownerTest('加入前的舊清單與加入後的清單失敗，都不會蓋掉已接受的旅程', async ({ page }) => {
    await joinWhileListUnavailable(page, false);
  });
});
