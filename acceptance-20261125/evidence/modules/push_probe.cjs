const assert=require('node:assert/strict');
const crypto=require('node:crypto');
const path=require('node:path');
const {chromium}=require(path.resolve('frontend/node_modules/@playwright/test'));
const origin=process.argv[2];
assert.equal(new URL(origin).hostname,'127.0.0.1');
(async()=>{
  const browser=await chromium.launch({executablePath:'C:/Program Files/Google/Chrome/Application/chrome.exe',headless:true,ignoreDefaultArgs:['--disable-background-networking']});
  try {
    const ctx=await browser.newContext();
    await ctx.grantPermissions(['notifications'],{origin});
    const page=await ctx.newPage();
    await page.goto(origin);
    const key=crypto.createECDH('prime256v1');
    key.generateKeys();
    const result=await page.evaluate(async publicBytes=>{
      await navigator.serviceWorker.register('/sw.js');
      const worker=await navigator.serviceWorker.ready;
      const permission=Notification.permission;
      const subscription=worker.pushManager.subscribe({userVisibleOnly:true,applicationServerKey:Uint8Array.from(publicBytes)})
        .then(async s=>{const host=new URL(s.endpoint).hostname;await s.unsubscribe();return {subscribed:true,provider:host}});
      try {
        return {permission, ...await Promise.race([subscription,new Promise((_,reject)=>setTimeout(()=>reject(new Error('no subscription result within 25 seconds')),25000))])};
      } catch(error) { return {permission,subscribed:false,error:error.name,message:error.message};}
    },Array.from(key.getPublicKey()));
    console.log('Clean Chrome profile, registered product sw.js, ephemeral VAPID key;',result);
  } finally {await browser.close();}
})().catch(e=>{console.error(e.message);process.exitCode=1});
