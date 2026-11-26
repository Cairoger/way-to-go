const fs=require('node:fs'),path=require('node:path');
const {chromium,webkit,expect}=require(path.resolve("frontend/node_modules/@playwright/test"));
const conf=JSON.parse(fs.readFileSync(process.argv[2],"utf8"));
const engine=process.argv[3]||"chromium";
const summary={engine,observations:{}};
const dest=path.join(__dirname,"walk-"+engine+".json");
const save=()=>fs.writeFileSync(dest,JSON.stringify(summary,null,2));
const obs=summary.observations;
(async()=>{
 const b=await (engine==="webkit"?webkit:chromium).launch(engine==="webkit"?{}:{executablePath:"C:/Program Files/Google/Chrome/Application/chrome.exe"});
 try{
  const ctx=await b.newContext({baseURL:conf.origin,locale:"zh-TW"}),req=ctx.request;
  const headers={"X-Requested-With":"WayToGo"};
  const get=async r=>{if(!r.ok())throw Error("HTTP "+r.status()+": "+(await r.text()).slice(0,160));return r.json()};
  await get(await req.post("/api/v1/auth/local-test",{headers,data:{username:conf.username,password:conf.password}}));
  const trip=await get(await req.post("/api/v1/trips",{headers,data:{title:"實機補驗 "+engine}})),base="/api/v1/trips/"+trip.id;
  const [day]=await get(await req.get(base+"/days"));
  const text="O'Brien & 旅伴 <em>春遊</em>";
  await get(await req.post("/api/v1/days/"+day.id+"/items",{headers,data:{title:text,notes:"慣用符號 < > &"}}));
  const p=await ctx.newPage();await p.goto("/?trip="+trip.id);await p.getByRole("heading",{name:text,exact:true}).waitFor();
  obs.inertText={displayed:await p.getByRole("heading",{name:text,exact:true}).innerText(),emChildren:await p.getByRole("heading",{name:text,exact:true}).locator("em").count()};save();
  const btn=n=>p.getByRole("button",{name:n,exact:true});
  await btn("日期協調").click();await btn("標記我的日期").click();await p.getByLabel("開始日期",{exact:true}).fill("2027-05-04");await btn("儲存標記").click();
  await p.getByText(/1 可以 · 0 可能 · 0 不行 · 0 未填/).first().waitFor();
  await btn("選用區間").click();await btn("確認套用日期").click();await expect.poll(async()=>(await get(await req.get(base))).start_date).toBe("2027-05-04");
  obs.liveDate="2027-05-04 written from UI and read back from API";save();
  const poll=await get(await req.post(base+"/polls",{headers,data:{title:"雙城評分",kind:"place",mode:"rating",options:[{text:"京都"},{text:"台南"}]}}));
  await btn("投票").click();const a=p.locator("article").filter({has:p.getByRole("heading",{name:"雙城評分"})});
  await a.getByRole("combobox",{name:"京都",exact:true}).selectOption("4");await a.getByRole("combobox",{name:"台南",exact:true}).selectOption("5");
  const [ballot]=await Promise.all([p.waitForResponse(r=>r.url().includes("/ballot") && r.request().method()==="PUT"),a.getByRole("button",{name:"送出選票"}).click()]);
  obs.ratingHTTP=ballot.status();expect(ballot.ok()).toBeTruthy();save();
  await btn("旅程地圖").click();const hint=p.getByText(/付費功能開發中/);obs.mapPaidHint=await hint.innerText();save();
  await btn("交通與住宿").click();await btn("新增航班").waitFor();const body=p.getByRole("main");obs.flightHintOnList=await body.getByText(/付費功能開發中/).count();
  await btn("新增航班").click();const dlg=p.getByRole("dialog",{name:"新增航班"});await dlg.waitFor();obs.flightHintInForm=await dlg.getByText(/付費功能開發中/).count();obs.flightManualEntry=await dlg.getByLabel("航班編號",{exact:true}).count();obs.flightText=(await dlg.innerText()).slice(0,1600);
  await p.screenshot({path:path.join(__dirname,"flight-"+engine+".png")});save();
  await ctx.close();
 }catch(e){summary.error=String(e);save();process.exitCode=1}finally{await b.close()}
})();
