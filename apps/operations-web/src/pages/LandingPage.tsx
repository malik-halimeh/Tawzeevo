import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";

import { useAuth } from "../auth/AuthContext";
import { PublicHeader } from "../components/AppShell";
import { Arrow, Icon } from "../components/Icon";
import { DayBoard } from "../components/Illustrations";

/**
 * Public landing page (docs/design-references/PUBLIC_ENTRY.md). It explains Tawzeevo through
 * the distributor's working day and leads to sign-in. Public statistics stay one link away;
 * nothing here invents platform numbers, tracking, stock or payment claims.
 */
export function LandingPage() {
  const { t } = useTranslation();
  const { status } = useAuth();
  // The synthetic role gallery (D-029) is an environment-gated reviewer tool; the landing links
  // to it only in builds where it exists.
  const demoHref = import.meta.env.VITE_DEMO_PREVIEW === "true" ? "/demo" : undefined;
  const signedIn = status === "authenticated";
  const primaryTo = signedIn ? "/workspace" : "/login";

  return (
    <div className="entry-page landing">
      <PublicHeader landing />
      <main id="main" tabIndex={-1}>
        <section className="hero">
          <div className="hero-copy">
            <p className="eyebrow"><Icon name="box" small />{t("landing.eyebrow")}</p>
            <h1>{t("landing.title")}<br /><span>{t("landing.titleAccent")}</span></h1>
            <p className="lead">{t("landing.lead")}</p>
            <div className="hero-actions">
              <Link className="button button-arrow" to={primaryTo}>{t(signedIn ? "nav.workspace" : "landing.signIn")}<Arrow /></Link>
              <a className="text-link" href="#how">{t("landing.closerLook")}</a>
            </div>
            <p className="quiet-note">{t("landing.quiet")}</p>
          </div>
          <div className="hero-art">
            <div className="art-sun" aria-hidden="true"><Icon name="sun" /></div>
            <DayBoard demoHref={demoHref} />
          </div>
        </section>
        <section aria-labelledby="workflow-title" className="workflow" id="how">
          <div className="section-heading">
            <p className="eyebrow">{t("landing.howEyebrow")}</p>
            <h2 id="workflow-title">{t("landing.howTitle")}<br />{t("landing.howTitleSecond")}</h2>
          </div>
          <div className="feature-grid">
            <article><span className="feature-icon"><Icon name="person" /></span><h3>{t("landing.feature1")}</h3><p>{t("landing.feature1Body")}</p></article>
            <article><span className="feature-icon"><Icon name="van" /></span><h3>{t("landing.feature2")}</h3><p>{t("landing.feature2Body")}</p></article>
            <article><span className="feature-icon"><Icon name="shop" /></span><h3>{t("landing.feature3")}</h3><p>{t("landing.feature3Body")}</p></article>
          </div>
        </section>
        <section className="closing">
          <div>
            <p className="eyebrow">{t("landing.closingEyebrow")}</p>
            <h2>{t("landing.closingTitle")}</h2>
            <p>{t("landing.closingBody")}</p>
          </div>
          <Link className="button button-arrow" to={primaryTo}>{t(signedIn ? "nav.workspace" : "landing.welcomeBack")}<Arrow /></Link>
        </section>
      </main>
      <footer className="site-footer">
        <span>{t("landing.footer")}</span>
        <div>
          <Link to="/stats">{t("nav.statistics")}</Link>
          {demoHref ? <a href={demoHref}>{t("landing.preview")}</a> : null}
        </div>
      </footer>
    </div>
  );
}
