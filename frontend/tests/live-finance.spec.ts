import { expect, test } from '@playwright/test';

test('兩位旅伴記錄外幣支出、收到超額提醒並分兩次結清', async ({
  page: owner,
  browser,
  baseURL,
}) => {
  test.skip(
    process.env.E2E_DISPOSABLE !== '1',
    '使用 run_live_acceptance.py 建立獨立帳號及資料庫。',
  );
  test.setTimeout(100000);
  const guestContext = await browser.newContext({ baseURL });
  const guest = await guestContext.newPage();
  const guestName = '分帳旅伴';
  const ownerName = process.env.E2E_LOCAL_USERNAME!;
  const headers = { 'X-Requested-With': 'WayToGo' };
  try {
    const login = await owner.request.post('/api/v1/auth/local-test', {
      headers,
      data: { username: ownerName, password: process.env.E2E_LOCAL_PASSWORD },
    });
    expect(login.ok()).toBeTruthy();
    const trip = await owner.request.post('/api/v1/trips', {
      headers,
      data: { title: '分帳驗收', currency: 'TWD' },
    });
    expect(trip.ok()).toBeTruthy();
    const { id } = await trip.json();
    const invite = await owner.request.post('/api/v1/trips/' + id + '/invitations', {
      headers,
      data: {},
    });
    expect(invite.ok()).toBeTruthy();
    const { code } = await invite.json();
    expect(
      (
        await guest.request.post('/api/v1/auth/guest', {
          headers,
          data: { code, nickname: guestName },
        })
      ).ok(),
    ).toBeTruthy();
    for (const p of [owner, guest]) {
      await p.goto('/?trip=' + id);
      await p.getByRole('button', { name: '預算與分帳', exact: true }).click();
      await expect(p.getByRole('heading', { name: '預算與分帳' })).toBeVisible();
    }
    await owner.getByRole('button', { name: '設定預算' }).click();
    const budget = owner.getByRole('dialog', { name: '設定預算' });
    await budget.getByLabel(/預算額度/).fill('300');
    await budget.getByRole('button', { name: '儲存預算' }).click();
    await expect(guest.getByText('旅程總預算')).toBeVisible();
    await owner.getByRole('button', { name: '新增費用' }).click();
    const expense = owner.getByRole('dialog', { name: '新增費用' });
    await expense.getByLabel('費用名稱').fill('搭乘機場巴士');
    await expense.getByLabel('費用幣別').fill('USD');
    await expense.getByLabel(/費用總額/).fill('12.50');
    await expense.getByLabel(/手動匯率/).fill('32');
    const payers = expense.getByRole('group', { name: /付款人及墊付金額/ });
    await payers.getByRole('checkbox', { name: guestName }).check();
    await payers.getByLabel(ownerName + ' 墊付金額').fill('10.00');
    await payers.getByLabel(guestName + ' 墊付金額').fill('2.50');
    await expense.getByRole('button', { name: '儲存費用' }).click();
    await expect(expense).toHaveCount(0);
    await expect(guest.getByText('實際支出已超出預算')).toBeVisible();
    await expect(guest.getByText('應付 TWD 120.00')).toBeVisible();
    await guest.getByText('搭乘機場巴士', { exact: true }).click();
    await expect(guest.getByText(/換算 TWD 400.00/)).toBeVisible();
    await guest.getByRole('button', { name: '記錄還款' }).click();
    const firstPayment = guest.getByRole('dialog', { name: '記錄已完成的還款' });
    await firstPayment.getByLabel(/已還金額/).fill('50.00');
    await firstPayment.getByRole('button', { name: '記錄還款' }).click();
    await expect(owner.getByText('部分結清', { exact: true })).toBeVisible();
    await expect(owner.getByText('應收 TWD 70.00')).toBeVisible();
    await owner.getByRole('button', { name: '記錄還款' }).click();
    const finalPayment = owner.getByRole('dialog', { name: '記錄已完成的還款' });
    await expect(finalPayment.getByLabel(/已還金額/)).toHaveValue('70.00');
    await finalPayment.getByRole('button', { name: '記錄還款' }).click();
    await expect(guest.getByText('已結清', { exact: true })).toBeVisible();
    const state = await (await guest.request.get('/api/v1/trips/' + id + '/finance')).json();
    expect(state.expenses).toHaveLength(1);
    expect(state.settlements).toHaveLength(2);
    expect(Object.values(state.balances)).toEqual(['0.00', '0.00']);
  } finally {
    await guestContext.close();
  }
});
