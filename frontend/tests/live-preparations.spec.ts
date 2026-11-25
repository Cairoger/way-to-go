import { expect, test, type Page } from '@playwright/test';

function action(page: Page, name: string) {
  return page.getByRole('button', { name, exact: true });
}

test('真實登入、邀請、私人與共用任務、訂位授權及提及通知', async ({
  page: owner,
  browser,
  baseURL,
}) => {
  test.skip(
    process.env.E2E_DISPOSABLE !== '1' ||
      !process.env.E2E_LOCAL_USERNAME ||
      !process.env.E2E_LOCAL_PASSWORD,
    '請以 backend/run_live_acceptance.py 啟動隔離測試。',
  );
  test.setTimeout(150000);
  const guestContext = await browser.newContext({ baseURL });
  const guest = await guestContext.newPage();
  try {
    const guestName = '驗收旅伴';
    const tripName = '行前驗收 ' + Date.now();
    await owner.goto('/');
    await action(owner, '建立旅程').click();
    const credentials = owner.getByRole('form', { name: '本機測試帳號登入' });
    await credentials.getByLabel('測試帳號', { exact: true }).fill(process.env.E2E_LOCAL_USERNAME!);
    await credentials.getByLabel('密碼', { exact: true }).fill(process.env.E2E_LOCAL_PASSWORD!);
    await credentials.getByRole('button', { name: '使用測試帳號登入' }).click();
    const newTrip = owner.getByRole('dialog', { name: '建立旅程' });
    await newTrip.getByLabel('旅程名稱').fill(tripName);
    await newTrip.getByRole('button', { name: '建立旅程', exact: true }).click();
    await expect(owner.getByRole('heading', { name: tripName })).toBeVisible();
    await owner.reload();
    await expect(owner.getByRole('heading', { name: tripName })).toBeVisible();
    const tripId = new URL(owner.url()).searchParams.get('trip');
    expect(tripId).toBeTruthy();
    const tripPath = '/api/v1/trips/' + tripId;
    await action(owner, '旅伴').click();
    await action(owner, '產生邀請').click();
    await guest.goto(await owner.getByLabel('邀請連結').inputValue());
    await guest.getByLabel('你的暱稱').fill(guestName);
    await guest.getByRole('dialog').getByRole('button', { name: '加入旅程', exact: true }).click();
    await expect(guest.getByRole('heading', { name: tripName })).toBeVisible();
    await expect(owner.getByText(/2 人在線/)).toBeVisible();
    for (const who of [owner, guest]) await action(who, '行前清單').click();
    await action(owner, '新增任務').click();
    const shared = owner.getByRole('dialog', { name: '新增共用任務' });
    await shared.getByLabel('任務名稱').fill('查詢集合地點');
    await shared.getByRole('checkbox', { name: guestName }).check();
    await shared.getByRole('checkbox', { name: process.env.E2E_LOCAL_USERNAME! }).uncheck();
    await shared.getByRole('button', { name: '儲存任務' }).click();
    await expect(guest.getByRole('heading', { name: '查詢集合地點' })).toBeVisible();
    await expect(owner.getByLabel('查詢集合地點 我的進度')).toHaveCount(0);
    await guest.getByLabel('查詢集合地點 我的進度').selectOption('done');
    await expect(owner.getByText('1 / 1 已完成')).toBeVisible();

    await action(guest, '個人清單').click();
    await action(guest, '新增任務').click();
    const personal = guest.getByRole('dialog', { name: '新增個人任務' });
    await personal.getByLabel('任務名稱').fill('私人行李清點');
    await personal.getByRole('button', { name: '儲存任務' }).click();
    await expect(guest.getByRole('heading', { name: '私人行李清點' })).toBeVisible();
    await action(owner, '個人清單').click();
    await expect(owner.getByText('你的行前清單是空的')).toBeVisible();
    const ownerTasks = await owner.request.get(tripPath + '/tasks');
    expect(ownerTasks.ok()).toBeTruthy();
    expect(await ownerTasks.text()).not.toContain('私人行李清點');

    for (const who of [owner, guest]) {
      await action(who, '交通與住宿').click();
      await action(who, '住宿').click();
    }
    await action(owner, '新增住宿').click();
    const booking = owner.getByRole('dialog', { name: '新增住宿' });
    await booking.getByLabel('住宿名稱').fill('集合旅店');
    await booking.getByLabel('入住日期').fill('2027-06-05');
    await booking.getByLabel('退房日期').fill('2027-06-06');
    await booking.getByLabel(/訂位代號/).fill('BOOK-TEST-ONLY');
    await booking.getByRole('button', { name: '儲存預訂' }).click();
    await expect(owner.getByText('訂位代號 BOOK-TEST-ONLY')).toBeVisible();
    await expect(guest.getByRole('heading', { name: '集合旅店' })).toBeVisible();
    await expect(guest.getByText(/BOOK-TEST-ONLY/)).toHaveCount(0);
    const guestBookings = await guest.request.get(tripPath + '/bookings');
    expect(guestBookings.ok()).toBeTruthy();
    expect(await guestBookings.text()).not.toContain('BOOK-TEST-ONLY');
    await action(owner, '編輯').click();
    const edit = owner.getByRole('dialog', { name: '編輯住宿' });
    await edit.getByRole('checkbox', { name: guestName }).check();
    await edit.getByRole('button', { name: '儲存預訂' }).click();
    await expect(guest.getByText('訂位代號 BOOK-TEST-ONLY')).toBeVisible();

    for (const who of [owner, guest]) await action(who, '航班').click();
    await action(owner, '新增航班').click();
    const flight = owner.getByRole('dialog', { name: '新增航班' });
    await flight.getByLabel('航班預訂名稱').fill('轉機往返');
    await flight.getByRole('button', { name: '新增航段' }).click();
    for (const [index, number, from, to, departure, arrival] of [
      ['1', 'WT01', 'TPE', 'HND', '2027-06-05T08:00', '2027-06-05T11:00'],
      ['2', 'WT02', 'HND', 'CTS', '2027-06-05T14:00', '2027-06-05T15:45'],
    ]) {
      const leg = flight.getByRole('group', { name: '航段 ' + index, exact: true });
      await leg.getByLabel('航班編號').fill(number);
      await leg.getByLabel('出發機場').fill(from);
      await leg.getByLabel('抵達機場').fill(to);
      await leg.getByLabel('起飛（當地時間）').fill(departure);
      await leg.getByLabel('抵達（當地時間）').fill(arrival);
      await leg
        .getByRole('checkbox', {
          name: index === '1' ? guestName : process.env.E2E_LOCAL_USERNAME!,
        })
        .check();
      await leg.getByLabel('座位').fill(index === '1' ? '3A' : '11D');
    }
    await flight.getByRole('button', { name: '儲存預訂' }).click();
    await expect(guest.getByText('WT01 · TPE 至 HND')).toBeVisible();
    await expect(guest.getByText('WT02 · HND 至 CTS')).toBeVisible();
    await expect(guest.getByText(guestName + ' / 3A')).toBeVisible();

    await action(owner, '討論').click();
    await owner.getByLabel('新增留言').fill('住宿確認了 ');
    await owner.getByLabel('提及旅伴').selectOption({ label: guestName });
    await action(owner, '送出留言').click();
    await guest.getByRole('button', { name: /通知中心，1 則未讀/ }).click();
    const inbox = guest.getByRole('dialog', { name: '通知中心' });
    await expect(inbox.getByText(new RegExp(tripName + '」提及你'))).toBeVisible();
    await inbox.getByRole('button', { name: '標為已讀' }).click();
    await expect(inbox.getByRole('button', { name: '標為已讀' })).toHaveCount(0);
    await guest.reload();
    await action(guest, '通知中心').click();
    await expect(
      guest.getByRole('dialog').getByText(new RegExp(tripName + '」提及你')),
    ).toBeVisible();
    await expect(guest.getByRole('dialog').getByRole('button', { name: '標為已讀' })).toHaveCount(
      0,
    );
    await guest
      .getByRole('dialog')
      .getByRole('button', { name: /提及你/ })
      .click();
    await expect(guest.getByText('住宿確認了 @' + guestName, { exact: true })).toBeVisible();
  } finally {
    await guestContext.close();
  }
});
