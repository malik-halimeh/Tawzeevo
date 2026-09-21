/* Reproducible browser acceptance checks. Uses the repository's existing Playwright and axe. */
const { createRequire } = require('node:module');
const path = require('node:path');
const fs = require('node:fs');
const assert = require('node:assert/strict');
const root = path.resolve(__dirname, '..');
const repo = process.env.TAWZEEVO_TOOL_ROOT || path.resolve(root, '../../..');
const req = createRequire(path.join(repo, 'package.json'));
const { chromium } = req('playwright');
const axeSource = fs.readFileSync(req.resolve('axe-core/axe.min.js'), 'utf8');
const checks = [], errors = [], external = [];
const url = process.env.DAYLIGHT_URL || 'http://127.0.0.1:4180';
let page;
const action = (a,more='')=>page.locator(`[data-action="${a}"]${more}:visible`).first();
const click = async(a,more='')=>action(a,more).click();
const check = (name,condition=true)=>{assert.ok(condition,name);checks.push(name);};
const body = ()=>page.locator('#app').innerText();
const shot = async(name)=>page.screenshot({path:path.join(root,'screenshots',name+'.png'),fullPage:false});
async function reset(){await click('reset');await page.evaluate(()=>document.fonts.ready);}
async function fit(label){
 const overflow=await page.evaluate(()=>({width:innerWidth,doc:document.documentElement.scrollWidth,bad:[...document.querySelectorAll('#app *')].filter(e=>{const r=e.getBoundingClientRect();return r.width&&getComputedStyle(e).visibility!=='hidden'&&(r.left<-.5||r.right>innerWidth+.5);}).slice(0,5).map(e=>e.className)}));
 check('Viewport fit: '+label,overflow.doc<=overflow.width+1&&overflow.bad.length===0);
}
async function axe(label){
 await page.evaluate(axeSource);
 const result=await page.evaluate(async()=>axe.run(document,{runOnly:{type:'tag',values:['wcag2a','wcag2aa','wcag21aa']}}));
 const violations=result.violations.map(v=>({id:v.id,impact:v.impact,nodes:v.nodes.map(n=>n.target)}));
 if(violations.length)console.log(JSON.stringify({label,violations}));
 check('axe WCAG A/AA: '+label,violations.length===0);
}
(async()=>{
 const browser=await chromium.launch({headless:true});
 const context=await browser.newContext({viewport:{width:390,height:844}});
 page=await context.newPage();
 page.on('pageerror',e=>errors.push(e.message));
 page.on('console',m=>{if(m.type()==='error')errors.push(m.text());});
 page.on('request',r=>{if(!r.url().startsWith(url)&&!r.url().startsWith('data:'))external.push(r.url());});
 try {
  await page.goto(url);await page.evaluate(()=>document.fonts.ready);
  await fit('initial phone');await axe('owner phone');
  await click('nav','[data-id="customers"]');
  await page.locator('#customer-search').fill('zzzz');check('Customer search empty state',(await body()).includes('No matching customers'));
  await page.locator('#customer-search').fill('Nour');await click('customer','[data-id="c1"]');
  check('Opening balance + invoice = 121 USD',(await body()).includes('121.00'));
  await page.locator('#network').selectOption('failure');
  await click('payment');await page.locator('#payment-form input').fill('0');await page.locator('#payment-form button').click();
  check('Payment rejects zero',await page.locator('#dialog').innerText().then(t=>t.includes('greater than zero')));
  await page.locator('#payment-form input').fill('20.25');await page.locator('#payment-form button').click();
  check('Payment review uses exact cents',(await page.locator('#dialog').innerText()).includes('20.25'));
  await axe('payment review');await shot('payment-review-mobile-en');
  await click('payment-submit');check('Visible payment pending state',(await page.locator('#dialog').innerText()).includes('Recording payment'));
  await page.getByText('Payment not recorded',{exact:true}).waitFor();
  check('Failed payment preserves balance',(await body()).includes('121.00'));
  await click('retry-online');await page.getByText('Payment recorded',{exact:true}).waitFor();
  check('Retry records one receipt',(await body()).match(/Payment received/g)?.length===1);
  await click('payment-done');check('Correct post-payment balance',(await body()).includes('100.75'));
  await click('back-list');check('Search preserved after returning',await page.locator('#customer-search').inputValue()==='Nour');
  await click('nav','[data-id="invoices"]');await click('invoice','[data-id="i1"]');await click('revise');
  await click('draft-qty','[data-index="0"][data-delta="1"]');
  check('Quantity control retains keyboard focus',await action('draft-qty','[data-index="0"][data-delta="1"]').evaluate(e=>e===document.activeElement));
  check('Piece/box arithmetic: 127 USD',(await body()).includes('127.00'));
  await click('confirm-invoice');await click('history');
  check('Two immutable revisions visible',(await body()).includes('Revision 2')&&(await body()).includes('79.00')&&(await body()).includes('127.00'));
  await click('view-revision','[data-index="0"]');check('Earlier revision unchanged',(await page.locator('#dialog').innerText()).includes('79.00'));
  await click('close-dialog');check('Dialog focus restoration',await action('view-revision','[data-index="0"]').evaluate(e=>e===document.activeElement));
  await click('nav','[data-id="invoices"]');await click('new-invoice');await click('add-product');await click('choose-product','[data-id="oil"]');
  await page.locator('[data-line="0"]').selectOption('BOX');await click('draft-qty','[data-index="0"][data-delta="1"]');
  await click('add-product');await click('choose-product','[data-id="rice"]');check('New composition piece/box total 98.50',(await body()).includes('98.50'));
  await page.locator('#network').selectOption('offline');await click('confirm-invoice');check('Unavailable confirmation preserves draft',(await body()).includes('98.50'));await click('close-dialog');
  await page.locator('#network').selectOption('online');await click('confirm-invoice');check('New invoice receives synthetic identifier',(await body()).includes('INV-DEMO-002'));
  await click('nav','[data-id="work"]');await page.locator('#network').selectOption('offline');await click('stop','[data-id="s1"]');
  await click('complete');await click('complete-confirm');check('Offline delivery queues',(await body()).includes('Queued'));
  await page.locator('#network').selectOption('failure');await click('sync');check('Syncing state visible',(await body()).includes('Syncing'));
  await page.locator('.badge:visible').filter({hasText:'Sync failed'}).first().waitFor();check('Failed sync retains retry',(await body()).includes('waiting to sync'));
  await page.locator('#network').selectOption('online');await click('sync');await page.getByText('Delivery updates synced. No payments were recorded.').waitFor();
  check('Queued delivery eventually accepted',(await body()).includes('Completed'));
  await click('nav','[data-id="customers"]');await click('customer','[data-id="c1"]');
  check('Delivery did not create a payment',(await body()).match(/Payment received/g)?.length===1);
  await click('back-list');await click('customer','[data-id="c3"]');check('LBP isolated from USD',(await body()).includes('2,700,000')&&!(await page.locator('.detail').innerText()).includes('USD'));
  await page.locator('#persona').selectOption('driver');check('Driver sees only separate assigned fixture',(await body()).includes('Safa Grocery')&&!(await page.locator('body').innerText()).includes('Al Nour'));
  check('Driver has no owner navigation',await page.locator('#app [data-action="payment"],#app [data-action="new-invoice"],#app [data-id="customers"]').count()===0);
  await click('stop','[data-id="d1"]');check('Driver projection omits debt and grades',!(await body()).match(/Grade|Account balance|profit|margin|supplier/i));
  await axe('driver details');await shot('driver-mobile-en');
  await page.locator('#persona').selectOption('shop');await click('category','[data-id="drinks"]');check('Category filter works',await page.locator('.product-card').count()===2);
  await click('category','[data-id="all"]');await page.locator('#shop-search').fill('nothing');check('Catalog empty search',(await body()).includes('No products found'));await page.locator('#shop-search').fill('');
  await click('product','[data-id="water"]');await page.locator('#product-unit').selectOption('BOX');await click('product-qty','[data-delta="1"]');await click('add-cart');await click('cart');
  check('Two water boxes total 12 USD',(await body()).includes('12.00'));await click('checkout');await page.locator('#checkout-form button').click();check('Checkout requires guest contact',await page.locator('[aria-invalid="true"]').count()===1);
  await page.locator('[name="name"]').fill('Nadine <Test>');await page.locator('[name="phone"]').fill('+961 00 000 099');await page.locator('[name="address"]').fill('Synthetic street, Saida');
  await page.locator('#network').selectOption('failure');await page.locator('#checkout-form button').click();await page.getByText('Order not sent.',{exact:false}).waitFor();
  check('Checkout failure preserves basket and form',await page.locator('[name="name"]').inputValue()==='Nadine <Test>'&&(await body()).includes('12.00'));
  await page.locator('#network').selectOption('online');await page.locator('#checkout-form button').click();await page.getByText('ORDER RECEIVED',{exact:true}).waitFor();
  check('Guest order acknowledgement, no delivery promise',(await body()).includes('Awaiting confirmation')&&(await body()).includes('Not set yet')&&(await body()).includes('Provisional invoice'));
  check('User input escaped',await page.locator('.order-confirmation test').count()===0&&(await body()).includes('Nadine <Test>'));
  check('Basket cleared after accepted checkout',await action('cart').getAttribute('aria-label')==='Your basket (0)');await shot('order-mobile-en');
  // Eight width/language combinations, with actual owner/driver/shop views and detailed interactions.
  for(const width of [360,390,768,1440]){
   await page.setViewportSize({width,height:width>=1100?1000:844});
   for(const lang of ['en','ar']){
    await reset();if(lang==='ar')await click('language');await page.evaluate(()=>document.fonts.ready);
    await fit(`owner ${width} ${lang}`);await shot(`owner-${width}-${lang}`);
    await click('stop','[data-id="s1"]');await fit(`stop ${width} ${lang}`);
    const attached=await page.locator('.action-area').evaluate(el=>{const r=el.getBoundingClientRect();return r.width>0&&r.left>=0&&r.right<=innerWidth;});check(`Action area visible ${width} ${lang}`,attached);
    if(width===390){await shot(`stop-${width}-${lang}`);await axe(`stop ${lang}`);}
    await click('nav','[data-id="customers"]');await click('customer','[data-id="c1"]');await fit(`customer ${width} ${lang}`);
    if(width===1440)await shot(`customer-${width}-${lang}`);
    await click('nav','[data-id="invoices"]');await click('invoice','[data-id="i1"]');await fit(`invoice ${width} ${lang}`);
    if(width===390)await shot(`invoice-${width}-${lang}`);
    await click('revise');await fit(`composer ${width} ${lang}`);
    await page.locator('#persona').selectOption('driver');await click('stop','[data-id="d1"]');await fit(`driver ${width} ${lang}`);
    if(width===390&&lang==='ar'){await axe('driver Arabic');await shot('driver-mobile-ar');}
    await page.locator('#persona').selectOption('shop');await page.evaluate(()=>document.fonts.ready);await fit(`shop ${width} ${lang}`);await shot(`storefront-${width}-${lang}`);
    if(width===390)await axe(`storefront ${lang}`);
    await click('product','[data-id="oil"]');await fit(`product ${width} ${lang}`);await click('add-cart');await click('cart');await fit(`cart ${width} ${lang}`);await click('checkout');await fit(`checkout ${width} ${lang}`);
    if(width===390){await axe(`checkout ${lang}`);await shot(`checkout-${width}-${lang}`);}
   }
  }
  for(const scenario of ['empty','loading','error']){await page.locator('#scenario').selectOption(scenario);check(`Explicit ${scenario} state`,await page.locator('.empty-state').count()===1);await fit(scenario);await click('ready');}
  await reset();await page.emulateMedia({reducedMotion:'reduce'});check('Reduced motion disables transition',await page.locator('.btn').first().evaluate(e=>getComputedStyle(e).transitionDuration==='0s'));
  await page.keyboard.press('Tab');check('Keyboard focus is visible',await page.evaluate(()=>document.activeElement.matches(':focus-visible')));
  await page.locator('#persona').selectOption('shop');await click('quick-add','[data-id="oil"]');await page.reload();check('Reload resets synthetic state',await page.locator('#persona').inputValue()==='owner');
  check('No external requests',external.length===0);check('No browser console/runtime errors',errors.length===0);
  check('No service worker or persistent application data',await page.evaluate(async()=>{return (await navigator.serviceWorker.getRegistrations()).length===0&&localStorage.length===0&&sessionStorage.length===0;}));
  const result={date:new Date().toISOString(),browser:browser.version(),status:'PASS',checks:checks.length,results:checks,errors,external};
  fs.writeFileSync(path.join(root,'tests','results.json'),JSON.stringify(result,null,2)+'\n');console.log(JSON.stringify({status:'PASS',checks:checks.length}));
 }catch(error){fs.writeFileSync(path.join(root,'tests','results.json'),JSON.stringify({status:'FAIL',checks:checks.length,results:checks,error:String(error),errors,external},null,2)+'\n');await shot('failure');console.error(error);process.exitCode=1;}
 finally{await browser.close();}
})();
