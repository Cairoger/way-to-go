import { expect, test, type APIResponse, type BrowserContext } from '@playwright/test';
import { writeFile } from 'node:fs/promises';

declare global {
  interface Window {
    closeTripSocket(): void;
  }
}

const headers = { 'X-Requested-With': 'WayToGo' };
async function json(response: APIResponse) {
  expect(response.ok(), 'API status ' + response.status()).toBeTruthy();
  return response.json();
}
async function join(contexts: BrowserContext[]) {
  const owner = contexts[0].request;
  await json(
    await owner.post('/api/v1/auth/local-test', {
      headers,
      data: { username: process.env.E2E_LOCAL_USERNAME, password: process.env.E2E_LOCAL_PASSWORD },
    }),
  );
  const trip = await json(
    await owner.post('/api/v1/trips', { headers, data: { title: '同步量測' } }),
  );
  const path = '/api/v1/trips/' + trip.id;
  const { code } = await json(await owner.post(path + '/invitations', { headers, data: {} }));
  for (const [i, guest] of contexts.slice(1).entries()) {
    await json(
      await guest.request.post('/api/v1/auth/guest', {
        headers,
        data: { code, nickname: '同步旅伴 ' + i },
      }),
    );
  }
  const pages = await Promise.all(contexts.map((c) => c.newPage()));
  for (const p of pages) {
    await p.goto('/?trip=' + trip.id);
    await p.getByRole('button', { name: '討論', exact: true }).click();
    await expect(p.getByLabel('新增留言')).toBeVisible();
  }
  await Promise.all(
    pages.map((p) =>
      expect(p.getByText(contexts.length + ' 人在線', { exact: false })).toBeVisible(),
    ),
  );
  return { pages, path };
}

test.beforeEach(() => {
  test.skip(process.env.E2E_DISPOSABLE !== '1', '使用隔離服務及測試帳號');
  test.setTimeout(150000);
});

test('五名旅伴同時留言，連續 20 次編輯自動顯示在其他四頁', async ({ browser, baseURL }, info) => {
  const contexts = await Promise.all(
    Array.from({ length: 5 }, () => browser.newContext({ baseURL })),
  );
  try {
    const { pages, path } = await join(contexts);
    const posts = await Promise.all(
      contexts.map(async (c, i) =>
        json(
          await c.request.post(path + '/comments', { headers, data: { content: '同時建立 ' + i } }),
        ),
      ),
    );
    const committed = await json(await contexts[0].request.get(path + '/comments'));
    expect(new Set(committed.map((row: { id: string }) => row.id))).toEqual(
      new Set(posts.map((p) => p.id)),
    );
    expect(committed).toHaveLength(5);
    let message = posts[0];
    const measurements: { edit: number; observer: number; ms: number }[] = [];
    for (let edit = 1; edit <= 20; edit++) {
      const content = '同步編輯第 ' + edit + ' 次';
      const started = performance.now();
      const observers = pages.slice(1).map(async (p, i) => {
        await p.getByText(content, { exact: true }).waitFor({ state: 'visible', timeout: 10000 });
        return { edit, observer: i + 2, ms: Math.round(performance.now() - started) };
      });
      const [updated, observed] = await Promise.all([
        contexts[0].request
          .patch('/api/v1/comments/' + message.id, {
            headers,
            data: { content, version: message.version },
          })
          .then(json),
        Promise.all(observers),
      ]);
      message = updated;
      measurements.push(...observed);
    }
    const sorted = measurements.map((m) => m.ms).sort((a, b) => a - b);
    const report = {
      posts: committed.length,
      samples: sorted.length,
      timeouts: 80 - sorted.length,
      p95Ms: sorted[Math.ceil(sorted.length * 0.95) - 1],
      maxMs: sorted.at(-1),
      measurements,
    };
    const body = JSON.stringify(report, null, 2);
    await info.attach('edit-to-visible.json', { body, contentType: 'application/json' });
    if (process.env.E2E_METRICS_PATH) await writeFile(process.env.E2E_METRICS_PATH, body);
    console.log(
      '5 browser pages, posts=' +
        report.posts +
        ', n=' +
        report.samples +
        ', timeouts=' +
        report.timeouts +
        ', P95=' +
        report.p95Ms +
        ' ms, max=' +
        report.maxMs +
        ' ms',
    );
    expect(report.samples).toBe(80);
    expect(report.p95Ms).toBeLessThan(2000);
  } finally {
    await Promise.all(contexts.map((c) => c.close()));
  }
});

test('雙人討論斷線後自動重連並補讀遺漏留言', async ({ browser, baseURL }) => {
  const contexts = await Promise.all([
    browser.newContext({ baseURL }),
    browser.newContext({ baseURL }),
  ]);
  try {
    const guest = contexts[1];
    // Close the actual trip socket, leaving both page instances and the API running.
    await guest.addInitScript(() => {
      const Native = window.WebSocket;
      window.WebSocket = class extends Native {
        constructor(url: string | URL, protocols?: string | string[]) {
          super(url, protocols);
          if (url.toString().includes('/ws/trips/')) {
            window.closeTripSocket = () => this.close(4000);
          }
        }
      };
    });
    const { pages, path } = await join(contexts);
    await pages[1].evaluate(() => window.closeTripSocket());
    await expect(pages[1].getByText('重新連線中', { exact: false })).toBeVisible();
    await json(
      await contexts[0].request.post(path + '/comments', {
        headers,
        data: { content: '斷線時新增' },
      }),
    );
    await expect(pages[1].getByText('斷線時新增', { exact: true })).toBeVisible();
    await Promise.all(
      pages.map((p) => expect(p.getByText('2 人在線', { exact: false })).toBeVisible()),
    );
  } finally {
    await Promise.all(contexts.map((c) => c.close()));
  }
});
