import { t } from "@/lib/i18n";

export default function NotFound() {
  return (
    <main className="root-page">
      <p className="brand"><span className="brand-symbol" aria-hidden="true"><i /><i /><i /></span>Tawzeevo</p>
      <h1>{t("en", "notFoundTitle")} · <span dir="rtl" lang="ar">{t("ar", "notFoundTitle")}</span></h1>
      <p className="muted">{t("en", "notFoundBody")}</p>
      <p className="muted" dir="rtl" lang="ar">{t("ar", "notFoundBody")}</p>
    </main>
  );
}
