import { useTranslation } from "react-i18next";

import { Icon } from "./Icon";

/**
 * Sign-in story illustration (docs/design-references/PUBLIC_ENTRY.md): a restrained family of
 * line icons joined by a dashed illustrative path. It represents a working day, never a map or
 * tracking surface, and is hidden from assistive technology as pure decoration.
 */
export function RouteMural() {
  const { t } = useTranslation();
  return (
    <div className="mural" aria-hidden="true">
      <svg className="mural-path" viewBox="0 0 500 400">
        <path d="M70 80h220q60 0 60 60v60q0 50-60 50H150q-65 0-65 60h340" />
        <circle cx="70" cy="80" r="7" />
        <circle cx="425" cy="310" r="7" />
      </svg>
      <span className="mural-icon m0"><Icon name="shop" /></span>
      <span className="mural-icon m1"><Icon name="invoice" /></span>
      <span className="mural-icon m2"><Icon name="box" /></span>
      <span className="mural-icon m3"><Icon name="van" /></span>
      <span className="mural-icon m4"><Icon name="pin" /></span>
      <span className="mural-icon m5"><Icon name="sun" /></span>
      <div className="mural-message"><Icon name="check" small /><span>{t("entry.storyMessage")}</span></div>
    </div>
  );
}

/** The landing page's order-to-delivery board: three steps of one working day. */
export function DayBoard({ demoHref }: { demoHref?: string | undefined }) {
  const { t } = useTranslation();
  return (
    <div className="day-board">
      <div className="board-top"><span><Icon name="sun" small />{t("landing.boardLabel")}</span><small>{t("landing.boardNote")}</small></div>
      <div className="board-title"><h2>{t("landing.boardTitle")}</h2><span className="board-date" aria-hidden="true"><Icon name="van" /></span></div>
      <ol className="board-route">
        <li className="route-row"><span className="route-icon"><Icon name="shop" /></span><div><strong>{t("landing.step1")}</strong><p>{t("landing.step1Body")}</p></div></li>
        <li className="route-row"><span className="route-icon"><Icon name="invoice" /></span><div><strong>{t("landing.step2")}</strong><p>{t("landing.step2Body")}</p></div></li>
        <li className="route-row"><span className="route-icon blue"><Icon name="van" /></span><div><strong>{t("landing.step3")}</strong><p>{t("landing.step3Body")}</p></div></li>
      </ol>
      {demoHref ? (
        <a className="board-action" href={demoHref}>
          <span><small>{t("landing.demoKicker")}</small><strong>{t("landing.demoAction")}</strong></span>
          <span className="directional"><Icon name="arrow" /></span>
        </a>
      ) : null}
    </div>
  );
}
