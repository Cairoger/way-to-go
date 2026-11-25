const fs = require("node:fs"), path = require("node:path");
const {chromium, expect} = require(path.resolve("frontend/node_modules/@playwright/test"));
const cfg=JSON.parse(fs.readFileSync(process.argv[2],"utf8"));
const word = "O'Brien <em>春遊</em> & 夏天";
const observations={};
(async()=>{
 const browser=await chromium.launch({executablePath:"C:/Program Files/Google/Chrome/Application/chrome.exe"});
 try {
  const ctx=await browser.newContext({baseURL:cfg.origin,locale:"zh-TW"});
  const post=async(path,data)=>{const r=await ctx.request.post("/api/v1"+path,{headers:{"X-Requested-With":"WayToGo"},data});if(!r.ok())throw Error(path+" "+r.status());return r.json()};
  await post("/auth/local-test",{username:cfg.username,password:cfg.password});
  const trip=await post("/trips",{title:"普通文字顯示驗收"}), base="/trips/"+trip.id;
  const [day]=await (await ctx.request.get("/api/v1"+base+"/days")).json();
  const place=await post(base+"/places",{name:word,address:"春遊路一號",latitude:25.03,longitude:121.56});
  await post("/days/"+day.id+"/items",{title:word,place_id:place.id});
  await post(base+"/comments",{content:word});
  const p=await ctx.newPage(), tab=n=>p.getByRole("button",{name:n,exact:true});
  async function check(key,loc){await expect(loc).toContainText(word);const em=await loc.locator("em").count();observations[key]={literalFound:(await loc.innerText()).includes(word),emDescendants:em};expect(em).toBe(0)}
  await p.goto("/?trip="+trip.id);
  await check("itinerary",p.getByRole("heading",{name:word,exact:true}));
  await tab("討論").click();
  await check("comment",p.getByText(word,{exact:true}).first());
  await tab("旅程地圖").click();
  await p.locator(".leaflet-marker-icon").first().click();
  await check("leaflet_popup",p.locator(".leaflet-popup-content"));
  await tab("每日行程").click();
  await tab("匯出行程 PDF").click();
  await p.evaluate(()=>{const original=window.open.bind(window);window.open=(...args)=>{const w=original(...args);if(w)w.print=()=>{};return w}});
  const [printable]=await Promise.all([p.waitForEvent("popup"),tab("列印或儲存 PDF").click()]);
  await check("print_view",printable.locator("body"));await printable.close();
  await p.keyboard.press("Escape");
  await p.getByText("離線閱讀",{exact:true}).click();
  await tab("儲存離線旅程").click();await tab("更新離線旅程").waitFor();
  const url=p.url();await ctx.setOffline(true);await p.close();
  const reader=await ctx.newPage();await reader.goto(url);
  await check("saved_offline",reader.getByRole("heading",{name:word,exact:true}));
  await ctx.close();
 }catch(e){observations.error=String(e);process.exitCode=1}
 finally{fs.writeFileSync(path.join(__dirname,"literal-text.json"),JSON.stringify(observations,null,2));await browser.close()}
})();

