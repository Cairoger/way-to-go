import { expect, type Page } from '@playwright/test';
import { hasDisposableOwner, test } from './disposable-owner';

test.skip(!hasDisposableOwner, '需要隔離服務與本機測試帳號');

async function post(page: Page, path: string, data: object) {
  const response = await page.request.post('/api/v1' + path, {
    data,
    headers: { 'X-Requested-With': 'WayToGo' },
  });
  expect(response.ok(), await response.text()).toBeTruthy();
  return response.json();
}

test('同名景點各自保留 ID，自訂名稱與手動選項不改變連結', async ({ page }) => {
  const trip = await post(page, '/trips', { title: '同名景點票選' });
  const root = '/trips/' + trip.id;
  const name = '中央車站';
  const first = await post(page, root + '/places', { name, address: '中山路一號' });
  const second = await post(page, root + '/places', { name, address: '中山路二號' });
  await page.goto('/?trip=' + trip.id);
  await page.getByRole('button', { name: '投票', exact: true }).click();
  await page.getByRole('button', { name: '發起投票', exact: true }).click();
  const form = page.locator('form').filter({ has: page.getByLabel('投票主題') });
  await form.getByLabel('投票主題').fill('決定集合地點');
  const picker = form.getByLabel('從景點清單加入');
  await picker.selectOption({ label: '中央車站 · 中山路二號' });
  await picker.selectOption({ label: '中央車站 · 中山路一號' });
  await form.getByLabel('中央車站 · 中山路二號 的選項名稱').fill('東側分站');
  await form.getByLabel('手動輸入選項', { exact: false }).fill(name);
  const created = page.waitForResponse(
    (r) => r.request().method() === 'POST' && r.url().endsWith(root + '/polls'),
  );
  await form.getByRole('button', { name: '發起投票' }).click();
  expect((await created).status()).toBe(201);
  const list = await page.request.get('/api/v1' + root + '/polls');
  const [poll] = await list.json();
  expect(poll.rounds[0].options).toEqual([
    expect.objectContaining({ text: '東側分站', place_id: second.id }),
    expect.objectContaining({ text: '中央車站 · 中山路一號', place_id: first.id }),
    expect.objectContaining({ text: name, place_id: null }),
  ]);

  const option = poll.rounds[0].options[0];
  const path = '/polls/' + poll.id;
  const ballot = await page.request.put('/api/v1' + path + '/ballot', {
    headers: { 'X-Requested-With': 'WayToGo' },
    data: { version: poll.version, ballot_version: 0, option_ids: [option.id] },
  });
  expect(ballot.ok(), await ballot.text()).toBeTruthy();
  const closed = await post(page, path + '/close', { version: poll.version });
  const [day] = await (await page.request.get('/api/v1' + root + '/days')).json();
  const adopted = await post(page, path + '/adopt', {
    version: closed.version,
    day_id: day.id,
    option_id: option.id,
  });
  const [savedDay] = await (await page.request.get('/api/v1' + root + '/days')).json();
  expect(savedDay.items).toEqual([
    expect.objectContaining({ id: adopted.item_id, title: '東側分站', place_id: second.id }),
  ]);
});

const longName = '站'.repeat(150);
for (const { title, fields } of [
  {
    title: '同名同地址及無地址的長名稱景點可直接用預設名稱投票',
    fields: [
      { name: '文史館', address: '中山路一號' },
      { name: '文史館', address: '中山路一號' },
      { name: longName, city: '臺北市' },
      { name: longName, city: '臺北市' },
    ],
  },
  {
    title: 'Unicode 大小寫與連字等價的地址可直接用預設名稱投票',
    fields: [
      { name: '路口', address: 'Maß' },
      { name: '路口', address: 'Maẞ' },
      { name: '展館', address: 'oﬃce' },
      { name: '展館', address: 'offIce' },
      { name: '古城', address: 'ᾈΣ' },
      { name: '古城', address: 'ἀις' },
    ],
  },
]) {
  test(title, async ({ page }) => {
    const trip = await post(page, '/trips', { title });
    const root = '/trips/' + trip.id;
    const places = [];
    for (const place of fields) places.push(await post(page, root + '/places', place));

    await page.goto('/?trip=' + trip.id);
    await page.getByRole('button', { name: '投票', exact: true }).click();
    await page.getByRole('button', { name: '發起投票', exact: true }).click();
    const form = page.locator('form').filter({ has: page.getByLabel('投票主題') });
    await form.getByLabel('投票主題').fill('直接採用預設名稱');
    const picker = form.getByLabel('從景點清單加入');
    const expected = [];
    for (const place of places.reverse()) {
      const description = await picker.locator('option[value="' + place.id + '"]').innerText();
      const marker = description.match(/（#[\da-f-]+）$/)?.[0];
      expect(marker).toBeTruthy();
      await picker.selectOption({ label: description });
      const text = await form.locator('input[name="place-' + place.id + '"]').inputValue();
      expect(text.endsWith(marker!)).toBe(true);
      if (place.name === longName) expect(text.length).toBe(150);
      expected.push({ text, place_id: place.id });
    }
    expect(new Set(expected.map((p) => p.text)).size).toBe(fields.length);
    const created = page.waitForResponse(
      (r) => r.request().method() === 'POST' && r.url().endsWith(root + '/polls'),
    );
    await form.getByRole('button', { name: '發起投票' }).click();
    expect((await created).status()).toBe(201);
    const [poll] = await (await page.request.get('/api/v1' + root + '/polls')).json();
    expect(poll.rounds[0].options).toEqual(expected.map((place) => expect.objectContaining(place)));
  });
}
