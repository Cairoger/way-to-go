const fs = require('node:fs');
const path = require('node:path');
const project = path.resolve(__dirname, '../../..');
const {chromium,expect} = require(path.join(project,'frontend/node_modules/@playwright/test'));
const auth=JSON.parse(fs.readFileSync(process.env.WTG_UI_CONFIG || path.join(project,'.local/audit-ui-20261125/runtime.json'),'utf8').replace(/^\uFEFF/,''));
const origin=process.env.WTG_CORE_ORIGIN || 'http://127.0.0.1:18731';
const action=(page,name)=>page.getByRole('button',{name,exact:true});
async function run() {
  const browser=await chromium.launch({executablePath:process.env.CHROME_EXECUTABLE || 'C:/Program Files/Google/Chrome/Application/chrome.exe',headless:true});
  try {
    const context=await browser.newContext({baseURL:origin,timezoneId:'Asia/Taipei',locale:'zh-TW',viewport:{width:1360,height:900}});
    const page=await context.newPage();
    page.on('dialog',d=>d.accept());
    const headers={Origin:origin};
    const login=await page.request.post('/api/v1/auth/local-test',{headers,data:{username:auth.username,password:auth.password}});
    expect(login.status()).toBe(200);
    const title='時區與封存 '+Date.now();
    const trip=await (await page.request.post('/api/v1/trips',{headers,data:{title,start_date:'2027-07-01'}})).json();
    const day=(await (await page.request.get('/api/v1/trips/'+trip.id+'/days')).json())[0];
    const entry=await page.request.post('/api/v1/days/'+day.id+'/items',{headers,data:{title:'紐約出發',timezone:'America/New_York',start_time:'09:00',duration:60}});
    expect(entry.status()).toBe(201);
    await page.goto('/?trip='+trip.id);
    const row=page.locator('.wp-timeline li').filter({hasText:'紐約出發'});
    await expect(row).toContainText('America/New_York');
    await expect(row).toContainText('21:00');
    await expect(row).toContainText('09:00');
    console.log('ZONES_UI',await row.innerText());
    await action(page,'封存旅程').click();
    const open=page.getByRole('button').filter({has:page.getByRole('heading',{name:new RegExp(title)})});
    await expect(page.getByRole('heading',{name:'旅程總覽',exact:true})).toBeVisible();
    await expect(open).toHaveCount(0);
    await action(page,'已封存').click();
    await expect(open).toBeVisible();
    await open.click();
    await expect(row).toContainText('紐約出發');
    console.log('ARCHIVE_UI shown only under archived; entry persisted');
    await action(page,'移到回收區').click();
    await action(page,'回收區').click();
    await page.getByRole('button').filter({has:page.getByRole('heading',{name:new RegExp(title)})}).click();
    const dialogs=page.getByRole('dialog');
    if(await dialogs.count()) {
      const button=dialogs.getByRole('button',{name:/復原/});
      if(await button.count()) await button.click();
    }
    await expect(page.getByRole('button').filter({has:page.getByRole('heading',{name:new RegExp('復原.*'+title)})})).toHaveCount(0);
    await action(page,'已封存').click();
    await expect(open).toBeVisible();
    await open.click();
    await expect(row).toContainText('紐約出發');
    console.log('RESTORE_UI restored retaining archive status and New York activity');
  } finally { await browser.close(); }
}
run().catch(e=>{console.error(e.message);process.exitCode=1});
