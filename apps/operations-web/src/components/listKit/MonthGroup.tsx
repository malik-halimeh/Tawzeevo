import { type ReactNode, useId } from "react";
import { useTranslation } from "react-i18next";

import "../../listKit.css";

/** "2026-10" (or a date starting with it) → "October 2026" / "تشرين الأول ٢٠٢٦" in the current language. */
function monthName(month: string, language: string): string {
  const [year, value] = month.slice(0, 7).split("-").map(Number);
  if (!year || !value) return month;
  return new Intl.DateTimeFormat(language === "ar" ? "ar-LB" : "en-GB", { month: "long", year: "numeric", timeZone: "UTC" }).format(new Date(Date.UTC(year, value - 1, 1)));
}

/**
 * Rows of one calendar month under a month heading, with an optional total for the month. `month` is
 * the "YYYY-MM" key the page grouped by (in the business's calendar). Children are ListRows.
 */
export function MonthGroup({ month, total, level = 2, children }: {
  month: string;
  total?: ReactNode;
  level?: 2 | 3;
  children: ReactNode;
}) {
  const { t, i18n } = useTranslation();
  const headingId = useId();
  const Heading = level === 2 ? "h2" : "h3";
  return (
    <section aria-labelledby={headingId} className="month-group">
      <div className="month-group-head">
        <Heading id={headingId}>{monthName(month, i18n.language)}</Heading>
        {total !== undefined ? <p className="month-group-total"><span className="sr-only">{t("listKit.monthTotal")} </span><bdi dir="ltr">{total}</bdi></p> : null}
      </div>
      <ul className="list-rows">{children}</ul>
    </section>
  );
}
