const fs=require('node:fs');
const path=require('node:path');
const root=path.resolve(__dirname,'../../..');
process.env.PLAYWRIGHT_BROWSERS_PATH=path.join(root,'.local/audit-ui-20261125/pw-browsers');
const {firefox,expect}=require(path.join(root,'frontend/node_modules/@playwright/test'));
(async()=>{
  const b=await firefox.launch({timeout:18000});
  try{
    const p=await b.newPage({locale:'zh-TW'});
    await p.goto('http://127.0.0.1:18731/');
    await expect(p.getByRole('heading',{name:'旅程總覽',exact:true})).toBeVisible();
    await p.getByRole('button',{name:'已確認',exact:true}).click();
    await expect(p.locator('.trip-card')).toHaveCount(1);
    await p.getByRole('button',{name:'開啟多洛米蒂山間漫遊'}).click();
    await p.getByRole('button',{name:'Day 3',exact:true}).click();
    await expect(p.getByText('塞切達山',{exact:true})).toBeVisible();
    console.log(JSON.stringify({browser:b.version(),ua:await p.evaluate(()=>navigator.userAgent),workspace:true,filters:true,openDay3:true}));
  }finally{await b.close()}
})().catch(e=>{console.error(String(e));process.exitCode=1});
