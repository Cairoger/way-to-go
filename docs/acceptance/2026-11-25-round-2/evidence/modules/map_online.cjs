const fs=require('node:fs');
const path=require('node:path');
const assert=require('node:assert/strict');
const {chromium}=require(path.resolve('frontend/node_modules/@playwright/test'));
const s=JSON.parse(fs.readFileSync(process.argv[2],'utf8').replace(/^\uFEFF/,''));
assert.equal(new URL(s.origin).hostname,'127.0.0.1');
(async()=>{
  const browser=await chromium.launch({executablePath:'C:/Program Files/Google/Chrome/Application/chrome.exe'});
  try {
    const ctx=await browser.newContext({baseURL:s.origin,locale:'zh-TW',viewport:{width:750,height:820}});
    await ctx.request.post('/api/v1/auth/local-test',{headers:{'X-Requested-With':'WayToGo'},data:{username:s.username,password:s.password}});
    const all=await (await ctx.request.get('/api/v1/trips')).json();
    const trip=all.find(t=>t.title.startsWith('模組驗收'));
    assert.ok(trip);
    const page=await ctx.newPage();
    const responses={};
    page.on('response',res=>{if(new URL(res.url()).hostname==='tile.openstreetmap.org')responses[res.status()]=(responses[res.status()]||0)+1});
    await page.goto('/?trip='+trip.id);
    await page.getByRole('button',{name:'旅程地圖',exact:true}).click();
    await page.locator('.wp-pin').first().waitFor();
    try{await page.waitForFunction(()=>[...document.querySelectorAll('img.leaflet-tile')].filter(el=>el.complete&&el.naturalWidth>0).length>0,{},{timeout:10000})}catch{}
    const view=await page.locator('.wp-map').evaluate(el=>({pins:el.querySelectorAll('.wp-pin').length,visibleTiles:[...el.querySelectorAll('img.leaflet-tile')].filter(img=>img.complete&&img.naturalWidth>0).length,attribution:el.querySelector('.leaflet-control-attribution')?.textContent}));
    console.log(JSON.stringify({responses,view}));
    if(view.visibleTiles>0)await page.locator('.wp-map-panel').screenshot({path:path.join(__dirname,'live-map-online.png')});
    process.exitCode=view.visibleTiles>0?0:2;
  } finally {await browser.close();}
})().catch(e=>{console.error(e.message);process.exitCode=1});
