const {createRequire}=require('node:module');
const path=require('node:path');
const fs=require('node:fs');
const assert=require('node:assert/strict');
const root=path.resolve(__dirname,'..');
const req=createRequire(path.join(process.env.TAWZEEVO_TOOL_ROOT||path.resolve(root,'../../..'),'package.json'));
const {chromium}=req('playwright');
const axe=fs.readFileSync(req.resolve('axe-core/axe.min.js'),'utf8');
const url=process.env.DAYLIGHT_URL||'http://127.0.0.1:4180';
const checks=[],errors=[],external=[];
function check(label,result){assert.ok(result,label);checks.push(label);}
(async()=>{
 const browser=await chromium.launch({headless:true});
 const page=await browser.newPage();
 page.on('pageerror',e=>errors.push(e.message));
 page.on('console',m=>{if(m.type()==='error')errors.push(m.text());});
 page.on('request',r=>{if(!r.url().startsWith(url)&&!r.url().startsWith('data:'))external.push(r.url());});
 try {
  for(const lang of ['en','ar'])for(const width of [360,390,768,1440])for(const view of ['home','signin']){
   await page.setViewportSize({width,height:width===1440?1000:844});
   await page.goto(`${url}/welcome.html?lang=${lang}#${view}`);await page.evaluate(()=>document.fonts.ready);
   const label=`${view} ${width} ${lang}`;
   check('Correct requested screen: '+label,await page.locator(view==='home'?'.hero':'#signin-form').isVisible());
   check('No page overflow: '+label,await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
   check('No clipped text: '+label,await page.evaluate(()=>[...document.querySelectorAll('h1,h2,h3,p,label,strong')].every(e=>e.scrollWidth<=e.clientWidth+1||getComputedStyle(e).display==='inline')));
   await page.evaluate(axe);
   const violations=await page.evaluate(async()=> (await axe.run(document,{runOnly:{type:'tag',values:['wcag2a','wcag2aa','wcag21aa']}})).violations);
   if(violations.length)console.log(JSON.stringify({label,violations:violations.map(v=>({id:v.id,nodes:v.nodes.map(n=>n.target)}))}));
   check('axe WCAG A/AA: '+label,violations.length===0);
   await page.screenshot({path:path.join(root,'screenshots',`entry-${view}-${width}-${lang}.png`),fullPage:true});
  }
  await page.goto(url+'/welcome.html#signin');
  await page.locator('#email').fill('bad');await page.locator('#password').fill('');await page.locator('.submit').click();
  check('Validation restores first invalid field focus',await page.locator('#email').evaluate(e=>e===document.activeElement&&e.getAttribute('aria-invalid')==='true'));
  await page.locator('[data-action="reset"]').click();
  await page.locator('[data-action="reveal"]').click();check('Password reveal is labelled',await page.locator('#password').getAttribute('type')==='text'&&await page.locator('[data-action="reveal"]').getAttribute('aria-label')==='Hide password');
  await page.locator('#entry-state').selectOption('failure');await page.locator('.submit').click();await page.waitForTimeout(750);
  check('Sign-in failure visible',await page.locator('#form-status').innerText()==='Sign-in failed. Check your email and password and try again.');
  check('Sign-in failure preserves email',await page.locator('#email').inputValue()==='rami@example.invalid');
  await page.locator('#entry-state').selectOption('offline');await page.locator('.submit').click();check('Offline is distinct',/offline/.test(await page.locator('#form-status').innerText()));
  await page.locator('#entry-state').selectOption('loading');await page.locator('.submit').click();check('Loading disables duplicate submission',await page.locator('.submit').isDisabled());
  await page.locator('[data-action="reset"]').click();await page.locator('.submit').click();await page.waitForTimeout(750);
  check('Success remains explicitly simulated',/No account was signed in/.test(await page.locator('#form-status').innerText()));
  await page.locator('.demo-enter').click();check('Success connects to original owner concept',await page.locator('#persona').inputValue()==='owner');
  await page.goto(url+'/welcome.html#signin');await page.locator('[data-view="recovery"]').click();await page.locator('.submit').click();await page.waitForTimeout(750);
  check('Recovery is generic and sends no email',/If an account exists/.test(await page.locator('#form-status').innerText()));
  await page.locator('[data-view="signin"]').click();await page.locator('[data-boundary="registration"]').click();
  check('Registration is a labelled scope boundary',await page.locator('#boundary').isVisible());
  await page.keyboard.press('Escape');check('Dialog restores trigger focus',await page.locator('[data-boundary="registration"]').evaluate(e=>e===document.activeElement));
  await page.locator('[data-boundary="statistics"]').click();check('Existing statistics are retained as secondary destination',/existing public statistics page/.test(await page.locator('#boundary-copy').innerText()));await page.keyboard.press('Escape');
  await page.setViewportSize({width:360,height:440});await page.locator('#password').focus();await page.locator('#password').scrollIntoViewIfNeeded();
  check('Password fits short viewport',await page.locator('#password').evaluate(e=>{const r=e.getBoundingClientRect();return r.top>=0&&r.bottom<=innerHeight;}));
  await page.locator('.submit').scrollIntoViewIfNeeded();check('Primary action remains reachable in short viewport',await page.locator('.submit').isVisible());
  await page.setViewportSize({width:390,height:844});await page.locator('[data-action="language"]').click();
  check('Arabic language and direction change together',await page.locator('html').getAttribute('lang')==='ar'&&await page.locator('html').getAttribute('dir')==='rtl');
  check('Email stays LTR',await page.locator('#email').getAttribute('dir')==='ltr');
  await page.emulateMedia({reducedMotion:'reduce'});check('Reduced motion disables transitions',await page.locator('.submit').evaluate(e=>getComputedStyle(e).transitionDuration==='0s'));
  await page.goto(url+'/welcome.html#signin');await page.locator('#email').focus();await page.keyboard.press('Tab');check('Keyboard moves from email to password',await page.locator('#password').evaluate(e=>e===document.activeElement));
  await page.keyboard.press('Tab');check('Password toggle is keyboard reachable',await page.locator('[data-action="reveal"]').evaluate(e=>e===document.activeElement));
  check('No persistent browser storage',await page.evaluate(()=>localStorage.length===0&&sessionStorage.length===0));
  check('No service workers',(await page.evaluate(()=>navigator.serviceWorker.getRegistrations())).length===0);
  check('No external requests',external.length===0);check('No runtime or console errors',errors.length===0);
  fs.writeFileSync(path.join(__dirname,'entry-results.json'),JSON.stringify({status:'PASS',date:new Date().toISOString(),browser:browser.version(),checks,errors,external},null,2));
  console.log(`Entry design checks: ${checks.length} PASS`);
 } catch(error){await page.screenshot({path:path.join(root,'screenshots','entry-failure.png'),fullPage:true});throw error;}finally{await browser.close();}
})();
