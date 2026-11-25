const fs=require("node:fs"),path=require("node:path");
const {chromium,expect}=require(path.resolve("frontend/node_modules/@playwright/test"));
const cfg=JSON.parse(fs.readFileSync(process.argv[2],"utf8"));
const data={};
(async()=>{
 const b=await chromium.launch({executablePath:"C:/Program Files/Google/Chrome/Application/chrome.exe"});
 try {
  const ctx=await b.newContext({baseURL:cfg.origin}),observer=await b.newContext({baseURL:cfg.origin});
  const headers={"X-Requested-With":"WayToGo"};
  const request=async(r)=>{if(!r.ok())throw Error(r.status()+" "+(await r.text()).slice(0,100));return r.json()};
  const original=await request(await ctx.request.post("/api/v1/auth/local-test",{headers,data:{username:cfg.username,password:cfg.password}}));
  const tr=await request(await ctx.request.post("/api/v1/trips",{headers,data:{title:"成員名稱版本複驗"}})),base="/api/v1/trips/"+tr.id;
  const inv=await request(await ctx.request.post(base+"/invitations",{headers,data:{days:1}}));
  await request(await observer.request.post("/api/v1/auth/guest",{headers,data:{nickname:"另一位旅伴",code:inv.code}}));
  const pages=[await ctx.newPage(),await ctx.newPage()];
  await Promise.all(pages.map(async(p)=>{await p.goto("/");await p.locator("button.profile").click();await expect(p.getByLabel("顯示暱稱")).toHaveValue(original.nickname)}));
  data.both_forms_read_same_initial_name=true;
  const names=["第一頁儲存","第二頁舊表單儲存"];
  for(const [index,p] of pages.entries())await p.getByLabel("顯示暱稱").fill(names[index]);
  data.writes=[];
  for(const [index,p] of pages.entries()){
   const [res]=await Promise.all([p.waitForResponse(r=>r.url().endsWith("/api/v1/auth/me")&&r.request().method()==="PATCH"),p.getByRole("button",{name:"儲存暱稱"}).click()]);
   const saved=await request(res);await expect(p.getByText("暱稱已儲存。")).toBeVisible();
   const members=await request(await observer.request.get(base+"/members"));
   const peerSees=JSON.stringify(members).includes(names[index]);expect(peerSees).toBeTruthy();
   data.writes.push({open_tab:index+1,status:res.status(),request_fields:Object.keys(res.request().postDataJSON()),if_match_sent:!!res.request().headers()["if-match"],returned_nickname:saved.nickname,member_in_other_context_read_new_value:peerSees});
  }
  const after=await ctx.request.get("/api/v1/auth/me");data.latest_nickname=(await after.json()).nickname;data.server_supplied_etag=after.headers().etag||null;
  const precondition=await ctx.request.patch("/api/v1/auth/me",{headers:{...headers,"If-Match":'"deliberately-nonmatching-revision"'},data:{nickname:"明確不匹配的條件"}});
  data.explicit_nonmatching_if_match_http=precondition.status();
  data.after_conditional_write=(await request(await ctx.request.get("/api/v1/auth/me"))).nickname;
 }catch(e){data.diagnostic=String(e);process.exitCode=1}
 finally{fs.writeFileSync(path.join(__dirname,"profile-tabs.json"),JSON.stringify(data,null,2));await b.close()}
})();

