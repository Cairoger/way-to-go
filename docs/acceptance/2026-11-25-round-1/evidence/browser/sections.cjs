const fs=require('node:fs');
const path=require('node:path');
const root=path.resolve(__dirname,'../../..'),lab=path.join(root,'.local/audit-ui-20261125');
const {chromium,expect}=require(path.join(root,'frontend/node_modules/@playwright/test'));
const setup=JSON.parse(fs.readFileSync(path.join(lab,'runtime.json')));
const modules=path.join(root,'frontend/node_modules/.pnpm');
const axe=path.join(modules,fs.readdirSync(modules).find(s=>s.startsWith('axe-core@')),'node_modules/axe-core/axe.min.js');
const tabs={
  '每日行程':'每日行程','候選景點':'候選景點','旅程地圖':'景點地圖','日期協調':'日期協調','投票':'旅程投票',
  '討論':'旅程討論','行前清單':'行前清單','交通與住宿':'交通與住宿','預算與分帳':'預算與分帳','旅伴':'旅程成員'
};
const out={screens:[]},save=()=>fs.writeFileSync(path.join(__dirname,'sections.json'),JSON.stringify(out,null,2));
(async()=>{
  const browser=await chromium.launch({executablePath:'C:/Program Files/Google/Chrome/Application/chrome.exe'});
  try{
    const ctx=await browser.newContext({baseURL:setup.origin,locale:'zh-TW'});
    await ctx.route('https://tile.openstreetmap.org/**',r=>r.abort('failed'));
    const user=await ctx.request.post('/api/v1/auth/guest',{headers:{'X-Requested-With':'WayToGo'},data:{code:setup.invite,nickname:'畫面檢查旅伴'}});
    if(!user.ok())throw Error('guest setup HTTP '+user.status());
    const p=await ctx.newPage();
    p.setDefaultTimeout(7000);
    await p.goto('/?trip='+setup.trip);
    await p.addScriptTag({path:axe});
    for(const width of [1280,390]){
      await p.setViewportSize({width,height:844});
      for(const [tab,title] of Object.entries(tabs)){
        await p.getByRole('button',{name:tab,exact:true}).click();
        await expect(p.getByRole('heading',{level:2,name:new RegExp(title)}).first()).toBeVisible();
        const screen=await p.evaluate(async()=>{
          const r=await axe.run({runOnly:{type:'tag',values:['wcag2a','wcag2aa','wcag21a','wcag21aa','wcag22a','wcag22aa']}});
          return {width:innerWidth,scrollWidth:document.documentElement.scrollWidth,violations:r.violations.map(v=>({id:v.id,nodes:v.nodes.map(n=>({target:n.target,summary:n.failureSummary}))}))};
        });
        out.screens.push({tab,...screen});save();
      }
    }
  }catch(e){out.error=String(e);save();process.exitCode=1}
  finally{await browser.close()}
})();
