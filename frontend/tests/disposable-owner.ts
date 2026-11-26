import { expect, test as base, type BrowserContext } from '@playwright/test';

const { E2E_DISPOSABLE, E2E_LOCAL_USERNAME, E2E_LOCAL_PASSWORD } = process.env;
export const hasDisposableOwner = Boolean(
  E2E_DISPOSABLE === '1' && E2E_LOCAL_USERNAME && E2E_LOCAL_PASSWORD,
);

type OwnerCookies = Awaited<ReturnType<BrowserContext['cookies']>>;

// Only the built-in page receives the owner session. Additional guest contexts start anonymous.
export const test = base.extend<object, { ownerCookies: OwnerCookies }>({
  ownerCookies: [
    async ({ playwright }, provide, workerInfo) => {
      if (!hasDisposableOwner) throw new Error('需要隔離服務與本機測試帳號。');
      const api = await playwright.request.newContext({ baseURL: workerInfo.project.use.baseURL });
      try {
        const login = () =>
          api.post('/api/v1/auth/local-test', {
            headers: { 'X-Requested-With': 'WayToGo' },
            data: { username: E2E_LOCAL_USERNAME, password: E2E_LOCAL_PASSWORD },
          });
        let response = await login();
        if (response.status() === 429) {
          const delay = Number(response.headers()['retry-after']);
          if (Number.isInteger(delay) && delay > 0 && delay <= 60) {
            await new Promise((resolve) => setTimeout(resolve, delay * 1000));
            response = await login();
          }
        }
        await expect(response).toBeOK();
        const { cookies } = await api.storageState();
        expect(cookies.length).toBeGreaterThan(0);
        await provide(cookies);
      } finally {
        await api.dispose();
      }
    },
    { scope: 'worker', timeout: 100_000 },
  ],
  page: async ({ page, ownerCookies }, provide) => {
    await page.context().addCookies(ownerCookies);
    await provide(page);
  },
});
