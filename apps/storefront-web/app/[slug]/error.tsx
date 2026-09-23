"use client";

import { t } from "@/lib/i18n";

/**
 * Shown when a shop page cannot be built (the catalog API failed): the same bilingual message style as the
 * not-found page, with a way to try again, instead of the framework's English-only fallback. Nothing about
 * the error itself is displayed.
 */
export default function ShopError({ retry }: { error: Error & { digest?: string }; retry: () => void }) {
  return (
    <main className="root-page">
      {/* The page's own metadata could not be built; React places this title in the document head. */}
      <title>{`${t("en", "errorTitle")} · Tawzeevo`}</title>
      <p className="brand"><span className="brand-symbol" aria-hidden="true"><i /><i /><i /></span>Tawzeevo</p>
      <h1>{t("en", "errorTitle")} · <span dir="rtl" lang="ar">{t("ar", "errorTitle")}</span></h1>
      <p className="muted">{t("en", "errorBody")}</p>
      <p className="muted" dir="rtl" lang="ar">{t("ar", "errorBody")}</p>
      <p><button className="button" onClick={() => retry()} type="button">{t("en", "tryAgain")} · <span lang="ar">{t("ar", "tryAgain")}</span></button></p>
    </main>
  );
}
