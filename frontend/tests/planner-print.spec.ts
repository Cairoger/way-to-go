import { expect, test } from '@playwright/test';

test('列印指定行程日並排除私人資料', async ({ page, browserName }) => {
  const member = { id: 'print-user', nickname: '旅伴', account_type: 'local_test' };
  const trip = {
    id: 'print-trip',
    owner_id: member.id,
    title: '列印測試',
    description: '',
    start_date: null,
    end_date: null,
    destinations: [],
    currency: 'TWD',
    status: 'planning',
    cover: 'tainan',
    archived: false,
    deleted_at: null,
    version: 1,
    member_count: 1,
    day_count: 2,
    place_count: 0,
    created_at: '2026-04-01T00:00:00Z',
  };
  const days = ['第一天活動', '第二天活動'].map((title, i) => ({
    id: 'day-' + i,
    day_number: i + 1,
    title: '',
    timezone: 'Asia/Taipei',
    date: null,
    items: [
      {
        id: 'item-' + i,
        editable_by: member.id,
        created_by: member.id,
        title,
        item_type: 'custom',
        start_time: '10:00',
        timezone: null,
        local_timezone: 'Asia/Taipei',
        notes: '私人訂位代碼',
        version: 1,
      },
    ],
  }));
  await page.routeWebSocket('**/ws/trips/**', (ws) => {
    ws.send(JSON.stringify({ type: 'presence', members: [member.id] }));
  });
  await page.route('**/api/v1/**', async (route) => {
    const path = new URL(route.request().url()).pathname.slice('/api/v1'.length);
    const routes: Record<string, unknown> = {
      '/auth/me': member,
      '/notifications': {
        items: [],
        device_registered: false,
        preferences: { mentions: true, push: false, version: 0, public_key: null },
      },
      '/trips': [trip],
      '/trips/print-trip': trip,
      '/trips/print-trip/members': [{ ...member, role: 'owner' }],
      '/trips/print-trip/days': days,
      '/trips/print-trip/places': [],
    };
    await route.fulfill({ json: routes[path] ?? [] });
  });
  await page.goto('/?trip=print-trip');
  await page.getByRole('button', { name: '匯出行程 PDF' }).click();
  await page.getByRole('checkbox', { name: 'Day 2' }).uncheck();
  // The browser print dialog and DevTools PDF generation cannot run at the same time.
  await page.evaluate(() => {
    const open = window.open.bind(window);
    window.open = (...args) => {
      const tab = open(...args);
      if (tab)
        tab.print = () => {
          tab.document.body.dataset.printRequested = 'yes';
        };
      return tab;
    };
  });
  const [preview] = await Promise.all([
    page.waitForEvent('popup'),
    page.getByRole('button', { name: '列印或儲存 PDF' }).click(),
  ]);
  await expect(preview.getByText('10:00　第一天活動')).toBeVisible();
  await expect(preview.getByText('第二天活動')).toHaveCount(0);
  await expect(preview.getByText('私人訂位代碼')).toHaveCount(0);
  await expect(preview.locator('body')).toHaveAttribute('data-print-requested', 'yes');
  if (browserName === 'chromium') {
    const pdf = await preview.pdf({ format: 'A4' });
    expect(pdf.subarray(0, 4).toString()).toBe('%PDF');
  }
  await preview.close();
});
