const path = require('node:path');
const fs = require('node:fs');
const { pathToFileURL } = require('node:url');
const pageDir = path.resolve(__dirname, '../..');
const repo = path.resolve(pageDir, '..');
const { chromium } = require(path.join(repo, 'frontend/node_modules/@playwright/test'));
(async () => {
  const browser = await chromium.launch({executablePath:'C:/Program Files/Google/Chrome/Application/chrome.exe'});
  try {
    const page = await browser.newPage({viewport:{width:1366,height:850},locale:'zh-TW'});
    const errors=[];
    page.on('pageerror',e=>errors.push(e.message));
    await page.goto(pathToFileURL(path.join(pageDir,'功能驗收報告.html')).href);
    const count=await page.locator('#rtm tbody tr').count();
    await page.locator('#pri').selectOption('P0');
    await page.locator('#res').selectOption('FAIL');
    const failedP0=await page.locator('#rtm tr[data-pri]:visible td:first-child').allTextContents();
    await page.locator('button[type=reset]').click();
    await page.locator('#q').fill('FR-AUTH-01');
    const matches=await page.locator('#rtm tbody tr:visible').count();
    await page.locator('button[type=reset]').click();
    const pics=await page.locator('figure img').evaluateAll(async imgs => {
      await Promise.all(imgs.map(async image=>{ image.loading='eager'; await image.decode(); }));
      return imgs.map(image=>image.naturalWidth);
    });
    await page.locator('nav a[href="#verdict"]').click();
    if(!page.url().endsWith('#verdict')) throw Error('verdict anchor');
    await page.setViewportSize({width:390,height:844});
    const viewport=await page.evaluate(()=>({width:innerWidth,scroll:document.documentElement.scrollWidth}));
    if(count<140||failedP0.length!==2||matches===0||errors.length||pics.some(v=>!v)||viewport.width!==viewport.scroll)throw Error(JSON.stringify({count,failedP0,matches,errors,pics,viewport}));
    fs.writeFileSync(path.join(__dirname,'report-browser.json'),JSON.stringify({count,failedP0,matches,pics,viewport,errors},null,2));
  } finally { await browser.close(); }
})().catch(e=>{console.error(e);process.exitCode=1;});
