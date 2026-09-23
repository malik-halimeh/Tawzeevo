/* Public-entry design study. No authentication, network, persistence or production routing. */
(() => {
  'use strict';
  const $ = (s) => document.querySelector(s);
  const params = new URLSearchParams(location.search);
  let lang = params.get('lang') === 'ar' ? 'ar' : 'en';
  const hashView = () => ['signin','recovery'].includes(location.hash.slice(1)) ? location.hash.slice(1) : 'home';
  let view = hashView();
  let scenario = 'normal', timer = 0;
  let focusBeforeDialog;
  const t = (en, ar) => lang === 'ar' ? ar : en;
  const paths = {
    box:'<path d="m12 3 9 5v9l-9 5-9-5V8Zm-9 5 9 5 9-5m-9 5v9M7 5.8l10 5.4"/>',
    invoice:'<path d="M5 3h10l4 4v14H5Zm10 0v5h4M8 12h8m-8 4h5"/>',
    shop:'<path d="M4 10v11h16V10M3 3h18l1 7a3 3 0 0 1-5 1 3 3 0 0 1-5 0 3 3 0 0 1-5 0 3 3 0 0 1-5-1Zm6 18v-6h6v6"/>',
    van:'<path d="M2 6h12v11H2Zm12 4h4l4 4v3h-8M17 10v4h5"/><circle cx="6" cy="18" r="2"/><circle cx="18" cy="18" r="2"/>',
    pin:'<path d="M20 10c0 6-8 11-8 11S4 16 4 10a8 8 0 1 1 16 0Z"/><circle cx="12" cy="10" r="2.5"/>',
    arrow:'<path d="M4 12h16m-6-6 6 6-6 6"/>',
    check:'<path d="m5 12 4 4L19 6"/>',
    person:'<circle cx="12" cy="7" r="4"/><path d="M4 22v-3a8 8 0 0 1 16 0v3"/>',
    email:'<rect x="3" y="5" width="18" height="14" rx="2"/><path d="m3 6 9 7 9-7"/>',
    lock:'<rect x="5" y="10" width="14" height="11" rx="2"/><path d="M8 10V6a4 4 0 0 1 8 0v4m-4 4v3"/>',
    sun:'<circle cx="12" cy="12" r="4"/><path d="M12 1v3m0 16v3M1 12h3m16 0h3M4 4l2 2m12 12 2 2M4 20l2-2M18 6l2-2"/>',
    eye:'<path d="M2 12s4-7 10-7 10 7 10 7-4 7-10 7S2 12 2 12Z"/><circle cx="12" cy="12" r="3"/>'
  };
  const icon = (key, cls='') => `<svg class="icon ${cls}" aria-hidden="true" viewBox="0 0 24 24">${paths[key]}</svg>`;
  const brand = () => '<span class="brand-symbol" aria-hidden="true"><i></i><i></i><i></i></span><bdi>Tawzeevo</bdi>';
  const link = (label, page, cls='') => `<a class="${cls}" href="#${page}" data-view="${page}">${label}</a>`;
  function mural() {
    return `<div class="mural" aria-hidden="true"><svg class="mural-path" viewBox="0 0 500 400"><path d="M70 80h220q60 0 60 60v60q0 50-60 50H150q-65 0-65 60h340"/><circle cx="70" cy="80" r="7"/><circle cx="425" cy="310" r="7"/></svg>${['shop','invoice','box','van','pin','sun'].map((k,i)=>`<span class="mural-icon m${i}">${icon(k)}</span>`).join('')}<div class="mural-message">${icon('check')}<span>${t('Everything has its place.','لكل تفصيل مكانه.')}</span></div></div>`;
  }
  function header() {
    return `<header class="site-header"><a href="#home" data-view="home" class="brand" aria-label="${t('Tawzeevo home','توزيفو — الرئيسية')}">${brand()}</a><nav aria-label="${t('Main navigation','التنقل الرئيسي')}">${view==='home'?'<a class="how-link" href="#how">'+t('How it works','كيف يعمل')+'</a>':link(t('About Tawzeevo','عن توزيڤو'),'home','about-link')}<button data-action="language" class="language" lang="${lang==='en'?'ar':'en'}">${lang==='en'?'العربية':'English'}</button>${view==='home'?link(t('Sign in','تسجيل الدخول'),'signin','button primary small'):''}</nav></header>`;
  }
  function board() {
    return `<div class="day-board"><div class="board-top"><span>${icon('sun')} ${t('A day with Tawzeevo','يوم مع توزيڤو')}</span><small>${t('Illustrative preview','مثال توضيحي')}</small></div><div class="board-title"><h2>${t('From the first order<br>to the last stop.','من أول طلب<br>إلى آخر زيارة.')}</h2><span class="board-date">${icon('van')}</span></div><div class="board-route"><div class="route-row"><span class="route-icon">${icon('shop')}</span><div><strong>${t('An order comes in','يصلك طلب')}</strong><p>${t('Your storefront brings it to you.','متجرك يوصله إليك.')}</p></div></div><div class="route-row"><span class="route-icon">${icon('invoice')}</span><div><strong>${t('You review the details','تراجع التفاصيل')}</strong><p>${t('Confirm the invoice. Set the delivery date.','تؤكد الفاتورة وتحدد موعد التسليم.')}</p></div></div><div class="route-row"><span class="route-icon blue">${icon('van')}</span><div><strong>${t('Your next stop is clear','زيارتك التالية واضحة')}</strong><p>${t('Customer, items and address, together.','العميل والأصناف والعنوان، معاً.')}</p></div></div></div><a class="board-action" href="index.html"><span><small>${t('SEE IT IN ACTION','شاهد التجربة')}</small><strong>${t('Open a sample workday','افتح يوم عمل تجريبي')}</strong></span>${icon('arrow','directional')}</a></div>`;
  }
  function home() {
    return `<main id="main" tabindex="-1"><section class="hero"><div class="hero-copy"><p class="eyebrow">${icon('box')}${t('BUILT AROUND YOUR BUSINESS DAY','حول تفاصيل يوم عملك')}</p><h1>${t('Your business.<br><span>A clearer day.</span>','أعمالك.<br><span>ويومك أوضح.</span>')}</h1><p class="lead">${t('Orders, customers and deliveries, connected. Run your distribution business from your phone, with room to work at your desk.','طلباتك وعملاؤك وتوصيلاتك، في مكان واحد. أدر أعمال التوزيع من هاتفك، وتابع التفاصيل من مكتبك.')}</p><div class="hero-actions">${link(t('Sign in to your workspace','ادخل إلى مساحة عملك')+icon('arrow','directional'),'signin','button primary')}<a class="text-link" href="#how">${t('Take a closer look','تعرّف على التجربة')}</a></div><p class="quiet-note">${t('For the owner on the road. And the team beside them.','للمالك على الطريق، وللفريق الذي يعمل معه.')}</p></div><div class="hero-art"><div class="art-sun" aria-hidden="true">${icon('sun')}</div>${board()}</div></section><section id="how" class="workflow" aria-labelledby="workflow-title"><div class="section-heading"><p class="eyebrow">${t('LESS TO KEEP IN YOUR HEAD','تفاصيل أقل تشغل بالك')}</p><h2 id="workflow-title">${t('The details, together.<br>The next step, in reach.','التفاصيل معاً.<br>والخطوة التالية بمتناولك.')}</h2></div><div class="feature-grid">${[
      ['person','Know the customer.','اعرف عميلك.','Contact details, invoices and recorded payments stay connected to each customer.','تفاصيل التواصل والفواتير والدفعات المسجّلة، مرتبطة بكل عميل.'],
      ['van','Keep the day moving.','تابع يومك بوضوح.','Work through assigned stops with the address and delivery details close at hand.','تابع الزيارات المسندة إليك، والعنوان وتفاصيل التسليم أمامك.'],
      ['shop','Let orders come to you.','دع الطلبات تصل إليك.','A storefront in your business’s name. Customers can order as guests; you review and confirm.','متجر باسم نشاطك. يطلب العملاء كضيوف، وأنت تراجع الطلبات وتؤكدها.']
    ].map(([key,en,ar,copy,copyAr])=>`<article><span class="feature-icon">${icon(key)}</span><h3>${t(en,ar)}</h3><p>${t(copy,copyAr)}</p></article>`).join('')}</div></section><section class="closing"><div><p class="eyebrow">${t('ON YOUR OWN, OR WITH A TEAM','بمفردك أو مع فريقك')}</p><h2>${t('Your business. Your way of working.','أعمالك، على طريقتك.')}</h2><p>${t('Deliver yourself or assign stops to a driver. Your customers can use your storefront without a business sign-in.','سلّم الطلبات بنفسك أو أسند الزيارات إلى سائق. ويمكن لعملائك الطلب من متجرك دون تسجيل دخول خاص بالأعمال.')}</p></div>${link(t('Welcome back','أهلاً بعودتك')+icon('arrow','directional'),'signin','button primary')}</section></main>`;
  }
  function field(id,label,key,type,value,auto) {
    return `<div class="field"><label for="${id}">${label}</label><div class="input-shell">${icon(key)}<input id="${id}" name="${id}" type="${type}" value="${value}" autocomplete="${auto}" dir="ltr" aria-describedby="${id}-error" ${id==='email'?'inputmode="email"':''}>${id==='password'?`<button type="button" class="reveal" data-action="reveal" aria-label="${t('Show password','إظهار كلمة المرور')}" aria-pressed="false">${icon('eye')}</button>`:''}</div><span class="field-error" id="${id}-error"></span></div>`;
  }
  function signin() {
    const recovery=view==='recovery';
    return `<main id="main" class="signin-layout" tabindex="-1"><aside class="signin-story"><p class="eyebrow">${t('YOUR DAY, CONNECTED','يومك، مترابط')}</p><h2>${t('A good day starts<br>with a clear<br>next step.','يومك أفضل<br>حين تكون خطوتك<br>التالية واضحة.')}</h2><p>${t('From the counter to the road, keep the details of your business close.','من المحل إلى الطريق، تبقى تفاصيل أعمالك قريبة منك.')}</p>${mural()}<div class="story-foot"><span>${icon('invoice')}${t('Orders','الطلبات')}</span><span>${icon('person')}${t('Customers','العملاء')}</span><span>${icon('van')}${t('Deliveries','التوصيلات')}</span></div></aside><section class="signin-panel" aria-labelledby="sign-title"><div class="form-intro"><span class="welcome-icon">${icon(recovery?'lock':'sun')}</span><p class="eyebrow">${t('TAWZEEVO WORKSPACE','مساحة عمل توزيڤو')}</p><h1 id="sign-title">${recovery?t('Let’s get you back in.','لنساعدك على العودة.'):t('Welcome back.','أهلاً بعودتك.')}</h1><p>${recovery?t('Enter your email to request a password reset.','أدخل بريدك الإلكتروني لطلب إعادة تعيين كلمة المرور.'):t('Sign in to continue your workday.','سجّل دخولك لمتابعة يوم عملك.')}</p></div><div class="sample-notice">${icon('info' in paths?'info':'lock')}<span>${t('Design preview. Use the sample details below; do not enter real credentials.','معاينة تصميم. استخدم البيانات التجريبية أدناه؛ لا تُدخل بيانات دخول حقيقية.')}</span></div><div id="form-status" role="status" tabindex="-1"></div><form id="signin-form" novalidate>${field('email',t('Email address','البريد الإلكتروني'),'email','email','rami@example.invalid','off')}${recovery?'':field('password',t('Password','كلمة المرور'),'lock','password','daylight-demo','off')}${recovery?'':`<div class="form-options">${link(t('Forgot password?','نسيت كلمة المرور؟'),'recovery')}</div>`}<button type="submit" class="button primary submit">${recovery?t('Send reset link','أرسل رابط إعادة التعيين'):t('Sign in','تسجيل الدخول')}${icon('arrow','directional')}</button></form><div id="after-form">${recovery?link(t('Back to sign in','العودة إلى تسجيل الدخول'),'signin','back-signin'):`<p class="register-note">${t('New to Tawzeevo?','جديد على توزيڤو؟')} <button class="inline-button" data-boundary="registration">${t('Create an account','أنشئ حساباً')}</button></p><div class="customer-note">${icon('shop')}<p><strong>${t('Here to place an order?','هنا لتطلب من أحد المتاجر؟')}</strong><span>${t('Open the storefront link shared by your supplier. Guest checkout is available there.','افتح رابط المتجر الذي شاركه مورّدك. يمكنك إتمام الطلب كضيف هناك.')}</span></p></div>`}</div></section></main>`;
  }
  function footer() {return `<footer class="site-footer"><span>${t('Tawzeevo · A clearer working day.','توزيڤو · ليوم عمل أوضح.')}</span><div><button data-boundary="statistics">${t('Public statistics','الإحصاءات العامة')}</button><a href="index.html">${t('Explore the workspace preview','استكشف نموذج مساحة العمل')}</a></div></footer>`;}
  function render(focus=false) {
    clearTimeout(timer);
    document.documentElement.lang=lang;document.documentElement.dir=lang==='ar'?'rtl':'ltr';
    document.title=t('Tawzeevo · '+(view==='home'?'A clearer day':'Welcome back'),'توزيڤو · '+(view==='home'?'يومك أوضح':'أهلاً بعودتك'));
    $('#preview').innerHTML=`<aside class="preview-strip" aria-label="${t('Design preview controls','أدوات معاينة التصميم')}"><span>DAYLIGHT <span class="preview-label">/ ${t('PUBLIC ENTRY CONCEPT','تصميم الصفحات العامة')}</span></span><div><label for="entry-state">${t('Form state','حالة النموذج')}</label><select id="entry-state">${[['normal',t('Normal','عادي')],['failure',t('Sign-in error','خطأ في الدخول')],['offline',t('Offline','غير متصل')],['loading',t('Loading','جارٍ التحميل')]].map(([v,l])=>`<option value="${v}" ${scenario===v?'selected':''}>${l}</option>`).join('')}</select><button data-action="reset">${t('Reset','إعادة ضبط')}</button></div></aside>`;
    $('#entry').innerHTML=header()+(view==='home'?home():signin())+footer();
    if(focus) { $('#main').focus(); window.scrollTo(0,0); }
  }
  function navigate(next) {view=next; history.replaceState(null,'','#'+next);render(true);}
  function status(text,kind='error') {$('#form-status').className='form-status '+kind;$('#form-status').textContent=text;$('#form-status').focus();}
  function boundary(kind) {
    focusBeforeDialog=document.activeElement;
    $('#boundary-title').textContent=kind==='statistics'?t('Public statistics remain available.','الإحصاءات العامة تبقى متاحة.'):t('Account creation','إنشاء حساب');
    $('#boundary-copy').textContent=kind==='statistics'?t('In the application, this link opens the existing public statistics page. This design preview does not load live statistics or invent platform numbers.','في التطبيق، يفتح هذا الرابط صفحة الإحصاءات العامة الحالية. لا تحمّل معاينة التصميم إحصاءات مباشرة ولا تعرض أرقاماً افتراضية للمنصة.'):t('In the application, this link opens the existing registration form. Account creation is outside this design preview.','في التطبيق، يفتح هذا الرابط نموذج التسجيل الحالي. إنشاء الحسابات خارج نطاق معاينة التصميم هذه.');
    $('#close-boundary').textContent=t('Back to preview','العودة إلى المعاينة');$('#boundary').showModal();
  }
  document.addEventListener('click',(event)=>{
    const target=event.target.closest('[data-view],[data-action],[data-boundary]');if(!target)return;
    if(target.dataset.view){event.preventDefault();navigate(target.dataset.view);return;}
    if(target.dataset.boundary){boundary(target.dataset.boundary);return;}
    if(target.dataset.action==='language') {lang=lang==='en'?'ar':'en';render();$('[data-action="language"]').focus();}
    if(target.dataset.action==='reset') {scenario='normal';render();$('[data-action="reset"]').focus();}
    if(target.dataset.action==='reveal') {const input=$('#password');const show=input.type==='password';input.type=show?'text':'password';target.setAttribute('aria-pressed',String(show));target.setAttribute('aria-label',show?t('Hide password','إخفاء كلمة المرور'):t('Show password','إظهار كلمة المرور'));}
  });
  $('#close-boundary').addEventListener('click',()=>$('#boundary').close());
  $('#boundary').addEventListener('close',()=>focusBeforeDialog?.focus());
  document.addEventListener('change',(event)=>{if(event.target.id==='entry-state'){scenario=event.target.value;if(view==='home')navigate('signin');else render();$('#entry-state').focus();}});
  document.addEventListener('submit',(event)=>{
    if(event.target.id!=='signin-form')return;event.preventDefault();
    const email=$('#email'), password=$('#password');
    const errors=[];
    if(!email.value.trim()||!email.validity.valid)errors.push([email,t('Enter a valid email address.','أدخل بريداً إلكترونياً صالحاً.')]);
    if(password&&!password.value)errors.push([password,t('Enter your password.','أدخل كلمة المرور.')]);
    for(const input of [email,password].filter(Boolean)){input.removeAttribute('aria-invalid');$('#'+input.id+'-error').textContent='';}
    if(errors.length){for(const [input,message] of errors){input.setAttribute('aria-invalid','true');$('#'+input.id+'-error').textContent=message;}errors[0][0].focus();return;}
    if(email.value!=='rami@example.invalid'||(password&&password.value!=='daylight-demo')) {status(t('Use the sample email and password. Reset restores them. No sign-in request was sent.','استخدم البريد وكلمة المرور التجريبيين. زر إعادة الضبط يعيدهما. لم يُرسَل أي طلب دخول.'));return;}
    if(scenario==='offline'){status(t('You’re offline. Reconnect before signing in.','أنت غير متصل. اتصل بالإنترنت قبل تسجيل الدخول.'));return;}
    const submit=$('.submit');submit.disabled=true;submit.textContent=t('Please wait…','يرجى الانتظار…');$('#signin-form').setAttribute('aria-busy','true');
    $('#live').textContent=t('Processing preview.','جارٍ معالجة المعاينة.');
    if(scenario==='loading')return;
    timer=setTimeout(()=>{
      $('#signin-form').removeAttribute('aria-busy');submit.disabled=false;submit.textContent=view==='recovery'?t('Send reset link','أرسل رابط إعادة التعيين'):t('Sign in','تسجيل الدخول');
      if(scenario==='failure'){status(t('Sign-in failed. Check your email and password and try again.','تعذّر تسجيل الدخول. تحقق من البريد وكلمة المرور وحاول مجدداً.'));return;}
      $('#signin-form').hidden=true;$('#after-form').hidden=true;
      if(view==='recovery'){status(t('If an account exists for that address, a reset link will be sent. Preview only: no email was sent.','إذا وُجد حساب بهذا البريد، سيُرسَل رابط إعادة تعيين. هذه معاينة فقط: لم يُرسَل بريد.'),'success');$('#after-form').hidden=false;}
      else {status(t('Preview complete. Your sample workday is ready. No account was signed in.','اكتملت المعاينة. يوم عملك التجريبي جاهز. لم يتم الدخول إلى أي حساب.'),'success');$('#form-status').insertAdjacentHTML('afterend',`<a class="button primary demo-enter" href="index.html">${t('Open sample workspace','افتح مساحة العمل التجريبية')}${icon('arrow','directional')}</a>`);}
    },650);
  });
  window.addEventListener('hashchange',()=>{if(['','#home','#signin','#recovery'].includes(location.hash)){view=hashView();render(true);}});
  render();
})();
