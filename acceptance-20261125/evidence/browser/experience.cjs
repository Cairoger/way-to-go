const fs=require('node:fs');
const path=require('node:path');
const root=path.resolve(__dirname,'../../..');
const {chromium,expect}=require(path.join(root,'frontend/node_modules/@playwright/test'));
const setup=JSON.parse(fs.readFileSync(path.join(root,'.local/audit-ui-20261125/runtime.json'),'utf8'));
const store={};
const save=()=>fs.writeFileSync(path.join(__dirname,'experience.json'),JSON.stringify(store,null,2));
const headers={'X-Requested-With':'WayToGo'};
async function json(res){
  if(!res.ok()) throw Error(res.status()+': '+(await res.text()).slice(0,250));
  return res.json();
}
async function audit(page){
  const folder=path.join(root,'frontend/node_modules/.pnpm');
  const name=fs.readdirSync(folder).find(x=>x.startsWith('axe-core@'));
  await page.addScriptTag({path:path.join(folder,name,'node_modules/axe-core/axe.min.js')});
  return page.evaluate(async()=>{
    const r=await axe.run({runOnly:{type:'tag',values:['wcag2a','wcag2aa','wcag21a','wcag21aa','wcag22a','wcag22aa']}});
    return {tool:r.testEngine.version,passes:r.passes.length,incomplete:r.incomplete.length,violations:r.violations.map(v=>({id:v.id,impact:v.impact,tags:v.tags,nodes:v.nodes.map(n=>({target:n.target,html:n.html,summary:n.failureSummary}))}))};
  });
}
(async()=>{
  const browser=await chromium.launch({executablePath:'C:/Program Files/Google/Chrome/Application/chrome.exe'});
  try{
    const context=await browser.newContext({baseURL:setup.origin,locale:'zh-TW',viewport:{width:1280,height:820}});
    const p=await context.newPage();
    p.setDefaultTimeout(12000);
    await p.goto('/');
    await expect(p.getByRole('heading',{name:'旅程總覽',exact:true})).toBeVisible();
    await p.screenshot({path:path.join(__dirname,'desktop-home.png')});
    store.a11y={home:await audit(p)};save();
    await p.getByRole('button',{name:'建立旅程',exact:true}).click();
    const form=p.getByRole('form',{name:'本機測試帳號登入'});
    await form.getByRole('button',{name:'使用測試帳號登入'}).click();
    store.form={nativeRequired:await form.getByLabel('測試帳號',{exact:true}).evaluate(e=>e.validationMessage),locale:await p.evaluate(()=>navigator.language)};
    await form.getByLabel('測試帳號',{exact:true}).fill('not-my-account');
    await form.getByLabel('密碼').fill('invalid-test-only');
    await form.getByRole('button',{name:'使用測試帳號登入'}).click();
    await expect(p.getByRole('alert')).toBeVisible();
    store.form.invalidCredentials=await p.getByRole('alert').innerText();save();
    await p.keyboard.press('Escape');
    const req=context.request;
    await json(await req.post('/api/v1/auth/local-test',{headers,data:{username:setup.username,password:setup.password}}));
    const trip=await json(await req.post('/api/v1/trips',{headers,data:{title:'港都散步｜實際瀏覽器驗收',start_date:'2027-02-01',end_date:'2027-02-02'}}));
    const api='/api/v1/trips/'+trip.id;
    const days=await json(await req.get(api+'/days'));
    const points=[['港邊步道','place',22.62,120.29],['車站咖啡','food',22.635,120.3],['古城旅館','stay',22.63,120.28]];
    for(const [i,point] of points.entries()){
      const [name,category,latitude,longitude]=point;
      const place=await json(await req.post(api+'/places',{headers,data:{name,category,latitude,longitude,address:name+'測試路一號',notes:'行前私人備註'}}));
      await json(await req.post('/api/v1/days/'+days[i===2?1:0].id+'/items',{headers,data:{title:name,item_type:category,place_id:place.id,start_time:i===0?'09:00':'14:00',duration:45,notes:'合成私人資料'}}));
    }
    let tiles=0;
    await p.route('https://tile.openstreetmap.org/**',r=>{tiles++;return r.abort('failed')});
    await p.goto('/?trip='+trip.id);
    await expect(p.getByText('尚無可用天氣預報',{exact:true})).toBeVisible();
    store.weather='尚無可用天氣預報';
    const tab=x=>p.getByRole('button',{name:x,exact:true});
    await tab('旅程地圖').click();
    await expect(p.locator('.wp-pin')).toHaveCount(3);
    await p.getByLabel('行程序列連線').selectOption({index:1});
    await expect(p.getByText('虛線依行程順序連接地點，實際道路請參考導航。')).toBeVisible();
    await expect(p.locator('.leaflet-overlay-pane path')).toHaveCount(1);
    await expect(p.getByText(/底圖暫時無法載入/)).toBeVisible();
    store.map={tileRequestsAborted:tiles,pins:await p.locator('.wp-pin').evaluateAll(xs=>xs.map(x=>({text:x.textContent,color:getComputedStyle(x).backgroundColor}))),line:await p.locator('.leaflet-overlay-pane path').evaluate(x=>({dash:x.getAttribute('stroke-dasharray'),path:x.getAttribute('d')})),notice:await p.locator('.wp-map-panel [role=status]').innerText(),places:await p.locator('.wp-map-line').allTextContents(),links:await p.locator('.wp-map-line a').evaluateAll(xs=>xs.map(x=>({text:x.getAttribute('aria-label'),url:x.href,target:x.target}))),attribution:await p.locator('.leaflet-control-attribution').innerText()};
    await p.locator('.wp-map-panel').screenshot({path:path.join(__dirname,'live-map-fallback.png')});
    // Keep public providers untouched; assert user-initiated popup requests reach the URL encoded in each link.
    const opened=[];
    await context.route('https://www.google.com/maps/**',async r=>{opened.push(r.request().url());await r.fulfill({status:200,contentType:'text/plain',body:'External destination captured for acceptance'})});
    for(const label of ['在 Google Maps 搜尋港邊步道','導航至港邊步道']){
      const [popup]=await Promise.all([p.waitForEvent('popup'),p.getByRole('link',{name:label,exact:true}).click()]);
      await popup.waitForLoadState('domcontentloaded');await popup.close();
    }
    store.map.popupRequests=opened;save();
    await tab('每日行程').click();
    await expect(p.getByRole('heading',{name:'港邊步道'})).toBeVisible();
    store.a11y.planner=await audit(p);
    store.rwd=[];
    for(const width of [320,390,768,1280]){
      await p.setViewportSize({width,height:844});
      await p.waitForTimeout(120);
      store.rwd.push(await p.evaluate(()=>({width:innerWidth,scrollWidth:document.documentElement.scrollWidth,clientWidth:document.documentElement.clientWidth,button:document.querySelector('.wp-item')?.getBoundingClientRect().width})));
      if(width===390) await p.screenshot({path:path.join(__dirname,'live-mobile.png')});
    }
    save();
    await tab('匯出行程 PDF').click();
    await p.getByRole('checkbox',{name:/Day 2/}).uncheck();
    await p.evaluate(()=>{
      const open=window.open.bind(window);
      window.open=(...args)=>{const tab=open(...args);if(tab)tab.print=()=>{tab.document.body.dataset.printRequested='yes'};return tab};
    });
    store.pdf={};
    for(const mode of ['details','brief']){
      await p.getByLabel('詳細程度').selectOption(mode);
      const [pdf]=await Promise.all([p.waitForEvent('popup'),p.getByRole('button',{name:'列印或儲存 PDF'}).click()]);
      await pdf.waitForFunction(()=>document.body.dataset.printRequested==='yes');
      const printed=await pdf.locator('body').innerText();
      const bytes=await pdf.pdf({path:path.join(__dirname,'itinerary-'+mode+'.pdf'),format:'A4'});
      store.pdf[mode]={bytes:bytes.length,signature:bytes.subarray(0,4).toString(),printed,includesDay1:printed.includes('港邊步道'),includesDay2:printed.includes('古城旅館'),includesAddress:printed.includes('測試路一號'),includesPrivateNote:printed.includes('合成私人資料')||printed.includes('行前私人備註')};
      await pdf.close();
    }
    save();
    await p.keyboard.press('Escape');
    const ready=await p.evaluate(async()=>{await navigator.serviceWorker.ready;return (await caches.keys())});
    await p.reload();
    await expect(p.getByRole('heading',{name:'港邊步道'})).toBeVisible();
    const sw=await p.evaluate(async()=>({controlling:!!navigator.serviceWorker.controller,keys:await Promise.all((await caches.keys()).map(async key=>({key,urls:(await (await caches.open(key)).keys()).map(r=>new URL(r.url).pathname)})))}));
    await context.setOffline(true);
    const offline=await context.newPage();
    let err=null;
    try{await offline.goto(setup.origin+'/?trip='+trip.id,{waitUntil:'domcontentloaded',timeout:12000})}
    catch(e){err=String(e).split('\n')[0]}
    store.offline={ready,sw,error:err,showsItinerary:await offline.getByRole('heading',{name:'港邊步道'}).count(),online:await p.evaluate(()=>navigator.onLine)};
    await context.setOffline(false);
    await offline.goto('/?trip='+trip.id);
    await expect(offline.getByRole('heading',{name:'港邊步道'})).toBeVisible();
    store.offline.afterReconnecting=true;save();
  }catch(e){store.error=String(e);save();process.exitCode=1}
  finally{await browser.close()}
})();
