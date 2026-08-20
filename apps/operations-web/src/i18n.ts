import i18n from "i18next";
import { initReactI18next } from "react-i18next";

const resources = {
  en: {
    translation: {
      brand: "Tawzeevo",
      eyebrow: "Operations platform",
      heading: "Your Cash Van workspace is taking shape.",
      body: "The secure tenant, session, and PostgreSQL foundations are ready for the next milestone.",
      language: "العربية",
      foundation: "Foundation status",
      api: "FastAPI service",
      database: "PostgreSQL migrations",
      tenant: "Tenant isolation contract",
      ready: "Established",
      email: "Contact email",
      validate: "Validate form foundation",
      valid: "Form validation is connected.",
    },
  },
  ar: {
    translation: {
      brand: "توزيفو",
      eyebrow: "منصة العمليات",
      heading: "مساحة عمل سيارة التوزيع قيد الإنشاء.",
      body: "أُسست بنية المستأجرين والجلسات وقاعدة PostgreSQL بأمان للمرحلة التالية.",
      language: "English",
      foundation: "حالة الأساس",
      api: "خدمة FastAPI",
      database: "ترحيلات PostgreSQL",
      tenant: "عقد عزل المستأجرين",
      ready: "جاهز",
      email: "البريد الإلكتروني للتواصل",
      validate: "اختبار أساس النموذج",
      valid: "التحقق من النموذج متصل.",
    },
  },
} as const;

void i18n.use(initReactI18next).init({
  resources,
  lng: "en",
  fallbackLng: "en",
  interpolation: { escapeValue: false },
});

export default i18n;
