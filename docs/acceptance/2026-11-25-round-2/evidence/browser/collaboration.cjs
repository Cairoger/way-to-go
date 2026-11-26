const fs = require('node:fs');
const path = require('node:path');
const { performance } = require('node:perf_hooks');
const root = path.resolve(__dirname, '../../..');
const pw = require(path.join(root, 'frontend/node_modules/@playwright/test'));
const setup = JSON.parse(fs.readFileSync(process.env.WTG_AUDIT_SETUP || path.join(root, '.local/audit-ui-20261125/runtime.json'),'utf8').replace(/^\uFEFF/,''));
const chrome = 'C:/Program Files/Google/Chrome/Application/chrome.exe';
const count = Number(process.env.WTG_AUDIT_CLIENTS || 5);
if(![2,3,4,5].includes(count))throw new Error('Supported collaboration group: 2–5');
const visibleGroup = new RegExp(count+' 人在線');
const out = { config: { clients: count, upstream: process.env.WTG_AUDIT_STACK || 'local Next.js -> FastAPI -> fresh SQLite', client: count+' isolated Chrome browser contexts' }, samples: [], apiMs: [], editVisibleMs: [] };
const result=path.resolve(__dirname,process.env.WTG_AUDIT_RESULT || 'collaboration.json');
const save = () => fs.writeFileSync(result, JSON.stringify(out, null, 2));
const headers = { 'X-Requested-With': 'WayToGo' };
const wait = ms => new Promise(resolve=>setTimeout(resolve,ms));
const p95 = xs => [...xs].sort((a,b)=>a-b)[Math.ceil(xs.length*.95)-1];
async function data(response) {
  if (!response.ok()) throw new Error(response.status()+' '+(await response.text()).slice(0,260));
  return response.json();
}
(async()=>{
  const browser = await pw.chromium.launch({executablePath:chrome});
  try {
    const contexts = await Promise.all(Array.from({length:count},()=>browser.newContext({baseURL:setup.origin,locale:'zh-TW'})));
    const pages = await Promise.all(contexts.map(c=>c.newPage()));
    const states = pages.map(()=>({opened:0,closed:0,peak:0}));
    pages.forEach((p,i)=>p.on('websocket',s=>{
      if(!s.url().includes('/ws/trips/')) return;
      const state=states[i];
      state.opened++;
      state.peak=Math.max(state.peak,state.opened-state.closed);
      s.on('close',()=>state.closed++);
    }));
    const owner=contexts[0].request;
    await data(await owner.post('/api/v1/auth/local-test',{headers,data:{username:setup.username,password:setup.password}}));
    const trip = await data(await owner.post('/api/v1/trips',{headers,data:{title:'五位旅伴同步驗收'}}));
    const tripApi='/api/v1/trips/'+trip.id;
    const {code}=await data(await owner.post(tripApi+'/invitations',{headers,data:{}}));
    for(let i=1;i<count;i++) await data(await contexts[i].request.post('/api/v1/auth/guest',{headers,data:{nickname:'旅伴樣本 '+i,code}}));
    for (const p of pages) {
      await p.goto('/?trip='+trip.id);
      await p.getByRole('button',{name:'討論',exact:true}).click();
      await pw.expect(p.getByLabel('新增留言')).toBeVisible({timeout:10000});
    }
    await Promise.all(pages.map(p=>pw.expect(p.getByText(visibleGroup)).toBeVisible({timeout:15000})));
    const start=performance.now();
    const snap=()=>{out.samples.push({seconds:Math.round((performance.now()-start)/1000),ws:states.map(s=>({...s,live:s.opened-s.closed}))});save()};
    snap();
    const messages=await Promise.all(contexts.map(async (c,i)=>data(await c.request.post(tripApi+'/comments',{headers,data:{content:'五位同時留言 '+i}}))));
    out.parallelCreates=messages.length;save();
    const saved=await data(await owner.get(tripApi+'/comments'));
    out.parallelPosts={expected:count,unique:new Set(messages.map(m=>m.id)).size,readBack:saved.filter(c=>c.content.startsWith('五位同時留言 ')).length};
    save();
    let message=messages[0];
    for(let k=0;k<20;k++){
      const content='跨裝置留言編輯 '+k;
      const begin=performance.now();
      const observers=pages.slice(1).map(async (p,idx)=>{
        await p.getByText(content,{exact:true}).waitFor({state:'visible',timeout:10000});
        return {round:k+1,client:idx+2,ms:Math.round(performance.now()-begin)};
      });
      const [updated,measurements]=await Promise.all([owner.patch('/api/v1/comments/'+message.id,{headers,data:{content,version:message.version}}).then(data),Promise.all(observers)]);
      message=updated;
      out.editVisibleMs.push(...measurements);save();
    }
    for(let i=0;i<20;i++) await Promise.all(contexts.map(async c=>{
      const begin=performance.now();
      await data(await c.request.get(tripApi));
      out.apiMs.push(Math.round(performance.now()-begin));
    }));
    out.p95={editToRenderedOtherClientMs:p95(out.editVisibleMs.map(x=>x.ms)),apiGetTripMs:p95(out.apiMs)};
    snap();
    for(let minute=1;minute<=6;minute++){
      await wait(Math.max(0,minute*60000-(performance.now()-start)));
      snap();
    }
    out.visibleGroup=await Promise.all(pages.map(p=>p.getByText(visibleGroup).isVisible()));
    save();
  }catch(e){out.error=String(e);save();process.exitCode=1}
  finally{await browser.close()}
})();
