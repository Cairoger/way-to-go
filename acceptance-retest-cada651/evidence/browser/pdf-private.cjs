const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');
const root = path.resolve(__dirname, '../../..');
const {chromium, expect} = require(path.join(root,'frontend/node_modules/@playwright/test'));
const setup = JSON.parse(fs.readFileSync(process.env.WTG_AUDIT_SETUP,'utf8').replace(/^\uFEFF/,''));
const result = {expectedPublic:'PUBLICCHECKINWWT', expectedAddress:'PUBLICADDRESSWWT', expectedPrivate:['BOOKPRIVATEWWT','EXPENSEPRIVATEWWT','SPLITGUESTWWT','125.79','91.23','34.56'], http:[], printed:{}};
const save = () => fs.writeFileSync(path.join(__dirname,'pdf-private.json'), JSON.stringify(result,null,2));
const headers = {'X-Requested-With':'WayToGo'};
async function body(resp,endpoint) {
  result.http.push({endpoint,status:resp.status()});
  if(!resp.ok())throw Error(endpoint+' HTTP '+resp.status()+': '+(await resp.text()).slice(0,300));
  return resp.json();
}
(async()=>{
  const b=await chromium.launch({executablePath:'C:/Program Files/Google/Chrome/Application/chrome.exe'});
  try{
    const ctx=await b.newContext({baseURL:setup.origin,locale:'zh-TW'});
    const guest=await b.newContext({baseURL:setup.origin,locale:'zh-TW'});
    const req=ctx.request, write=async(u,data)=>body(await req.post(u,{headers,data}),'POST '+u);
    await write('/api/v1/auth/local-test',{username:setup.username,password:setup.password});
    const owner=(await body(await req.get('/api/v1/auth/me'),'GET auth/me')).id;
    const trip=await write('/api/v1/trips',{title:'PDF 敏感欄位驗收',currency:'TWD',start_date:'2027-07-10',end_date:'2027-07-10'});
    const api='/api/v1/trips/'+trip.id;
    const {code}=await write(api+'/invitations',{});
    await body(await guest.request.post('/api/v1/auth/guest',{headers,data:{code,nickname:'SPLITGUESTWWT'}}),'POST auth/guest');
    const guestId=(await body(await guest.request.get('/api/v1/auth/me'),'GET guest auth/me')).id;
    const [day]=await body(await req.get(api+'/days'),'GET trip/days');
    const place=await write(api+'/places',{name:'港邊旅館',address:result.expectedAddress,category:'stay'});
    const item=await write('/api/v1/days/'+day.id+'/items',{title:result.expectedPublic,item_type:'stay',place_id:place.id,start_time:'15:00'});
    const booking=await write(api+'/bookings',{title:'合成旅館預訂',kind:'stay',status:'booked',currency:'TWD',reference:'BOOKPRIVATEWWT',item_id:item.id,stay:{check_in:'2027-07-10',check_out:'2027-07-11',guests:[]}});
    const expense=await write(api+'/expenses',{title:'EXPENSEPRIVATEWWT',category:'住宿',incurred_on:'2027-07-10',kind:'actual',currency:'TWD',amount:'125.79',payers:{[owner]:'125.79'},split_mode:'custom',splits:{[owner]:'91.23',[guestId]:'34.56'}});
    const storedBookings=await body(await req.get(api+'/bookings'),'GET bookings');
    const finance=await body(await req.get(api+'/finance'),'GET finance');
    const row=finance.expenses.find(e=>e.id===expense.id),stay=storedBookings.find(r=>r.id===booking.id);
    result.persisted={tripId:trip.id,booking:{reference:stay.reference,linkedToPrintedItem:stay.item_id===item.id},expense:{title:row.title,amount:row.amount,payers:row.payers,splits:row.splits,guestNickname:finance.members[guestId].nickname}};
    if(stay.reference!=='BOOKPRIVATEWWT'||stay.item_id!==item.id||row.title!=='EXPENSEPRIVATEWWT'||String(row.amount)!=='125.79'||row.splits[owner].amount!=='91.23'||row.splits[guestId].amount!=='34.56')throw Error('Persisted booking/expense proof mismatch');
    const fileResponse=await req.get(api+'/files');
    result.privateFiles={collectionStatus:fileResponse.status(),expected:'Create authorized private file, then assert its absence',actual:'Private file object unavailable; separate from booking and expense verification'};save();
    const p=await ctx.newPage();p.setDefaultTimeout(10000);
    await p.goto('/?trip='+trip.id);
    await expect(p.getByRole('heading',{name:result.expectedPublic})).toBeVisible();
    await p.getByRole('button',{name:'匯出行程 PDF'}).click();
    await p.evaluate(()=>{
      const open=window.open.bind(window);
      window.open=(...args)=>{const w=open(...args);if(w)w.print=()=>{w.document.body.dataset.printRequested='yes'};return w};
    });
    for(const mode of ['details','brief']) {
      await p.getByLabel('詳細程度').selectOption(mode);
      const [popup]=await Promise.all([p.waitForEvent('popup'),p.getByRole('button',{name:'列印或儲存 PDF'}).click()]);
      await popup.waitForFunction(()=>document.body.dataset.printRequested==='yes');
      const dom=await popup.locator('body').innerText();
      const bytes=await popup.pdf({path:path.join(__dirname,'pdf-private-'+mode+'.pdf'),format:'A4'});
      result.printed[mode]={dom,bytes:bytes.length,sha256:crypto.createHash('sha256').update(bytes).digest('hex'),absentFromDOM:Object.fromEntries(result.expectedPrivate.map(s=>[s,!dom.includes(s)]))};save();
      if(!dom.includes(result.expectedPublic)||dom.includes(result.expectedAddress)!==(mode==='details')||result.expectedPrivate.some(s=>dom.includes(s)))throw Error('Print DOM mismatch: '+mode);
      await popup.close();
    }
  }catch(e){result.error=String(e);save();process.exitCode=1}
  finally{await b.close()}
})();
