import { t } from "@/lib/i18n";

/** The platform root has no shop of its own: each business lives at its own address. */
export default function Home() {
  return (
    <main className="root-page">
      <p className="brand"><span className="brand-symbol" aria-hidden="true"><i /><i /><i /></span>Tawzeevo</p>
      <h1>{t("en", "rootTitle")}</h1>
      <p className="muted">{t("en", "rootBody")}</p>
      <p className="muted" dir="rtl" lang="ar">{t("ar", "rootBody")}</p>
    </main>
  );
}
