import { expect, test, type Page } from '@playwright/test';
import { execFileSync } from 'node:child_process';
import { resolve } from 'node:path';

const png = Buffer.from(
  'iVBORw0KGgoAAAANSUhEUgAAAAQAAAADCAIAAAA7ljmRAAAADElEQVR4nGNgIAoAAAAnAAHKRxGqAAAAAElFTkSuQmCC',
  'base64',
);
function button(page: Page, name: string) {
  return page.getByRole('button', { name, exact: true });
}
async function attach(page: Page, name: string, privateFile = false) {
  await button(page, '上傳附件').click();
  const dialog = page.getByRole('dialog', { name: '上傳附件', exact: true });
  await dialog
    .locator('input[type=file]')
    .setInputFiles({ name, mimeType: 'image/png', buffer: png });
  if (privateFile) await dialog.getByLabel('可見範圍').selectOption('private');
  await dialog.getByRole('button', { name: '上傳檔案' }).click();
  await expect(page.getByText(name, { exact: true })).toBeVisible();
}

test('真實檔案入口、私人授權、每期任務、留言圖片與兩種 PDF', async ({
  page,
  browser,
  baseURL,
  browserName,
}) => {
  test.skip(
    process.env.E2E_DISPOSABLE !== '1' ||
      !process.env.E2E_LOCAL_USERNAME ||
      !process.env.E2E_LOCAL_PASSWORD,
    '需要隔離服務',
  );
  test.setTimeout(180000);
  const extra = await browser.newContext({ baseURL });
  const guest = await extra.newPage();
  try {
    const headers = { Origin: baseURL! };
    const post = async (path: string, data: object) => {
      const r = await page.request.post('/api/v1' + path, { headers, data });
      expect(r.ok(), await r.text()).toBeTruthy();
      return r.json();
    };
    const owner = await post('/auth/local-test', {
      username: process.env.E2E_LOCAL_USERNAME,
      password: process.env.E2E_LOCAL_PASSWORD,
    });
    const trip = await post('/trips', { title: '文件驗收 ' + Date.now() });
    const root = '/trips/' + trip.id;
    const invitation = await post(root + '/invitations', {});
    expect(
      (
        await guest.request.post('/api/v1/auth/guest', {
          headers,
          data: { code: invitation.code, nickname: '附件讀者' },
        })
      ).ok(),
    ).toBeTruthy();
    const days = await (await page.request.get('/api/v1' + root + '/days')).json();
    await post('/days/' + days[0].id + '/items', { title: 'Public museum', item_type: 'custom' });
    await post(root + '/bookings', {
      kind: 'stay',
      title: '合成住宿',
      reference: 'BOOKMARK771',
      stay: { check_in: '2027-01-01', check_out: '2027-01-02', guests: [] },
    });
    await post(root + '/expenses', {
      title: 'EXPENSEMARK771',
      category: '餐飲',
      incurred_on: '2027-01-01',
      kind: 'actual',
      currency: 'TWD',
      amount: '80',
      split_mode: 'custom',
      payers: { [owner.id]: '80' },
      splits: { [owner.id]: '80' },
    });
    for (const p of [page, guest]) await p.goto('/?trip=' + trip.id);
    await button(page, '旅程檔案').click();
    await attach(page, 'trip-guide.png');
    await button(page, '預覽').click();
    await expect(page.getByRole('img', { name: 'trip-guide.png' })).toBeVisible();
    await page.getByRole('dialog').getByRole('button', { name: '關閉' }).click();
    await button(page, '每日行程').click();
    await button(page, '附件').click();
    await attach(page, 'item-guide.png');
    await page.getByRole('dialog').getByRole('button', { name: '關閉' }).click();
    await button(page, '預算與分帳').click();
    await page.getByText('EXPENSEMARK771', { exact: true }).click();
    await button(page, '附件').click();
    await attach(page, 'expense.png');
    await page.getByRole('dialog').getByRole('button', { name: '關閉' }).click();
    await button(page, '交通與住宿').click();
    await button(page, '住宿').click();
    await button(page, '附件').click();
    await attach(page, 'PRIVATEFILE771.png', true);
    await page.getByRole('dialog').getByRole('button', { name: '關閉' }).click();
    await button(guest, '旅程檔案').click();
    await expect(guest.getByText('item-guide.png', { exact: true })).toBeVisible();
    await expect(guest.getByText('PRIVATEFILE771.png', { exact: true })).toHaveCount(0);
    const ownerFiles = await (await page.request.get('/api/v1' + root + '/files')).json();
    const secret = ownerFiles.find(
      (f: { filename: string }) => f.filename === 'PRIVATEFILE771.png',
    );
    for (const path of ['preview', 'download']) {
      expect((await guest.request.get('/api/v1/files/' + secret.id + '/' + path)).status()).toBe(
        403,
      );
      expect((await page.request.get('/api/v1/files/' + secret.id + '/' + path)).ok()).toBeTruthy();
    }
    await button(page, '行前清單').click();
    await button(page, '新增任務').click();
    const task = page.getByRole('dialog', { name: '新增共用任務' });
    await task.getByLabel('任務名稱').fill('每週確認');
    await task.getByLabel('截止日期').fill('2027-01-01');
    await task.getByLabel('重複週期').selectOption('weekly');
    await task.getByRole('button', { name: '儲存任務' }).click();
    await button(page, '附件').click();
    await attach(page, 'task-guide.png');
    await page.getByRole('dialog').getByRole('button', { name: '關閉' }).click();
    await page.getByLabel('每週確認 我的進度').selectOption('done');
    await expect(page.getByText('每週 · 第 2 期')).toBeVisible();
    await page.getByText(/已完成期別/).click();
    await expect(page.getByText(/第 1 期 · 2027-01-01/)).toBeVisible();
    await button(page, '討論').click();
    await page.getByLabel('新增留言').fill('旅程相片');
    await page
      .getByLabel('留言圖片')
      .setInputFiles({ name: 'comment-picture.png', mimeType: 'image/png', buffer: png });
    await button(page, '送出留言').click();
    await button(guest, '討論').click();
    await expect(guest.getByRole('img', { name: 'comment-picture.png' })).toBeVisible();
    await guest.reload();
    await button(guest, '討論').click();
    const image = guest.getByRole('img', { name: 'comment-picture.png' });
    await expect.poll(() => image.evaluate((el) => (el as HTMLImageElement).naturalWidth)).toBe(4);
    const copied = await post(root + '/copy', {});
    expect(await (await page.request.get('/api/v1/trips/' + copied.id + '/files')).json()).toEqual(
      [],
    );
    if (browserName === 'chromium') {
      await button(page, '每日行程').click();
      await button(page, '匯出行程 PDF').click();
      await page.evaluate(() => {
        const open = window.open.bind(window);
        window.open = (...args) => {
          const tab = open(...args);
          if (tab) tab.print = () => {};
          return tab;
        };
      });
      for (const mode of ['brief', 'details']) {
        await page.getByLabel('詳細程度').selectOption(mode);
        const [tab] = await Promise.all([
          page.waitForEvent('popup'),
          button(page, '列印或儲存 PDF').click(),
        ]);
        await expect(tab.getByText(/Public museum/)).toBeVisible();
        const pdf = await tab.pdf({ format: 'A4' });
        const python =
          process.env.E2E_PYTHON ||
          resolve(
            '..',
            '.venv',
            process.platform === 'win32' ? 'Scripts/python.exe' : 'bin/python',
          );
        const extracted = execFileSync(
          python,
          [
            '-X',
            'utf8',
            '-c',
            'from pypdf import PdfReader; import io,sys; print(" ".join(p.extract_text() for p in PdfReader(io.BytesIO(sys.stdin.buffer.read())).pages))',
          ],
          { input: pdf, encoding: 'utf8' },
        );
        expect(extracted).toContain('Public museum');
        for (const marker of ['PRIVATEFILE771', 'BOOKMARK771', 'EXPENSEMARK771'])
          expect(extracted).not.toContain(marker);
        await tab.close();
      }
    }
  } finally {
    await extra.close();
  }
});
