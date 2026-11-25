import { expect, type BrowserContext } from '@playwright/test';
import { test, type OfflineSite } from './offline-site';

const traveler = { id: 'saved-user', nickname: '離線測試旅伴', account_type: 'local_test' };
const trip = {
  id: 'saved-trip',
  owner_id: traveler.id,
  title: '紐約散步',
  description: '不儲存描述',
  start_date: '2027-11-07',
  end_date: '2027-11-07',
  destinations: ['紐約'],
  currency: 'TWD',
  status: 'planning',
  cover: 'tainan',
  archived: false,
  deleted_at: null,
  version: 1,
  member_count: 1,
  day_count: 1,
  place_count: 1,
  created_at: '2026-01-01T00:00:00Z',
};
const place = {
  id: 'museum',
  name: '市立展館',
  address: '第五大道一號',
  city: '紐約',
  country: '',
  tags: [],
  category: 'place',
  status: 'want',
  editable_by: traveler.id,
  created_by: traveler.id,
  candidate: true,
  candidate_id: 'candidate',
  latitude: null,
  longitude: null,
  version: 1,
  notes: '秘密註記',
};
const item = {
  id: 'visit',
  title: '清晨參觀',
  item_type: 'place',
  day_id: 'one',
  place_id: place.id,
  start_time: '01:30',
  local_timezone: 'America/New_York',
  start_instant: '2027-11-07T05:30:00Z',
  clock_note: '當地時鐘回撥，重複的小時採第一次出現的時間。',
  notes: '私人訂位代碼',
  editable_by: traveler.id,
  version: 1,
};

async function fixture(context: BrowserContext, site: OfflineSite) {
  let account: typeof traveler | null = traveler;
  let removed = false;
  await context.routeWebSocket('**/ws/trips/**', (ws) =>
    ws.send(JSON.stringify({ type: 'presence', members: [traveler.id] })),
  );
  site.handleApi(async (req, res) => {
    const path = new URL(req.url!, site.origin).pathname.slice('/api/v1'.length);
    if (path === '/auth/logout') account = null;
    if (path === '/places/museum' && req.method === 'DELETE') {
      const chunks = [];
      for await (const chunk of req) chunks.push(chunk);
      expect(JSON.parse(Buffer.concat(chunks).toString())).toEqual({
        version: 1,
        lease_id: 'lease',
      });
      removed = true;
    }
    const routes: Record<string, unknown> = {
      '/auth/me': account,
      '/auth/logout': {},
      '/trips': account ? [trip] : [],
      '/trips/saved-trip': trip,
      '/trips/saved-trip/members': [{ ...traveler, role: 'owner' }],
      '/trips/saved-trip/places': removed ? [] : [place],
      '/trips/saved-trip/days': [
        {
          id: 'one',
          day_number: 1,
          date: '2027-11-07',
          title: '',
          timezone: 'America/New_York',
          items: [removed ? { ...item, archived_place: place } : item],
        },
      ],
      '/edit-leases': { id: 'lease', version: 1 },
      '/places/museum': { deleted: true, version: 2 },
      '/notifications': { items: [], preferences: { mentions: false, push: false, version: 1 } },
    };
    res.writeHead(path === '/auth/me' && !account ? 401 : 200, {
      'Content-Type': 'application/json',
      'Cache-Control': 'no-store',
    });
    res.end(JSON.stringify(routes[path] ?? []));
  });
  return {
    switchAccount: () => {
      account = { ...traveler, id: 'other', nickname: '其他旅伴' };
    },
  };
}

test('自行儲存之後，關閉原頁、開新頁可離線唯讀；登出清除所有分頁的副本', async ({
  context,
  page,
  offlineSite,
}) => {
  await fixture(context, offlineSite);
  await page.goto(offlineSite.origin + '/?trip=saved-trip');
  await expect(page.getByText(item.clock_note)).toBeVisible();
  expect(
    await page.evaluate(() =>
      Object.keys(localStorage).filter((k) => k.startsWith('waytogo.offline.trip.')),
    ),
  ).toEqual([]);
  await page.getByText('離線閱讀', { exact: true }).click();
  await page.getByRole('button', { name: '儲存離線旅程' }).click();
  await expect(page.getByRole('button', { name: '更新離線旅程' })).toBeVisible();
  const url = page.url();
  await offlineSite.disconnect();
  await page.close();
  const reader = await context.newPage();
  await reader.goto(url);
  await expect(reader.getByText('離線唯讀')).toBeVisible();
  await expect(reader.getByRole('heading', { name: '紐約散步' })).toBeVisible();
  await expect(reader.getByText('清晨參觀')).toBeVisible();
  await expect(reader.getByText(/01:30.*America\/New_York/)).toBeVisible();
  await expect(reader.getByText(/第五大道一號/).first()).toBeVisible();
  await expect(reader.getByRole('button')).toHaveCount(0);
  const stored = await reader.evaluate(() => JSON.stringify(localStorage));
  for (const secret of ['私人訂位代碼', '秘密註記', '不儲存描述'])
    expect(stored).not.toContain(secret);
  await offlineSite.reconnect();
  const online = await context.newPage();
  await online.goto(offlineSite.origin);
  await online.getByRole('button', { name: /離線測試旅伴.*本機測試帳號/ }).click();
  await online.getByRole('button', { name: '登出', exact: true }).click();
  await expect(reader.getByRole('heading', { name: '此旅程尚未儲存在裝置上' })).toBeVisible();
  await offlineSite.disconnect();
  const cleared = await context.newPage();
  await cleared.goto(url);
  await expect(cleared.getByRole('heading', { name: '此旅程尚未儲存在裝置上' })).toBeVisible();
  await expect(cleared.getByText('清晨參觀')).toHaveCount(0);
});

test('切換帳號後移除上一個帳號的離線旅程', async ({ context, page, offlineSite }) => {
  const session = await fixture(context, offlineSite);
  await page.goto(offlineSite.origin + '/?trip=saved-trip');
  await page.getByText('離線閱讀', { exact: true }).click();
  await page.getByRole('button', { name: '儲存離線旅程' }).click();
  await expect(page.getByRole('button', { name: '更新離線旅程' })).toBeVisible();
  session.switchAccount();
  await page.goto(offlineSite.origin);
  await expect(page.getByRole('button', { name: /其他旅伴.*本機測試帳號/ })).toBeVisible();
  expect(
    await page.evaluate(() =>
      Object.keys(localStorage).filter((k) => k.startsWith('waytogo.offline.trip.')),
    ),
  ).toEqual([]);
});

test('從景點詳情移除原始景點；地圖顯示付費提示與免費導航', async ({
  context,
  page,
  offlineSite,
}) => {
  await fixture(context, offlineSite);
  await page.goto(offlineSite.origin + '/?trip=saved-trip');
  await page.getByRole('button', { name: '旅程地圖' }).click();
  await expect(page.getByText(/付費功能開發中/)).toBeVisible();
  await expect(page.getByRole('link', { name: '導航至市立展館' })).toHaveAttribute(
    'href',
    /google.com\/maps\/dir/,
  );
  await page.getByRole('button', { name: '候選景點', exact: true }).click();
  await page.getByRole('button', { name: '市立展館', exact: true }).click();
  await page.getByRole('button', { name: '移除原始景點' }).click();
  await expect(page.getByText(/已排入的活動會保留/)).toBeVisible();
  await page.getByRole('button', { name: '確認移除' }).click();
  await expect(page.getByRole('heading', { name: '還沒有候選景點' })).toBeVisible();
  await page.reload();
  await expect(page.getByText(/已移除景點.*第五大道一號/)).toBeVisible();
});
