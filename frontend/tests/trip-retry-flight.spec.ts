import { expect, type Page } from '@playwright/test';
import { hasDisposableOwner, test } from './disposable-owner';

test.skip(!hasDisposableOwner, '需要隔離服務與本機測試帳號');
test.use({ serviceWorkers: 'block' });

const headers = { 'X-Requested-With': 'WayToGo' };

async function loseFirstCreateResponse(
  page: Page,
  title: string,
  loss: 'disconnect' | 'incomplete',
) {
  const keys: string[] = [];
  await page.route('**/api/v1/trips', async (route) => {
    if (route.request().method() !== 'POST') return route.continue();
    keys.push(route.request().headers()['idempotency-key']);
    if (keys.length !== 1) return route.continue();
    const committed = await route.fetch();
    expect(committed.status()).toBe(201);
    if (loss === 'disconnect') await route.abort('connectionfailed');
    else await route.fulfill({ response: committed, body: '{' });
  });
  await page.goto('/');
  await page.getByRole('button', { name: '建立旅程', exact: true }).click();
  const form = page.getByRole('dialog', { name: '建立旅程' });
  await form.getByLabel('旅程名稱').fill(title);
  await form.getByRole('button', { name: '建立旅程', exact: true }).click();
  await expect(form.getByRole('alert')).toContainText('尚未確認');
  return { form, keys };
}

test('回應遺失後重送同一份旅程只建立一筆', async ({ page }) => {
  const title = '重送 ' + Date.now();
  const { form, keys } = await loseFirstCreateResponse(page, title, 'disconnect');
  await form.getByLabel('旅程名稱').fill('  ' + title);
  await form.getByRole('button', { name: '建立旅程', exact: true }).click();
  await expect(page.getByRole('heading', { name: title, exact: true })).toBeVisible();
  const trips = await (await page.request.get('/api/v1/trips')).json();
  expect(trips.filter((trip: { title: string }) => trip.title === title)).toHaveLength(1);
  expect(keys[0]).toBeTruthy();
  expect(keys).toEqual([keys[0], keys[0]]);
});

test('回應遺失後改草稿，需明確確認才另外建立', async ({ page }) => {
  const original = '原草稿 ' + Date.now();
  const changed = original + ' 更新版';
  const { form, keys } = await loseFirstCreateResponse(page, original, 'incomplete');
  await form.getByLabel('旅程名稱').fill(changed);
  const submit = form.getByRole('button', { name: '建立旅程', exact: true });
  page.once('dialog', (d) => d.dismiss());
  await submit.click();
  await expect(form).toBeVisible();
  expect(keys).toHaveLength(1);
  page.once('dialog', (d) => d.accept());
  await submit.click();
  await expect(page.getByRole('heading', { name: changed, exact: true })).toBeVisible();
  const trips = await (await page.request.get('/api/v1/trips')).json();
  for (const title of [original, changed]) {
    expect(trips.filter((trip: { title: string }) => trip.title === title)).toHaveLength(1);
  }
  expect(keys).toHaveLength(2);
  expect(keys[1]).toBeTruthy();
  expect(keys[1]).not.toBe(keys[0]);
});

test('兩位既有旅客離團後，航班建立者仍可辨識並單獨編輯', async ({ page, browser, baseURL }) => {
  const guests = [await browser.newContext({ baseURL }), await browser.newContext({ baseURL })];
  try {
    const post = async (path: string, data: object) => {
      const response = await page.request.post('/api/v1' + path, { headers, data });
      await expect(response).toBeOK();
      return response.json();
    };
    const trip = await post('/trips', { title: '航班旅客 ' + Date.now() });
    const root = '/trips/' + trip.id;
    const invite = await post(root + '/invitations', {});
    const ids: string[] = [];
    for (const guest of guests) {
      const joined = await guest.request.post('/api/v1/auth/guest', {
        headers,
        data: { code: invite.code, nickname: '小妤' },
      });
      await expect(joined).toBeOK();
      ids.push((await (await guest.request.get('/api/v1/auth/me')).json()).id);
    }

    await page.goto('/?trip=' + trip.id);
    await page.getByRole('button', { name: '討論', exact: true }).click();
    const rosterLabels: string[] = [];
    for (const id of ids) {
      const entry = page.getByLabel('提及旅伴').locator('option[value="' + id + '"]');
      await expect(entry).toHaveText('小妤 · ' + id.slice(0, 8));
      rosterLabels.push((await entry.textContent())!);
    }
    const renameSecond = async (nickname: string, version: number) => {
      await expect(
        await guests[1].request.patch('/api/v1/auth/me', { headers, data: { nickname, version } }),
      ).toBeOK();
    };
    await renameSecond('小安', 1);
    const first = { user_id: ids[0], seat: '', baggage: '15kg' };
    const second = { user_id: ids[1], seat: '', baggage: '15kg' };
    const leg = {
      number: 'QA07',
      origin: 'TPE',
      destination: 'NRT',
      departure: '2027-03-18T08:00:00+08:00',
      arrival: '2027-03-18T12:00:00+09:00',
      passengers: [first, second],
    };
    for (const title of ['去程', '回程']) {
      await post(root + '/bookings', { kind: 'flight', title, segments: [leg] });
    }
    for (const [index, guest] of guests.entries()) {
      await expect(
        await guest.request.delete('/api/v1' + root + '/members/' + ids[index], { headers }),
      ).toBeOK();
    }

    const dialog = page.getByRole('dialog', { name: '編輯航班' });
    const row = (name: string) => dialog.getByRole('group', { name, exact: true });
    const edit = (title: string) =>
      page
        .getByRole('article')
        .filter({ has: page.getByRole('heading', { name: title, exact: true }) })
        .getByRole('button', { name: '編輯', exact: true });
    const openEditor = async (title: string) => {
      await page.goto('/?trip=' + trip.id);
      await page.getByRole('button', { name: '交通與住宿', exact: true }).click();
      await edit(title).click();
    };
    const getPassengers = async (title: string) => {
      const response = await page.request.get('/api/v1' + root + '/bookings');
      await expect(response).toBeOK();
      return (await response.json()).find((booking: { title: string }) => booking.title === title)
        .segments[0].passengers;
    };
    const save = async () => {
      await dialog.getByRole('button', { name: '儲存預訂' }).click();
      await expect(dialog).toBeHidden();
    };

    await test.step('舊預訂沒有暱稱且 ID 前八碼相同時，可用延長的短 ID 區分', async () => {
      const bookingsUrl = '**/api/v1' + root + '/bookings';
      await page.route(bookingsUrl, async (route) => {
        const response = await route.fetch();
        const bookings = await response.json();
        const old = bookings.find((booking: { title: string }) => booking.title === '去程');
        delete old.departed_passenger_names;
        old.segments[0].passengers = [
          { ...first, user_id: '1234abcd-0001-4000-8000-000000000000' },
          { ...second, user_id: '1234abcd-0002-4000-8000-000000000000' },
        ];
        await route.fulfill({ response, json: bookings });
      });
      await openEditor('去程');
      for (const suffix of ['1234abcd-0001', '1234abcd-0002']) {
        const label = '已退出的旅客 · ' + suffix;
        await expect(row(label).getByRole('checkbox', { name: label, exact: true })).toBeChecked();
      }
      await page.unroute(bookingsUrl);
    });

    const changeSecond = async (title: string, labels: string[]) => {
      await openEditor(title);
      for (const label of labels) {
        await expect(row(label).getByRole('checkbox', { name: label, exact: true })).toBeChecked();
        await expect(row(label).getByLabel('座位', { exact: true })).toHaveValue('');
        await expect(row(label).getByLabel('行李', { exact: true })).toHaveValue('15kg');
      }
      const target = row(labels[1]);
      await target.getByLabel('座位', { exact: true }).fill('21C');
      await target.getByLabel('行李', { exact: true }).fill('23kg');
      await save();
      expect(await getPassengers(title)).toEqual([
        first,
        { ...second, seat: '21C', baggage: '23kg' },
      ]);
    };
    await test.step('無座位且行李相同，仍可依暱稱修改單一旅客', async () => {
      await changeSecond('去程', ['小妤（已退出）', '小安（已退出）']);
    });
    await test.step('兩位同名、無座且行李相同，依旅伴清單的 ID 只更新指定旅客', async () => {
      await renameSecond('小妤', 2);
      const labels = rosterLabels.map((label) => label + '（已退出）');
      await changeSecond('回程', labels);
      await edit('回程').click();
      const target = row(labels[1]);
      const selected = target.getByRole('checkbox');
      await selected.uncheck();
      await selected.check();
      await expect(target.getByLabel('座位', { exact: true })).toHaveValue('21C');
      await selected.uncheck();
      await save();
      expect(await getPassengers('回程')).toEqual([first]);
      await edit('回程').click();
      await expect(row('小妤（已退出）').getByRole('checkbox')).toBeChecked();
      await expect(selected).toHaveCount(0);
    });
  } finally {
    await Promise.all(guests.map((guest) => guest.close()));
  }
});
