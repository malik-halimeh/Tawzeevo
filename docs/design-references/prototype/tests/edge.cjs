const {createRequire}=require('node:module');
const path=require('node:path');
const fs=require('node:fs');
const assert=require('node:assert/strict');
const root=path.resolve(__dirname,'..');
const req=createRequire(path.join(process.env.TAWZEEVO_TOOL_ROOT||path.resolve(root,'../../..'),'package.json'));
const {chromium}=req('playwright');
(async()=>{
 const browser=await chromium.launch();
 const page=await browser.newPage({viewport:{width:360,height:800}});
 const checks=[];
 const click=(a,more='')=>page.locator(`[data-action="${a}"]${more}:visible`).first().click();
 const fit=async(label)=>{const result=await page.evaluate(()=>({width:innerWidth,actual:document.documentElement.scrollWidth,bad:[...document.querySelectorAll('.action-area *')].filter(e=>{const r=e.getBoundingClientRect();return r.width>0&&(r.left<0||r.right>innerWidth);}).map(e=>e.outerHTML.slice(0,100))}));assert.ok(result.actual<=result.width&&result.bad.length===0,JSON.stringify({label,result}));checks.push(label);};
 try{
  await page.goto('http://127.0.0.1:4180');
  for(const lang of ['en','ar']){
   if(lang==='ar')await click('language');
   await click('stop','[data-id="s3"]');await fit('LBP delivery 360 '+lang);
   await click('nav','[data-id="customers"]');await click('customer','[data-id="c3"]');await fit('LBP balance 360 '+lang);
   await click('payment');await page.setViewportSize({width:360,height:440});await page.locator('#payment-form input').fill('100000');
   const visible=await page.locator('#payment-form input').evaluate(e=>{const r=e.getBoundingClientRect();return r.top>=0&&r.bottom<=innerHeight;});assert.ok(visible);checks.push('Payment field in short viewport '+lang);
   await page.keyboard.press('Escape');assert.ok(!await page.locator('dialog').isVisible());checks.push('Escape dismisses dialog '+lang);
   await page.setViewportSize({width:360,height:800});await click('nav','[data-id="work"]');
  }
  fs.writeFileSync(path.join(root,'tests','edge-results.json'),JSON.stringify({status:'PASS',date:new Date().toISOString(),checks},null,2)+'\n');console.log(JSON.stringify({status:'PASS',checks}));
 }catch(error){await page.screenshot({path:path.join(root,'screenshots','edge-failure.png')});console.error(error);process.exitCode=1;}
 finally{await browser.close();}
})();
