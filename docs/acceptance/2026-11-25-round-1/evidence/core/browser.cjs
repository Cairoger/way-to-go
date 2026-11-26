// Two isolated Chrome profiles against the disposable stack. Uses Playwright browser controls.
const path = require('node:path');
const fs = require('node:fs');
const assert = require('node:assert/strict');
const project = path.resolve(__dirname, '../../..');
const { chromium, expect } = require(path.join(project, 'frontend/node_modules/@playwright/test'));
const options = JSON.parse(fs.readFileSync(process.env.WTG_UI_CONFIG || path.join(project, '.local/audit-ui-20261125/runtime.json'), 'utf8').replace(/^\uFEFF/, ''));
const origin = process.env.WTG_CORE_ORIGIN || 'http://127.0.0.1:18731';
const log = (name, values = {}) => console.log(JSON.stringify({name, ...values}));
const action = (p, name) => p.getByRole('button', {name,exact:true});
const dialog = p => p.getByRole('dialog');
const heading = (p, name) => p.getByRole('heading', {name,exact:true});
async function createItem(page, name, start, duration) {
  await action(page, '新增活動').click();
  const form = dialog(page);
  await form.getByLabel('活動名稱').fill(name);
  if (start) await form.getByLabel('開始時間').fill(start);
  if (duration) await form.getByLabel('停留分鐘').fill(duration);
  await action(form, '儲存活動').click();
  await expect(heading(page,name)).toBeVisible({timeout:10000});
}
async function run() {
  const browser = await chromium.launch({
    executablePath: process.env.CHROME_EXECUTABLE || 'C:/Program Files/Google/Chrome/Application/chrome.exe',
    headless:true,
  });
  try {
    const ownerCtx = await browser.newContext({baseURL:origin, locale:'zh-TW', viewport:{width:1360,height:900}, serviceWorkers:'block'});
    const guestCtx = await browser.newContext({baseURL:origin, locale:'zh-TW', viewport:{width:1100,height:850}, serviceWorkers:'block'});
    const owner = await ownerCtx.newPage(), guest = await guestCtx.newPage();
    owner.setDefaultTimeout(18000);
    guest.setDefaultTimeout(18000);
    let current, remote, suspend = false;
    const waiting = [];
    await guest.routeWebSocket('**/ws/trips/**', route => {
      if(suspend) { waiting.push(route); return; }
      current = route;
      remote = route.connectToServer();
    });
    await owner.goto('/');
    await action(owner, '建立旅程').click();
    const auth = owner.getByRole('form',{name:'本機測試帳號登入'});
    await auth.getByLabel('測試帳號',{exact:true}).fill(options.username);
    await auth.getByLabel('密碼',{exact:true}).fill(options.password);
    await action(auth, '使用測試帳號登入').click();
    const title = '核心驗收 '+Date.now();
    const tripForm = dialog(owner);
    await tripForm.getByLabel('旅程名稱').fill(title);
    const createFields = await tripForm.locator('input,textarea,select').evaluateAll(nodes=>nodes.map(n=>n.name));
    await action(tripForm, '建立旅程').click();
    await expect(heading(owner,title)).toBeVisible();
    const url = owner.url(), tripId = new URL(url).searchParams.get('trip');
    assert.ok(tripId);
    await owner.reload();
    await expect(heading(owner,title)).toBeVisible();
    log('TITLE_ONLY_SESSION_RELOAD', {createFields});
    await action(owner, '旅伴').click();
    await action(owner, '產生邀請').click();
    const invite = await owner.getByLabel('邀請連結').inputValue();
    const mail = new URL(await owner.getByRole('link',{name:'用 Email 邀請'}).getAttribute('href'));
    assert.ok(mail.protocol === 'mailto:' && mail.searchParams.get('body').includes(invite));
    assert.ok(mail.searchParams.get('subject').includes(title));
    await expect(owner.getByAltText('旅程邀請 QR Code')).toBeVisible();
    await guest.goto(invite);
    await guest.getByLabel('你的暱稱').fill('同團旅伴甲');
    await action(dialog(guest), '加入旅程').click();
    await expect(heading(guest,title)).toBeVisible();
    await expect(owner.getByText(/2 人在線/)).toBeVisible();
    await expect(owner.locator('.member-row').filter({hasText:'同團旅伴甲'})).toContainText('在線');
    log('GUEST_JOIN_EMAIL_QR_PRESENCE',{emailIncludesInvite:true,membersOnline:2});
    await action(owner,'每日行程').click();
    await action(owner,'新增日期').click();
    await action(dialog(owner),'新增日期').click();
    await expect(guest.getByRole('button',{name:/Day 02/})).toBeVisible();
    await owner.getByRole('button',{name:/Day 01/}).click();
    await createItem(owner,'出發散步','09:00','60');
    await expect(heading(guest,'出發散步')).toBeVisible({timeout:10000});
    log('CREATE_VISIBLE_ON_PEER');
    await createItem(guest,'旅伴早餐','09:20','25');
    await expect(heading(owner,'旅伴早餐')).toBeVisible();
    await expect(owner.getByText('時間重疊',{exact:true})).toHaveCount(2);
    log('OVERLAP',{persisted:2,warnings:2});
    await action(owner,'編輯出發散步').click();
    await expect(guest.locator('li').filter({has:heading(guest,'出發散步')})).toContainText('編輯中');
    await dialog(owner).getByLabel('活動名稱').fill('更新散步');
    await action(dialog(owner),'儲存活動').click();
    await expect(heading(guest,'更新散步')).toBeVisible();
    log('EDIT_AND_LOCK_VISIBLE_ON_PEER');
    const guestItem = guest.locator('.wp-timeline li').filter({has:heading(guest,'旅伴早餐')});
    const ownerItem = guest.locator('.wp-timeline li').filter({has:heading(guest,'更新散步')});
    assert.equal(await ownerItem.getAttribute('draggable'),'false');
    await guestItem.dragTo(ownerItem);
    await expect(owner.locator('.wp-timeline li h4').first()).toHaveText('旅伴早餐');
    log('DRAG_SAME_DAY',{first:'旅伴早餐',passive:'更新散步'});
    await guestItem.dragTo(guest.getByRole('button',{name:/Day 02/}));
    await expect(guest.getByRole('button',{name:/Day 02/})).toHaveAttribute('aria-pressed','true');
    await expect(heading(guest,'旅伴早餐')).toBeVisible();
    await expect(heading(owner,'旅伴早餐')).toHaveCount(0);
    await owner.getByRole('button',{name:/Day 02/}).click();
    await expect(heading(owner,'旅伴早餐')).toBeVisible();
    log('DRAG_CROSS_DAY',{guestAndOwnerSeeNewDay:true});
    await guest.screenshot({path:path.join(__dirname,'planner-cross-day.png')});
    await action(guest,'刪除旅伴早餐').click();
    await action(dialog(guest),'確認移除').click();
    await expect(heading(owner,'旅伴早餐')).toHaveCount(0);
    log('DELETE_VISIBLE_ON_PEER');
    // Sever only this synthetic tab's WS, with HTTP and the other tab still online.
    suspend=true;
    assert.ok(current && remote);
    await current.close({code:1001,reason:'isolated integration test'});
    await remote.close({code:1001,reason:'isolated integration test'});
    // Hold any attempted new WS before forwarding it to the live server.
    await expect.poll(()=>waiting.length,{timeout:15000}).toBeGreaterThan(0);
    await createItem(owner,'重連期間新增');
    assert.equal(await heading(guest,'重連期間新增').count(),0);
    log('RECONNECT_BEFORE_RESTORE',{received:0,heldConnections:waiting.length});
    suspend=false;
    // Release the test proxy's already-opened orphan socket. The next handshake is
    // forwarded immediately so the app receives a real open event after restoration.
    for(const route of waiting.splice(0)) await route.close({code:1001,reason:'reconnecting'});
    await expect(heading(guest,'重連期間新增')).toBeVisible({timeout:15000});
    log('RECONNECT_REFETCH',{before:0,after:1});
    await action(owner,'候選景點').click();
    await action(owner,'新增景點').first().click();
    const place=dialog(owner);
    await place.getByLabel('搜尋地點').fill('https://www.google.com/maps/place/Taipei+101/@2,3,14z/data=!3d25.03!4d121.56');
    await action(place,'搜尋').click();
    assert.equal(await place.getByLabel('景點名稱').inputValue(),'Taipei 101');
    assert.equal(await place.locator('[name=latitude]').count() ? await place.locator('[name=latitude]').inputValue() : await place.getByLabel('緯度').inputValue(),'25.03');
    await place.getByLabel('搜尋地點').fill('https://maps.app.goo.gl/example');
    await action(place,'搜尋').click();
    await expect(place.getByText(/請手動填寫名稱與座標/)).toBeVisible();
    await place.getByLabel('景點名稱').fill('手動補充景點');
    await place.locator('form.wp-form button[type=submit], form.wp-form .wp-save').first().click();
    await expect(action(owner,'手動補充景點')).toBeVisible();
    log('MAP_LINK_PARSE_AND_MANUAL_SAVE',{parsed:'Taipei 101',lat:25.03,manualSaved:true});
    log('COMPLETE',{browser:browser.version()});
  } finally { await browser.close(); }
}
run().catch(e=>{console.error(e.message); process.exitCode=1;});
