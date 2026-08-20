import { useRef, useState } from "react";
import { useTranslation } from "react-i18next";

import "./demo.css";

const roles = ["guest", "customer", "owner", "driver"] as const;
type DemoRole = (typeof roles)[number];

const copy = {
  en: {
    brandHome: "Tawzeevo home",
    skip: "Skip to demo content",
    language: "العربية",
    preview: "Synthetic preview",
    privacy: "Nothing on this page is saved or sent.",
    eyebrow: "Four perspectives · one distribution route",
    title: "See Tawzeevo from every stop.",
    intro: "Switch between carefully isolated role boundaries. Detailed interactive views arrive in the next demo milestones.",
    selector: "Choose a demo perspective",
    reset: "Reset preview",
    selected: "Selected perspective",
    roles: {
      guest: { label: "Guest", description: "An unauthenticated storefront visitor browsing a synthetic catalog." },
      customer: { label: "Customer", description: "A guest who supplied checkout details and is viewing a synthetic order-facing state." },
      owner: { label: "Owner", description: "A client account with owner membership in one tenant, able to oversee that tenant's work." },
      driver: { label: "Driver", description: "A least-privileged tenant member viewing only assigned operational work." },
    },
  },
  ar: {
    brandHome: "الصفحة الرئيسية لتوزيفو",
    skip: "انتقل إلى محتوى العرض",
    language: "English",
    preview: "معاينة ببيانات تجريبية",
    privacy: "لا يتم حفظ أو إرسال أي شيء في هذه الصفحة.",
    eyebrow: "أربع وجهات نظر · مسار توزيع واحد",
    title: "شاهد توزيـفو من كل محطة.",
    intro: "تنقّل بين حدود الأدوار المعزولة بعناية. ستصل العروض التفاعلية المفصلة في مراحل العرض التالية.",
    selector: "اختر منظوراً للعرض",
    reset: "إعادة ضبط المعاينة",
    selected: "المنظور المحدد",
    roles: {
      guest: { label: "زائر", description: "زائر متجر غير مسجل يتصفح كتالوجاً تجريبياً." },
      customer: { label: "عميل", description: "زائر أدخل بيانات الطلب ويشاهد حالة طلب تجريبية." },
      owner: { label: "مالك", description: "حساب عميل بعضوية مالك في منشأة واحدة ويشرف على عملها." },
      driver: { label: "سائق", description: "عضو منشأة بصلاحيات محدودة يرى فقط العمل المسند إليه." },
    },
  },
} as const;

export function DemoGallery() {
  const { i18n } = useTranslation();
  const language = i18n.resolvedLanguage?.startsWith("ar") ? "ar" : "en";
  const text = copy[language];
  const [selectedRole, setSelectedRole] = useState<DemoRole>("guest");
  const roleButtons = useRef<Array<HTMLButtonElement | null>>([]);

  const switchLanguage = async () => {
    const nextLanguage = language === "ar" ? "en" : "ar";
    await i18n.changeLanguage(nextLanguage);
    document.documentElement.lang = nextLanguage;
    document.documentElement.dir = nextLanguage === "ar" ? "rtl" : "ltr";
  };

  const selectRole = (role: DemoRole) => {
    setSelectedRole(role);
  };

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

  return (
    <div className="demo-gallery">
      <a className="skip-link" href="#demo-content">{text.skip}</a>
      <div className="demo-preview-banner" role="status">
        <strong>{text.preview}</strong>
        <span>{text.privacy}</span>
      </div>
      <header className="demo-header">
        <a aria-label={text.brandHome} className="brand-mark" href="/">
          <span className="brand-route" aria-hidden="true"><i /><i /><i /></span>
          <span>Tawzeevo</span>
        </a>
        <button className="language-switch" onClick={() => void switchLanguage()} type="button">
          <span aria-hidden="true">{language === "ar" ? "EN" : "ع"}</span>
          <span>{text.language}</span>
        </button>
      </header>

      <main className="demo-content" id="demo-content" tabIndex={-1}>
        <section className="demo-intro">
          <p className="eyebrow">{text.eyebrow}</p>
          <h1>{text.title}</h1>
          <p>{text.intro}</p>
        </section>

        <section aria-labelledby="demo-selector-title" className="demo-role-shell">
          <div className="demo-role-toolbar">
            <h2 id="demo-selector-title">{text.selector}</h2>
            <button className="button button-secondary button-small" onClick={() => setSelectedRole("guest")} type="button">
              {text.reset}
            </button>
          </div>
          <div aria-label={text.selector} className="demo-role-tabs" role="tablist">
            {roles.map((role, index) => (
              <button
                aria-controls={`demo-panel-${role}`}
                aria-selected={selectedRole === role}
                id={`demo-tab-${role}`}
                key={role}
                onClick={() => selectRole(role)}
                onKeyDown={(event) => moveSelection(index, event.key)}
                ref={(element) => { roleButtons.current[index] = element; }}
                role="tab"
                tabIndex={selectedRole === role ? 0 : -1}
                type="button"
              >
                <span aria-hidden="true">0{index + 1}</span>
                <strong>{text.roles[role].label}</strong>
              </button>
            ))}
          </div>
          <article
            aria-labelledby={`demo-tab-${selectedRole}`}
            className="demo-role-panel"
            id={`demo-panel-${selectedRole}`}
            role="tabpanel"
          >
            <p className="section-kicker">{text.selected}</p>
            <h2>{text.roles[selectedRole].label}</h2>
            <p>{text.roles[selectedRole].description}</p>
            <div aria-hidden="true" className="demo-route-line"><i /><i /><i /><i /></div>
          </article>
        </section>
      </main>
    </div>
  );
}
