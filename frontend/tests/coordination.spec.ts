import { expect, test, type Page } from '@playwright/test';
import type { Trip } from '../lib/trips';

test.use({ serviceWorkers: 'block' });

const ownerId = 'a4b80000-6e6c-4320-a594-938f06b9c001';
const memberId = 'f4b80000-6e6c-4320-a594-938f06b9c002';
const account = { id: ownerId, nickname: '小青', email: null, account_type: 'google' };
const placeNames = ['公園', '博物館', '海邊'];

async function openTrip(page: Page) {
  const trip: Trip = {
    id: 'coordination',
    title: '旅伴協調練習',
    description: '',
    destinations: [],
    start_date: null,
    end_date: null,
    version: 1,
    currency: 'TWD',
    status: 'planning',
    cover: 'tainan',
    archived: false,
    deleted_at: null,
    owner_id: ownerId,
    member_count: 2,
    day_count: 1,
    place_count: 0,
    created_at: '2026-11-01',
  };
  let entry: { start_date: string; end_date: string; status: string } | null = null;
  let comment = '';
  const ballots: Record<string, unknown> = {};
  const polls = ['rating', 'ranked'].map((mode) => ({
    id: mode,
    created_by: ownerId,
    editable_by: ownerId,
    version: 1,
    rounds: [
      {
        id: mode,
        number: 1,
        title: mode === 'rating' ? '旅伴評分' : '旅伴排序',
        kind: 'place',
        mode,
        closed: false,
        deadline: null,
        options: placeNames.map((text, i) => ({ id: 'opt' + i, text, place_id: null })),
        my_choices: [],
        my_ratings: {},
        ballot_version: 0,
        review_needed: false,
      },
    ],
  }));
  const members = [
    { ...account, role: 'owner' },
    { id: memberId, nickname: '小晴', account_type: 'guest', role: 'member' },
  ];
  await page.routeWebSocket('**/ws/trips/**', (socket) =>
    socket.send(JSON.stringify({ type: 'presence', members: [ownerId] })),
  );
  await page.route('**/api/v1/**', async (route) => {
    const req = route.request(),
      path = new URL(req.url()).pathname.replace('/api/v1', '');
    const method = req.method();
    let result: unknown = [];
    if (path === '/auth/me') result = account;
    else if (path === '/trips') result = [trip];
    else if (path === '/trips/' + trip.id) {
      if (method === 'PATCH')
        Object.assign(trip, req.postDataJSON(), { version: trip.version + 1 });
      result = trip;
    } else if (path.endsWith('/members')) result = members;
    else if (path.endsWith('/availability')) {
      if (method === 'POST') entry = req.postDataJSON();
      result =
        method === 'POST'
          ? entry
          : {
              member_count: 2,
              entries: entry ? [{ ...entry, id: 'entry', user_id: ownerId, version: 1 }] : [],
              recommendations: entry ? [{ ...entry, yes: 1, maybe: 0, no: 0, unknown: 1 }] : [],
            };
    } else if (path.endsWith('/polls')) result = polls;
    else if (path.endsWith('/ballot')) {
      ballots[path.split('/')[2]] = req.postDataJSON();
    } else if (path.endsWith('/comments')) {
      if (method === 'POST') comment = req.postDataJSON().content;
      result = comment
        ? [
            {
              id: 'one',
              author_id: ownerId,
              nickname: account.nickname,
              content: comment,
              parent_id: null,
              created_at: '2026-11-20T12:00:00Z',
              updated_at: null,
              deleted: false,
              version: 1,
            },
          ]
        : [];
    } else if (path === '/notifications')
      result = {
        preferences: { mentions: true, push: false, version: 0, public_key: null },
        items: [],
      };
    return route.fulfill({ json: result });
  });
  await page.goto('/?trip=' + trip.id);
  await expect(page.getByRole('heading', { name: trip.title })).toBeVisible();
  return { trip, ballots, postedComment: () => comment };
}

test('旅伴標記單日並套用至旅程日期', async ({ page }) => {
  const { trip } = await openTrip(page);
  await page.getByRole('button', { name: '日期協調', exact: true }).click();
  await page.getByRole('button', { name: '標記我的日期' }).click();
  await page.getByLabel('開始日期', { exact: true }).fill('2027-05-04');
  await page.getByRole('button', { name: '儲存標記' }).click();
  await expect(page.getByText('1 可以 · 0 可能 · 0 不行 · 1 未填')).toBeVisible();
  await page.getByRole('button', { name: '選用區間' }).click();
  await expect(page.getByLabel('旅程開始日')).toHaveValue('2027-05-04');
  await page.getByRole('button', { name: '確認套用日期' }).click();
  await expect.poll(() => trip.start_date).toBe('2027-05-04');
});

test('評分、排序及提及旅伴的輸入與呈現', async ({ page }) => {
  const { ballots, postedComment } = await openTrip(page);
  await page.getByRole('button', { name: '投票', exact: true }).click();
  const rating = page
    .locator('article')
    .filter({ has: page.getByRole('heading', { name: '旅伴評分' }) });
  for (let i = 0; i < placeNames.length; i++)
    await rating
      .getByRole('combobox', { name: placeNames[i], exact: true })
      .selectOption(String(i + 2));
  await rating.getByRole('button', { name: '送出選票' }).click();
  await expect
    .poll(() => ballots.rating)
    .toEqual({ version: 1, ballot_version: 0, ratings: { opt0: 2, opt1: 3, opt2: 4 } });
  const ranked = page
    .locator('article')
    .filter({ has: page.getByRole('heading', { name: '旅伴排序' }) });
  await ranked.getByRole('button', { name: '將博物館往前移' }).click();
  await ranked.getByRole('button', { name: '送出選票' }).click();
  await expect
    .poll(() => ballots.ranked)
    .toEqual({ version: 1, ballot_version: 0, option_ids: ['opt1', 'opt0', 'opt2'] });
  await page.getByRole('button', { name: '討論', exact: true }).click();
  await page.getByLabel('提及旅伴').selectOption(memberId);
  await page.getByRole('button', { name: '送出留言' }).click();
  await expect.poll(postedComment).toBe('@[小晴](' + memberId + ')');
  await expect(page.getByText('@小晴', { exact: true })).toBeVisible();
});
