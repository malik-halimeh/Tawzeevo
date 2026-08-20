import { FormEvent, useRef, useState } from "react";
import { useTranslation } from "react-i18next";

import "./demo.css";

const roles = ["guest", "customer", "owner", "driver"] as const;
type DemoRole = (typeof roles)[number];
type DemoLanguage = "en" | "ar";
type CategoryId = "all" | "pantry" | "home" | "drinks";

interface DemoProduct {
  id: string;
  category: Exclude<CategoryId, "all">;
  name: Record<DemoLanguage, string>;
  detail: Record<DemoLanguage, string>;
  price: string;
  mark: string;
  tone: string;
}

interface CheckoutDetails { name: string; phone: string; address: string; }

const products: readonly DemoProduct[] = [
  { id: "tomato", category: "pantry", name: { en: "Tomato paste", ar: "معجون طماطم" }, detail: { en: "660 g · piece", ar: "660 غ · حبة" }, price: "165,000 LBP", mark: "TP", tone: "coral" },
  { id: "oil", category: "pantry", name: { en: "Sunflower oil", ar: "زيت دوار الشمس" }, detail: { en: "1.5 L · piece", ar: "1.5 ل · حبة" }, price: "235,000 LBP", mark: "SO", tone: "gold" },
  { id: "cleaner", category: "home", name: { en: "Laundry gel", ar: "جل للغسيل" }, detail: { en: "2 L · piece", ar: "2 ل · حبة" }, price: "310,000 LBP", mark: "LG", tone: "blue" },
  { id: "water", category: "drinks", name: { en: "Sparkling water", ar: "مياه غازية" }, detail: { en: "6 × 1.5 L · pack", ar: "6 × 1.5 ل · عبوة" }, price: "190,000 LBP", mark: "SW", tone: "mint" },
] as const;

const categories: readonly CategoryId[] = ["all", "pantry", "home", "drinks"];

const copy = {
  en: {
    brandHome: "Tawzeevo home", skip: "Skip to demo content", language: "العربية",
    preview: "Synthetic preview", privacy: "Nothing on this page is saved or sent.",
    eyebrow: "Four perspectives · one distribution route", title: "See Tawzeevo from every stop.",
    intro: "Explore how one catalog moves from browsing to an order-facing view, then switch perspectives without touching live data.",
    selector: "Choose a demo perspective", reset: "Reset preview",
    roles: {
      guest: { label: "Guest", description: "An unauthenticated storefront visitor browsing a synthetic catalog." },
      customer: { label: "Customer", description: "A guest who supplied checkout details and is viewing a synthetic order-facing state." },
      owner: { label: "Owner", description: "A client account with owner membership in one tenant, able to oversee that tenant's work." },
      driver: { label: "Driver", description: "A least-privileged tenant member viewing only assigned operational work." },
    },
    guest: {
      kicker: "Public storefront · no sign-in", title: "Browse the van catalog",
      body: "Published products and tenant prices are presented by category. Add an item to begin a memory-only checkout.",
      categoryLabel: "Catalog categories", categories: { all: "All products", pantry: "Pantry", home: "Home care", drinks: "Drinks" },
      add: "Add to basket", basket: "Basket", emptyBasket: "Choose a product from the shelf to begin.", review: "Review checkout",
      checkoutTitle: "Where should this order go?", checkoutBody: "Only these three details are needed for this guest checkout preview.",
      name: "Name", phone: "Phone", address: "Address", placeOrder: "Place preview order", back: "Back to catalog",
      required: "Enter {{field}} to continue.", productShelf: "Product shelf",
    },
    customer: {
      kicker: "Order-facing view · no customer login", title: "Order received",
      body: "The business can review the items before confirmation. A delivery date, if needed, is set by the owner after confirmation.",
      reference: "Preview reference", contact: "Customer details", items: "Order items", request: "Request cancellation",
      requested: "Cancellation requested", requestedBody: "The request is waiting for the owner to approve or reject it.",
      demoName: "Rana Haddad", demoPhone: "+961 70 123 456", demoAddress: "Hamra, Beirut",
    },
    owner: {
      kicker: "Approved tenant · synthetic workspace", title: "Owner workbench",
      body: "A client system account working through an owner tenant membership, with the commercial context needed to prepare a draft.",
      tenant: "Cedar Route Distribution", tenantState: "Active tenant", context: "Tenant context",
      systemType: "System type", systemValue: "Client", membership: "Tenant membership", membershipValue: "Owner",
      assignee: "Operational assignee", assigneeValue: "Nadim Khoury · Owner membership",
      assigneeNote: "One owner can operate the Cash Van; no separate driver account is required.",
      customerStep: "1 · Find customer", customerPhone: "Customer phone", findCustomer: "Find customer",
      customerName: "Leila Mansour", customerGrade: "Grade A", customerAddress: "Mar Elias, Beirut",
      productStep: "2 · Resolve product", barcode: "Barcode", resolveBarcode: "Resolve barcode",
      productName: "Tomato paste", productDetail: "660 g", piecePrice: "Piece price", boxPrice: "Box price",
      piecesPerBox: "12 pieces per box", addToDraft: "Add to draft",
      draftStep: "3 · Draft invoice", draftTitle: "Draft invoice", draftState: "Draft",
      draftEmpty: "Resolve a barcode, then add the product here.", draftLine: "Tomato paste · 2 pieces",
      previewNote: "Synthetic invoice workspace · nothing is saved.",
    },
    driver: {
      kicker: "Assigned operations · synthetic workspace", title: "Driver route sheet",
      body: "Only the stops assigned to this driver membership and the details needed to complete them appear here.",
      tenant: "Cedar Route Distribution", membership: "Tenant membership", membershipValue: "Driver",
      driverName: "Samir Rahal", routeLabel: "Assigned route · Thursday", stopCount: "2 assigned stops",
      scopeNote: "Customer and invoice details appear only where needed for this assignment.",
      sequence: "Assigned stop order", stop: "Stop", assigned: "Assigned", viewDetails: "View stop details", hideDetails: "Hide stop details",
      contact: "Customer contact", invoice: "Invoice reference", note: "Delivery note",
      previewNote: "Internal operational preview · nothing is saved.",
      stops: [
        { name: "Maya Saleh", area: "Achrafieh, Beirut", phone: "+961 71 456 789", invoice: "INV-1048", note: "Call on arrival and use the main entrance." },
        { name: "Karim Nassar", area: "Hamra, Beirut", phone: "+961 70 882 114", invoice: "INV-1051", note: "Reception desk accepts the delivery." },
      ],
    },
    later: { kicker: "Boundary preview", title: "Detailed view arrives in its demo milestone" },
  },
  ar: {
    brandHome: "الصفحة الرئيسية لتوزيفو", skip: "انتقل إلى محتوى العرض", language: "English",
    preview: "معاينة ببيانات تجريبية", privacy: "لا يتم حفظ أو إرسال أي شيء في هذه الصفحة.",
    eyebrow: "أربع وجهات نظر · مسار توزيع واحد", title: "شاهد توزيـفو من كل محطة.",
    intro: "استكشف انتقال الكتالوج من التصفح إلى عرض الطلب، ثم بدّل المنظور من دون لمس البيانات الفعلية.",
    selector: "اختر منظوراً للعرض", reset: "إعادة ضبط المعاينة",
    roles: {
      guest: { label: "زائر", description: "زائر متجر غير مسجل يتصفح كتالوجاً تجريبياً." },
      customer: { label: "عميل", description: "زائر أدخل بيانات الطلب ويشاهد حالة طلب تجريبية." },
      owner: { label: "مالك", description: "حساب عميل بعضوية مالك في منشأة واحدة ويشرف على عملها." },
      driver: { label: "سائق", description: "عضو منشأة بصلاحيات محدودة يرى فقط العمل المسند إليه." },
    },
    guest: {
      kicker: "متجر عام · من دون تسجيل دخول", title: "تصفّح كتالوج السيارة",
      body: "تُعرض المنتجات المنشورة وأسعار المنشأة بحسب الفئة. أضف منتجاً لبدء طلب تجريبي محفوظ في الذاكرة فقط.",
      categoryLabel: "فئات الكتالوج", categories: { all: "كل المنتجات", pantry: "مونة", home: "عناية منزلية", drinks: "مشروبات" },
      add: "أضف إلى السلة", basket: "السلة", emptyBasket: "اختر منتجاً من الرف للبدء.", review: "مراجعة بيانات الطلب",
      checkoutTitle: "إلى أين نرسل هذا الطلب؟", checkoutBody: "هذه البيانات الثلاثة فقط مطلوبة في معاينة طلب الزائر.",
      name: "الاسم", phone: "الهاتف", address: "العنوان", placeOrder: "إنشاء طلب تجريبي", back: "العودة إلى الكتالوج",
      required: "أدخل {{field}} للمتابعة.", productShelf: "رف المنتجات",
    },
    customer: {
      kicker: "عرض الطلب · من دون دخول للعميل", title: "تم استلام الطلب",
      body: "يمكن للمنشأة مراجعة المنتجات قبل التأكيد. يحدد المالك موعد التوصيل، عند الحاجة، بعد التأكيد.",
      reference: "مرجع تجريبي", contact: "بيانات العميل", items: "منتجات الطلب", request: "طلب الإلغاء",
      requested: "تم طلب الإلغاء", requestedBody: "ينتظر الطلب موافقة المالك أو رفضه.",
      demoName: "رنا حداد", demoPhone: "+961 70 123 456", demoAddress: "الحمرا، بيروت",
    },
    owner: {
      kicker: "منشأة مقبولة · مساحة تجريبية", title: "منضدة عمل المالك",
      body: "حساب نظام من نوع عميل يعمل عبر عضوية مالك في المنشأة، مع السياق التجاري اللازم لإعداد مسودة.",
      tenant: "توزيع طريق الأرز", tenantState: "منشأة نشطة", context: "سياق المنشأة",
      systemType: "نوع النظام", systemValue: "عميل", membership: "عضوية المنشأة", membershipValue: "مالك",
      assignee: "المكلّف بالتشغيل", assigneeValue: "نديم خوري · عضوية مالك",
      assigneeNote: "يمكن لمالك واحد تشغيل سيارة التوزيع، ولا حاجة إلى حساب سائق منفصل.",
      customerStep: "1 · البحث عن عميل", customerPhone: "هاتف العميل", findCustomer: "البحث عن العميل",
      customerName: "ليلى منصور", customerGrade: "الفئة A", customerAddress: "مار الياس، بيروت",
      productStep: "2 · تحديد المنتج", barcode: "الباركود", resolveBarcode: "قراءة الباركود",
      productName: "معجون طماطم", productDetail: "660 غ", piecePrice: "سعر الحبة", boxPrice: "سعر الصندوق",
      piecesPerBox: "12 حبة في الصندوق", addToDraft: "إضافة إلى المسودة",
      draftStep: "3 · مسودة الفاتورة", draftTitle: "مسودة فاتورة", draftState: "مسودة",
      draftEmpty: "اقرأ باركوداً، ثم أضف المنتج هنا.", draftLine: "معجون طماطم · حبتان",
      previewNote: "مساحة فاتورة تجريبية · لا يتم حفظ شيء.",
    },
    driver: {
      kicker: "عمليات مسندة · مساحة تجريبية", title: "ورقة مسار السائق",
      body: "تظهر هنا فقط المحطات المسندة إلى عضوية هذا السائق والتفاصيل اللازمة لإكمالها.",
      tenant: "توزيع طريق الأرز", membership: "عضوية المنشأة", membershipValue: "سائق",
      driverName: "سمير رحال", routeLabel: "مسار مسند · الخميس", stopCount: "محطتان مسندتان",
      scopeNote: "تظهر بيانات العميل والفاتورة فقط عند الحاجة إليها ضمن هذا التكليف.",
      sequence: "ترتيب المحطات المسندة", stop: "المحطة", assigned: "مسندة", viewDetails: "عرض تفاصيل المحطة", hideDetails: "إخفاء تفاصيل المحطة",
      contact: "تواصل العميل", invoice: "مرجع الفاتورة", note: "ملاحظة التسليم",
      previewNote: "معاينة تشغيلية داخلية · لا يتم حفظ شيء.",
      stops: [
        { name: "مايا صالح", area: "الأشرفية، بيروت", phone: "+961 71 456 789", invoice: "INV-1048", note: "اتصل عند الوصول واستخدم المدخل الرئيسي." },
        { name: "كريم نصار", area: "الحمرا، بيروت", phone: "+961 70 882 114", invoice: "INV-1051", note: "يستلم مكتب الاستقبال الطلب." },
      ],
    },
    later: { kicker: "معاينة الحدود", title: "سيصل العرض المفصل في مرحلة العرض الخاصة به" },
  },
} as const;

function formatItemCount(language: DemoLanguage, count: number) {
  if (language === "ar") return count === 1 ? `${count} منتج` : `${count} منتجات`;
  return count === 1 ? `${count} item` : `${count} items`;
}

interface GuestViewProps {
  language: DemoLanguage;
  basket: string[];
  onAdd: (id: string) => void;
  onCheckout: (details: CheckoutDetails) => void;
}

function GuestView({ language, basket, onAdd, onCheckout }: GuestViewProps) {
  const text = copy[language].guest;
  const [category, setCategory] = useState<CategoryId>("all");
  const [checkoutOpen, setCheckoutOpen] = useState(false);
  const [details, setDetails] = useState<CheckoutDetails>({ name: "", phone: "", address: "" });
  const [errors, setErrors] = useState<Partial<Record<keyof CheckoutDetails, string>>>({});
  const visibleProducts = products.filter((product) => category === "all" || product.category === category);
  const basketProducts = basket.map((id) => products.find((product) => product.id === id)).filter((product): product is DemoProduct => Boolean(product));

  const submitCheckout = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const nextErrors: Partial<Record<keyof CheckoutDetails, string>> = {};
    (["name", "phone", "address"] as const).forEach((field) => {
      if (!details[field].trim()) nextErrors[field] = text.required.replace("{{field}}", text[field].toLocaleLowerCase(language));
    });
    setErrors(nextErrors);
    if (Object.keys(nextErrors).length === 0) onCheckout(details);
  };

  if (checkoutOpen) {
    return (
      <section aria-labelledby="demo-checkout-title" className="demo-checkout-view">
        <button className="text-button" onClick={() => setCheckoutOpen(false)} type="button">← {text.back}</button>
        <div className="demo-view-heading"><p className="section-kicker">{text.kicker}</p><h2 id="demo-checkout-title">{text.checkoutTitle}</h2><p>{text.checkoutBody}</p></div>
        <form className="demo-checkout-form" noValidate onSubmit={submitCheckout}>
          {(["name", "phone", "address"] as const).map((field) => (
            <label className="field" key={field}>
              <span>{text[field]}</span>
              <input aria-describedby={errors[field] ? `demo-${field}-error` : undefined} aria-invalid={Boolean(errors[field])} dir={field === "phone" ? "ltr" : undefined} name={field} onChange={(event) => setDetails((current) => ({ ...current, [field]: event.target.value }))} required type={field === "phone" ? "tel" : "text"} value={details[field]} />
              {errors[field] ? <small className="field-error" id={`demo-${field}-error`}>{errors[field]}</small> : null}
            </label>
          ))}
          <div className="demo-checkout-summary"><span>{text.basket}</span><strong>{formatItemCount(language, basketProducts.length)}</strong></div>
          <button className="button" type="submit">{text.placeOrder}</button>
        </form>
      </section>
    );
  }

  return (
    <section aria-labelledby="demo-guest-title" className="demo-storefront">
      <div className="demo-view-heading"><p className="section-kicker">{text.kicker}</p><h2 id="demo-guest-title">{text.title}</h2><p>{text.body}</p></div>
      <div aria-label={text.categoryLabel} className="demo-category-list">
        {categories.map((categoryId) => <button aria-pressed={category === categoryId} key={categoryId} onClick={() => setCategory(categoryId)} type="button">{text.categories[categoryId]}</button>)}
      </div>
      <div className="demo-shop-layout">
        <div aria-label={text.productShelf} className="demo-product-shelf">
          {visibleProducts.map((product) => (
            <article className="demo-product-card" key={product.id}>
              <div aria-hidden="true" className={`demo-product-visual tone-${product.tone}`}><span>{product.mark}</span></div>
              <div className="demo-product-copy"><span>{product.detail[language]}</span><h3>{product.name[language]}</h3><bdi dir="ltr">{product.price}</bdi></div>
              <button className="button button-secondary button-small" onClick={() => onAdd(product.id)} type="button">{text.add}<span aria-hidden="true">＋</span></button>
            </article>
          ))}
        </div>
        <aside aria-labelledby="demo-basket-title" className="demo-basket">
          <div><p className="section-kicker">{formatItemCount(language, basketProducts.length)}</p><h3 id="demo-basket-title">{text.basket}</h3></div>
          {basketProducts.length === 0 ? <p className="demo-basket-empty">{text.emptyBasket}</p> : <ol>{basketProducts.map((product, index) => <li key={`${product.id}-${index}`}><span>{product.name[language]}</span><bdi dir="ltr">{product.price}</bdi></li>)}</ol>}
          <button className="button" disabled={basketProducts.length === 0} onClick={() => setCheckoutOpen(true)} type="button">{text.review}</button>
        </aside>
      </div>
    </section>
  );
}

interface CustomerViewProps { language: DemoLanguage; details: CheckoutDetails | undefined; basket: string[]; }

function CustomerView({ language, details, basket }: CustomerViewProps) {
  const text = copy[language].customer;
  const [cancellationRequested, setCancellationRequested] = useState(false);
  const orderItems = basket.length > 0 ? basket : ["tomato", "water"];
  const orderProducts = orderItems.map((id) => products.find((product) => product.id === id)).filter((product): product is DemoProduct => Boolean(product));
  const customer = details ?? { name: text.demoName, phone: text.demoPhone, address: text.demoAddress };

  return (
    <section aria-labelledby="demo-customer-title" className="demo-customer-view">
      <div className="demo-view-heading"><p className="section-kicker">{text.kicker}</p><h2 id="demo-customer-title">{text.title}</h2><p>{text.body}</p></div>
      <div className="demo-order-ticket">
        <header><div><span>{text.reference}</span><strong>DEMO-1048</strong></div><span className="demo-order-stamp" aria-hidden="true">✓</span></header>
        <div className="demo-order-grid">
          <section aria-labelledby="demo-contact-title"><h3 id="demo-contact-title">{text.contact}</h3><strong>{customer.name}</strong><bdi dir="ltr">{customer.phone}</bdi><span>{customer.address}</span></section>
          <section aria-labelledby="demo-items-title"><h3 id="demo-items-title">{text.items}</h3><ol>{orderProducts.map((product, index) => <li key={`${product.id}-${index}`}><span>{product.name[language]}</span><bdi dir="ltr">{product.price}</bdi></li>)}</ol></section>
        </div>
        <footer>{cancellationRequested ? <div className="demo-requested" role="status"><strong>{text.requested}</strong><span>{text.requestedBody}</span></div> : <button className="button button-secondary" onClick={() => setCancellationRequested(true)} type="button">{text.request}</button>}</footer>
      </div>
    </section>
  );
}

function OwnerView({ language }: { language: DemoLanguage }) {
  const text = copy[language].owner;
  const [customerFound, setCustomerFound] = useState(false);
  const [productResolved, setProductResolved] = useState(false);
  const [draftAdded, setDraftAdded] = useState(false);

  return (
    <section aria-labelledby="demo-owner-title" className="demo-owner-view">
      <div className="demo-view-heading">
        <p className="section-kicker">{text.kicker}</p>
        <h2 id="demo-owner-title">{text.title}</h2>
        <p>{text.body}</p>
      </div>

      <section aria-label={text.context} className="demo-owner-context">
        <div className="demo-tenant-heading">
          <span aria-hidden="true">CR</span>
          <div><strong>{text.tenant}</strong><small>{text.tenantState}</small></div>
        </div>
        <dl>
          <div><dt>{text.systemType}</dt><dd>{text.systemValue}</dd></div>
          <div><dt>{text.membership}</dt><dd>{text.membershipValue}</dd></div>
        </dl>
        <div className="demo-assignment-card">
          <span>{text.assignee}</span>
          <strong>{text.assigneeValue}</strong>
          <small>{text.assigneeNote}</small>
        </div>
      </section>

      <div className="demo-owner-workbench">
        <section aria-labelledby="demo-owner-customer-title" className="demo-workbench-card">
          <p className="section-kicker" id="demo-owner-customer-title">{text.customerStep}</p>
          <label className="field">
            <span>{text.customerPhone}</span>
            <input defaultValue="+961 70 555 018" dir="ltr" type="tel" />
          </label>
          <button className="button button-secondary button-small" onClick={() => setCustomerFound(true)} type="button">{text.findCustomer}</button>
          {customerFound ? (
            <div className="demo-found-record" role="status">
              <span aria-hidden="true">LM</span>
              <div><strong>{text.customerName}</strong><small>{text.customerGrade}</small><small>{text.customerAddress}</small></div>
            </div>
          ) : null}
        </section>

        <section aria-labelledby="demo-owner-product-title" className="demo-workbench-card">
          <p className="section-kicker" id="demo-owner-product-title">{text.productStep}</p>
          <label className="field">
            <span>{text.barcode}</span>
            <input defaultValue="5285001234567" dir="ltr" inputMode="numeric" type="text" />
          </label>
          <button className="button button-secondary button-small" onClick={() => setProductResolved(true)} type="button">{text.resolveBarcode}</button>
          {productResolved ? (
            <div className="demo-resolved-product" role="status">
              <div aria-hidden="true" className="demo-product-visual tone-coral"><span>TP</span></div>
              <div className="demo-resolved-copy">
                <small>{text.productDetail}</small><strong>{text.productName}</strong><bdi dir="ltr">5285001234567</bdi>
              </div>
              <dl>
                <div><dt>{text.piecePrice}</dt><dd><bdi dir="ltr">165,000 LBP</bdi></dd></div>
                <div><dt>{text.boxPrice}</dt><dd><bdi dir="ltr">1,980,000 LBP</bdi><small>{text.piecesPerBox}</small></dd></div>
              </dl>
              <button className="button button-small" onClick={() => setDraftAdded(true)} type="button">{text.addToDraft}</button>
            </div>
          ) : null}
        </section>

        <section aria-labelledby="demo-owner-draft-title" className="demo-draft-card">
          <div className="demo-draft-header">
            <div><p className="section-kicker">{text.draftStep}</p><h3 id="demo-owner-draft-title">{text.draftTitle}</h3></div>
            <span className="status-badge status-pending">{text.draftState}</span>
          </div>
          {draftAdded ? (
            <div className="demo-draft-line" aria-live="polite">
              <div><strong>{text.productName}</strong><span>{text.draftLine}</span></div>
              <bdi dir="ltr">2 × 165,000 LBP</bdi>
            </div>
          ) : <p className="demo-draft-empty">{text.draftEmpty}</p>}
          <footer>{text.previewNote}</footer>
        </section>
      </div>
    </section>
  );
}

function DriverView({ language }: { language: DemoLanguage }) {
  const text = copy[language].driver;
  const [openStop, setOpenStop] = useState<number | null>(null);

  return (
    <section aria-labelledby="demo-driver-title" className="demo-driver-view">
      <div className="demo-view-heading">
        <p className="section-kicker">{text.kicker}</p>
        <h2 id="demo-driver-title">{text.title}</h2>
        <p>{text.body}</p>
      </div>

      <section aria-label={text.membership} className="demo-driver-context">
        <div className="demo-driver-identity">
          <span aria-hidden="true">SR</span>
          <div><strong>{text.driverName}</strong><small>{text.tenant}</small></div>
        </div>
        <dl>
          <div><dt>{text.membership}</dt><dd>{text.membershipValue}</dd></div>
          <div><dt>{text.routeLabel}</dt><dd>{text.stopCount}</dd></div>
        </dl>
        <p>{text.scopeNote}</p>
      </section>

      <section aria-labelledby="demo-driver-sequence" className="demo-dispatch-sheet">
        <header><h3 id="demo-driver-sequence">{text.sequence}</h3><span>{text.previewNote}</span></header>
        <ol>
          {text.stops.map((stop, index) => {
            const expanded = openStop === index;
            return (
              <li className="demo-stop-card" key={stop.invoice}>
                <div aria-hidden="true" className="demo-stop-marker"><span>{index + 1}</span></div>
                <div className="demo-stop-summary">
                  <div><span>{text.stop} {index + 1}</span><strong>{stop.name}</strong><small>{stop.area}</small></div>
                  <span className="status-badge status-current">{text.assigned}</span>
                </div>
                <button aria-controls={`demo-stop-details-${index}`} aria-expanded={expanded} className="button button-secondary button-small" onClick={() => setOpenStop(expanded ? null : index)} type="button">
                  {expanded ? text.hideDetails : text.viewDetails}
                </button>
                {expanded ? (
                  <dl className="demo-stop-details" id={`demo-stop-details-${index}`}>
                    <div><dt>{text.contact}</dt><dd><bdi dir="ltr">{stop.phone}</bdi></dd></div>
                    <div><dt>{text.invoice}</dt><dd><bdi dir="ltr">{stop.invoice}</bdi></dd></div>
                    <div><dt>{text.note}</dt><dd>{stop.note}</dd></div>
                  </dl>
                ) : null}
              </li>
            );
          })}
        </ol>
      </section>
    </section>
  );
}

export function DemoGallery() {
  const { i18n } = useTranslation();
  const language: DemoLanguage = i18n.resolvedLanguage?.startsWith("ar") ? "ar" : "en";
  const text = copy[language];
  const [selectedRole, setSelectedRole] = useState<DemoRole>("guest");
  const [basket, setBasket] = useState<string[]>([]);
  const [checkoutDetails, setCheckoutDetails] = useState<CheckoutDetails>();
  const [resetVersion, setResetVersion] = useState(0);
  const roleButtons = useRef<Array<HTMLButtonElement | null>>([]);

  const switchLanguage = async () => {
    const nextLanguage = language === "ar" ? "en" : "ar";
    await i18n.changeLanguage(nextLanguage);
    document.documentElement.lang = nextLanguage;
    document.documentElement.dir = nextLanguage === "ar" ? "rtl" : "ltr";
  };

  const resetPreview = () => { setSelectedRole("guest"); setBasket([]); setCheckoutDetails(undefined); setResetVersion((current) => current + 1); };

  const moveSelection = (currentIndex: number, key: string) => {
    let nextIndex: number | undefined;
    if (key === "Home") nextIndex = 0;
    if (key === "End") nextIndex = roles.length - 1;
    if (key === "ArrowRight") nextIndex = (currentIndex + 1) % roles.length;
    if (key === "ArrowLeft") nextIndex = (currentIndex - 1 + roles.length) % roles.length;
    if (nextIndex === undefined) return;
    const nextRole = roles[nextIndex];
    if (!nextRole) return;
    setSelectedRole(nextRole);
    roleButtons.current[nextIndex]?.focus();
  };

  const completeCheckout = (details: CheckoutDetails) => { setCheckoutDetails(details); setSelectedRole("customer"); };

  return (
    <div className="demo-gallery">
      <a className="skip-link" href="#demo-content">{text.skip}</a>
      <div className="demo-preview-banner" role="status"><strong>{text.preview}</strong><span>{text.privacy}</span></div>
      <header className="demo-header">
        <a aria-label={text.brandHome} className="brand-mark" href="/"><span className="brand-route" aria-hidden="true"><i /><i /><i /></span><span>Tawzeevo</span></a>
        <button className="language-switch" onClick={() => void switchLanguage()} type="button"><span aria-hidden="true">{language === "ar" ? "EN" : "ع"}</span><span>{text.language}</span></button>
      </header>
      <main className="demo-content" id="demo-content" tabIndex={-1}>
        <section className="demo-intro"><p className="eyebrow">{text.eyebrow}</p><h1>{text.title}</h1><p>{text.intro}</p></section>
        <section aria-labelledby="demo-selector-title" className="demo-role-shell">
          <div className="demo-role-toolbar"><h2 id="demo-selector-title">{text.selector}</h2><button className="button button-secondary button-small" onClick={resetPreview} type="button">{text.reset}</button></div>
          <div aria-label={text.selector} className="demo-role-tabs" role="tablist">
            {roles.map((role, index) => <button aria-controls={`demo-panel-${role}`} aria-selected={selectedRole === role} id={`demo-tab-${role}`} key={role} onClick={() => setSelectedRole(role)} onKeyDown={(event) => moveSelection(index, event.key)} ref={(element) => { roleButtons.current[index] = element; }} role="tab" tabIndex={selectedRole === role ? 0 : -1} type="button"><span aria-hidden="true">0{index + 1}</span><strong>{text.roles[role].label}</strong></button>)}
          </div>
          <article aria-labelledby={`demo-tab-${selectedRole}`} className={`demo-role-panel demo-role-${selectedRole}`} id={`demo-panel-${selectedRole}`} role="tabpanel">
            {selectedRole === "guest" ? <GuestView basket={basket} key={resetVersion} language={language} onAdd={(id) => setBasket((current) => [...current, id])} onCheckout={completeCheckout} /> : null}
            {selectedRole === "customer" ? <CustomerView basket={basket} details={checkoutDetails} language={language} /> : null}
            {selectedRole === "owner" ? <OwnerView key={resetVersion} language={language} /> : null}
            {selectedRole === "driver" ? <DriverView key={resetVersion} language={language} /> : null}
          </article>
        </section>
      </main>
    </div>
  );
}
