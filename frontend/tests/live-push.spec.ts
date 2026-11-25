import { chromium, expect, test, type BrowserContext } from '@playwright/test';
import { writeFile } from 'node:fs/promises';
import { execFile } from 'node:child_process';
import { resolve } from 'node:path';
import { promisify } from 'node:util';

const headers = { 'X-Requested-With': 'WayToGo' };
test.beforeEach(({ browserName }) => {
  test.skip(
    browserName !== 'chromium',
    '背景通知探測使用 Chromium 一般設定檔及 DevTools Protocol。',
  );
  test.skip(
    process.env.E2E_DISPOSABLE !== '1' || process.env.E2E_PUSH_PROBE !== '1',
    'Run against a disposable instance using --production --push',
  );
  test.setTimeout(120000);
});

async function setup(owner: BrowserContext, guest: BrowserContext) {
  const login = await owner.request.post('/api/v1/auth/local-test', {
    headers,
    data: { username: process.env.E2E_LOCAL_USERNAME, password: process.env.E2E_LOCAL_PASSWORD },
  });
  expect(login.ok()).toBeTruthy();
  const created = await owner.request.post('/api/v1/trips', {
    headers,
    data: { title: '背景推播測試' },
  });
  expect(created.ok()).toBeTruthy();
  const path = '/api/v1/trips/' + (await created.json()).id;
  const invite = await owner.request.post(path + '/invitations', { headers, data: {} });
  const joined = await guest.request.post('/api/v1/auth/guest', {
    headers,
    data: { code: (await invite.json()).code, nickname: '推播測試旅伴' },
  });
  expect(joined.ok()).toBeTruthy();
  return async () => {
    const comment = await owner.request.post(path + '/comments', {
      headers,
      data: { content: '@推播測試旅伴 已確認測試行程' },
    });
    expect(comment.ok()).toBeTruthy();
    const inbox = await guest.request.get('/api/v1/notifications');
    const [notice] = (await inbox.json()).items;
    const id = (await comment.json()).id;
    expect(notice.comment_id).toBe(id);
    return { id, notice };
  };
}

test('已安裝瀏覽器在隔離的一般設定檔訂閱並接收背景提及', async ({ browser, baseURL }, info) => {
  const owner = await browser.newContext({ baseURL });
  const user = await chromium.launchPersistentContext(info.outputPath('temporary-profile'), {
    baseURL,
    executablePath: process.env.CHROME_EXECUTABLE,
    headless: false,
    args: ['--start-minimized'],
    ignoreDefaultArgs: ['--disable-background-networking'],
  });
  const report: Record<string, unknown> = {};
  try {
    const mention = await setup(owner, user);
    await user.grantPermissions(['notifications'], { origin: baseURL! });
    const page = await user.newPage();
    await page.goto('/');
    await page.getByRole('button', { name: '通知中心', exact: true }).click();
    const enable = page.getByRole('button', { name: '啟用這台裝置的推播' });
    await expect(enable).toBeVisible();
    Object.assign(
      report,
      await page.evaluate(() => ({
        browser: navigator.userAgent,
        secure: isSecureContext,
        permission: Notification.permission,
      })),
    );
    await enable.click();
    const success = page.getByRole('button', { name: '關閉推播' });
    const failure = page.getByRole('dialog').getByRole('alert');
    await expect(success.or(failure)).toBeVisible({ timeout: 45000 });
    report.subscribed = await success.isVisible();
    report.browserError = report.subscribed ? undefined : await failure.innerText();
    // Leave the context running with no WayToGo page open.
    await page.close();
    const sent = Date.now();
    const { id, notice } = await mention();
    report.sentAt = new Date(sent).toISOString();
    report.inboxMatched = !!id;
    test.skip(
      !report.subscribed,
      'Browser push service declined this temporary profile: ' + report.browserError,
    );
    const worker = user.serviceWorkers()[0];
    await expect
      .poll(
        async () =>
          worker.evaluate(async () => {
            const reg = (self as unknown as { registration: ServiceWorkerRegistration })
              .registration;
            const [notification] = await reg.getNotifications({ tag: 'waytogo-mention' });
            return notification?.data?.noticeId;
          }),
        { timeout: 45000 },
      )
      .toBe(notice.id);
    report.notificationMatched = true;
    report.browserNotificationObservedAt = new Date().toISOString();
    if (process.platform === 'win32') {
      const probe = await promisify(execFile)(
        'powershell.exe',
        [
          '-NoProfile',
          '-NonInteractive',
          '-ExecutionPolicy',
          'Bypass',
          '-File',
          resolve('tests/probe-test-toast.ps1'),
          '-Origin',
          baseURL!,
        ],
        { windowsHide: true, timeout: 9000 },
      ).catch(() => ({ stdout: 'unavailable' }));
      report.windowsBanner = probe.stdout.trim();
      if (report.windowsBanner === 'clicked-isolated-toast') {
        const destination = () => user.pages().find((p) => p.url().endsWith('#comment-' + id));
        await expect.poll(() => Boolean(destination())).toBe(true);
        await expect(destination()!.locator('#comment-' + id)).toBeFocused();
        await expect
          .poll(async () => {
            const response = await (await user.request.get('/api/v1/notifications')).json();
            return response.items.find((item: { id: string }) => item.id === notice.id)?.read;
          })
          .toBe(true);
        report.osClickOpenedMatchingComment = true;
        report.osClickMarkedRead = true;
      }
    }
  } finally {
    console.log('Background push probe: ' + JSON.stringify(report));
    if (process.env.E2E_PUSH_RESULT)
      await writeFile(process.env.E2E_PUSH_RESULT, JSON.stringify(report, null, 2));
    await user.close();
    await owner.close();
  }
});

test('模擬瀏覽器收到推播後以授權通知定位留言', async ({ browser, baseURL }) => {
  const owner = await browser.newContext({ baseURL });
  const guest = await browser.newContext({ baseURL, permissions: ['notifications'] });
  try {
    const mention = await setup(owner, guest);
    const page = await guest.newPage();
    await page.goto('/');
    await page.evaluate(() => navigator.serviceWorker.ready.then(() => true));
    const { id, notice } = await mention();
    const cdp = await guest.newCDPSession(page);
    const registration = new Promise<string>((resolve) =>
      cdp.on('ServiceWorker.workerRegistrationUpdated', ({ registrations }) => {
        const entry = registrations.find((r) => r.scopeURL === baseURL + '/' && !r.isDeleted);
        if (entry) resolve(entry.registrationId);
      }),
    );
    await cdp.send('ServiceWorker.enable');
    await cdp.send('ServiceWorker.deliverPushMessage', {
      origin: baseURL!,
      registrationId: await registration,
      data: '',
    });
    const notification = () =>
      page.evaluate(async () => {
        const [n] = await (
          await navigator.serviceWorker.ready
        ).getNotifications({ tag: 'waytogo-mention' });
        return n && { title: n.title, body: n.body, id: n.data?.noticeId };
      });
    await expect
      .poll(notification)
      .toEqual({ title: 'WayToGo 旅伴手札', body: '旅伴在討論中提及了你。', id: notice.id });
    // The OS notification tray is outside WebDriver. Dispatch its click event in the
    // installed worker and capture openWindow, which normally requires an OS user gesture.
    const destination = await guest.serviceWorkers()[0].evaluate(async () => {
      const sw = self as unknown as {
        registration: ServiceWorkerRegistration;
        clients: { openWindow: (url: string) => Promise<unknown> };
      };
      const [n] = await sw.registration.getNotifications({ tag: 'waytogo-mention' });
      const click = new Event('notificationclick');
      let target = '';
      Object.assign(click, { notification: n, waitUntil: () => {} });
      const original = sw.clients.openWindow;
      try {
        sw.clients.openWindow = async (url) => {
          target = url;
        };
        self.dispatchEvent(click);
      } finally {
        sw.clients.openWindow = original;
      }
      return target;
    });
    expect(destination).toBe(baseURL + '/?notifications=1#notice=' + notice.id);
    await page.goto(destination);
    await expect(page.locator('#comment-' + id)).toContainText('已確認測試行程');
    await expect(page.locator('#comment-' + id)).toBeFocused();
    expect((await (await guest.request.get('/api/v1/notifications')).json()).items[0].read).toBe(
      true,
    );
  } finally {
    await guest.close();
    await owner.close();
  }
});
