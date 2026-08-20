import { NavLink, Outlet, useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";

import { useAuth } from "../auth/AuthContext";

const adminLinks = [
  ["/admin", "nav.overview"],
  ["/admin/users", "nav.users"],
  ["/admin/applications", "nav.applications"],
  ["/admin/tenants", "nav.tenants"],
] as const;

export function LanguageButton() {
  const { i18n, t } = useTranslation();

  const switchLanguage = async () => {
    const language = i18n.resolvedLanguage === "ar" ? "en" : "ar";
    await i18n.changeLanguage(language);
    document.documentElement.lang = language;
    document.documentElement.dir = language === "ar" ? "rtl" : "ltr";
  };

  return (
    <button className="language-switch" onClick={() => void switchLanguage()} type="button">
      <span aria-hidden="true">{i18n.resolvedLanguage === "ar" ? "EN" : "ع"}</span>
      <span>{t("language")}</span>
    </button>
  );
}

export function BrandMark() {
  const { t } = useTranslation();
  return (
    <NavLink aria-label={t("brandHome")} className="brand-mark" to="/">
      <span className="brand-route" aria-hidden="true">
        <i />
        <i />
        <i />
      </span>
      <span>Tawzeevo</span>
    </NavLink>
  );
}

export function PublicHeader() {
  const { t } = useTranslation();
  const { status } = useAuth();
  return (
    <header className="public-header">
      <BrandMark />
      <nav aria-label={t("nav.primary")} className="public-nav">
        <NavLink to="/stats">{t("nav.statistics")}</NavLink>
        {status === "unauthenticated" ? (
          <>
            <NavLink to="/login">{t("nav.login")}</NavLink>
            <NavLink className="button button-small" to="/register">
              {t("nav.register")}
            </NavLink>
          </>
        ) : null}
        {status === "authenticated" ? (
          <NavLink className="button button-small" to="/workspace">
            {t("nav.workspace")}
          </NavLink>
        ) : null}
        <LanguageButton />
      </nav>
    </header>
  );
}

export function AppShell() {
  const { t } = useTranslation();
  const { logout, user } = useAuth();
  const navigate = useNavigate();
  const links = user?.type === "admin" ? adminLinks : [["/workspace", "nav.overview"]] as const;

  const signOut = async () => {
    await logout();
    await navigate("/login", { replace: true });
  };

  return (
    <div className="app-frame">
      <a className="skip-link" href="#main-content">
        {t("skipToContent")}
      </a>
      <aside className="app-sidebar">
        <BrandMark />
        <div className="sidebar-context">
          <span>{t(user?.type === "admin" ? "roles.platformAdmin" : "roles.client")}</span>
          <strong>{user?.first_name} {user?.last_name}</strong>
        </div>
        <nav aria-label={t("nav.workspaceNav")} className="sidebar-nav">
          {links.map(([to, label]) => (
            <NavLink end={to === "/admin" || to === "/workspace"} key={to} to={to}>
              <span className="nav-stop" aria-hidden="true" />
              {t(label)}
            </NavLink>
          ))}
          <NavLink to="/profile">
            <span className="nav-stop" aria-hidden="true" />
            {t("nav.profile")}
          </NavLink>
          <NavLink to="/stats">
            <span className="nav-stop" aria-hidden="true" />
            {t("nav.statistics")}
          </NavLink>
        </nav>
        <div className="sidebar-footer">
          <LanguageButton />
          <button className="text-button" onClick={() => void signOut()} type="button">
            {t("nav.logout")}
          </button>
        </div>
      </aside>
      <div className="app-stage">
        <header className="mobile-app-header">
          <BrandMark />
          <LanguageButton />
        </header>
        <main id="main-content" className="app-content" tabIndex={-1}>
          <Outlet />
        </main>
      </div>
    </div>
  );
}
