import { expect } from '@playwright/test';
import { test } from './offline-site';

test('真實旅程離線重開、移除已排程景點與讀取封存地址', async ({ page, context, offlineSite }) => {
  test.skip(process.env.E2E_DISPOSABLE !== '1', '只能在專用的驗收資料庫建立測試旅程。');
  test.setTimeout(120000);
  const api = offlineSite.origin + '/api/v1';
  async function post(path: string, data: unknown) {
    const response = await context.request.post(api + path, {
      data,
      headers: { 'X-Requested-With': 'WayToGo' },
    });
    expect(response.ok(), path + ' returned ' + response.status()).toBeTruthy();
    return response.json();
  }
  await post('/auth/local-test', {
    username: process.env.E2E_LOCAL_USERNAME,
    password: process.env.E2E_LOCAL_PASSWORD,
  });
  const trip = await post('/trips', {
    title: '離線紐約手札',
    start_date: '2027-11-07',
    destinations: ['紐約'],
  });
  const base = '/trips/' + trip.id;
  const [day] = await (await context.request.get(api + base + '/days')).json();
  const place = await post(base + '/places', { name: '紐約展館', address: '第五大道一號' });
  await post('/days/' + day.id + '/items', {
    title: '清晨特展',
    start_time: '01:30',
    timezone: 'America/New_York',
    place_id: place.id,
    notes: '只在連線時查看的活動註記',
  });
  await page.goto(offlineSite.origin + '/?trip=' + trip.id);
  await expect(page.getByText(/重複的小時採第一次/)).toBeVisible();
  await page.getByRole('button', { name: '候選景點', exact: true }).click();
  await page.getByRole('button', { name: '紐約展館', exact: true }).click();
  await page.getByRole('button', { name: '移除原始景點' }).click();
  await page.getByRole('button', { name: '確認移除' }).click();
  await expect(page.getByRole('heading', { name: '還沒有候選景點' })).toBeVisible();
  expect(await (await context.request.get(api + base + '/places')).json()).toEqual([]);
  await page.reload();
  await expect(page.getByText(/已移除景點.*第五大道一號/)).toBeVisible();
  await page.getByText('離線閱讀', { exact: true }).click();
  await page.getByRole('button', { name: '儲存離線旅程' }).click();
  await expect(page.getByRole('button', { name: '更新離線旅程' })).toBeVisible();
  const url = page.url();
  await offlineSite.disconnect();
  await page.close();
  const reader = await context.newPage();
  await reader.goto(url);
  await expect(reader.getByText('離線唯讀')).toBeVisible();
  await expect(reader.getByRole('heading', { name: '清晨特展' })).toBeVisible();
  await expect(reader.getByText(/01:30.*America\/New_York/)).toBeVisible();
  await expect(reader.getByText('紐約展館 · 第五大道一號')).toBeVisible();
  await expect(reader.getByText(/只在連線時/)).toHaveCount(0);
  await expect(reader.getByRole('button')).toHaveCount(0);
});
