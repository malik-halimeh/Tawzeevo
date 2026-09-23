import { useQuery } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";
import { Link, NavLink, Outlet, useLocation, useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";

import { apiRequest } from "../api/client";
import type { TenantContextListResponse } from "../api/types";
import { useAuth } from "../auth/AuthContext";
import { Icon, type IconName } from "./Icon";
import { PHONE_PRIMARY_SECTIONS, SYNC_ANCHOR, WORK_ANCHOR, WORKSPACE_SECTIONS, sectionFromSearch, sectionHref, selectedContext, tenantFromSearch } from "./workspaceSections";

type ShellLink = readonly [string, string, IconName];

const adminLinks: readonly ShellLink[] = [
  ["/admin", "nav.overview", "work"],
  ["/admin/users", "nav.users", "people"],
  ["/admin/applications", "nav.applications", "invoice"],
  ["/admin/tenants", "nav.tenants", "building"],
];

export function LanguageButton({ className = "language" }: { className?: string }) {
  const { i18n, t } = useTranslation();
  const other = i18n.resolvedLanguage === "ar" ? "en" : "ar";

  const switchLanguage = async () => {
    await i18n.changeLanguage(other);
    document.documentElement.lang = other;
    document.documentElement.dir = other === "ar" ? "rtl" : "ltr";
  };

  return (
    <button className={className} lang={other} onClick={() => void switchLanguage()} type="button">
      {t("language")}
    </button>
  );
}

/** The Tawzeevo three-node mark: three connected stops, the middle one filled with citron. */
export function BrandMark({ to = "/" }: { to?: string }) {
  const { t } = useTranslation();
  return (
    <NavLink aria-label={t("brandHome")} className="brand" to={to}>
      <span className="brand-symbol" aria-hidden="true"><i /><i /><i /></span>
      <span className="brand-name">Tawzeevo</span>
    </NavLink>
  );
}

/** Public header shared by the landing, statistics and not-found pages. */
export function PublicHeader({ landing = false }: { landing?: boolean }) {
  const { t } = useTranslation();
  const { status } = useAuth();
  return (
    <>
    <a className="skip-link" href="#main">{t("skipToContent")}</a>
    <header className="site-header">
      <BrandMark />
      <nav aria-label={t("nav.primary")} className="site-nav">
        {landing ? <a className="site-nav-link how-link" href="#how">{t("nav.how")}</a> : <NavLink className="site-nav-link about-link" to="/">{t("nav.home")}</NavLink>}
        {!landing ? <NavLink className="site-nav-link stats-link" to="/stats">{t("nav.statistics")}</NavLink> : null}
        <LanguageButton />
        {status === "unauthenticated" ? (
          <>
            {!landing ? <NavLink className="site-nav-link" to="/register">{t("nav.register")}</NavLink> : null}
            <NavLink className="button button-small" to="/login">{t("nav.login")}</NavLink>
          </>
        ) : null}
        {status === "authenticated" ? <NavLink className="button button-small" to="/workspace">{t("nav.workspace")}</NavLink> : null}
      </nav>
    </header>
    </>
  );
}

/**
 * Reads the browser's own network flag (navigator.onLine) for the topline indicator. It says only
 * whether the browser believes it has a network; it never verifies the API. Nothing is polled.
 */
function useOnline(): boolean {
  const [online, setOnline] = useState(typeof navigator === "undefined" ? true : navigator.onLine);
  useEffect(() => {
    const up = () => setOnline(true);
    const down = () => setOnline(false);
    window.addEventListener("online", up);
    window.addEventListener("offline", down);
    return () => { window.removeEventListener("online", up); window.removeEventListener("offline", down); };
  }, []);
  return online;
}

/**
 * A software keyboard shrinks the visual viewport on phones. While it is open the bottom
 * navigation is hidden and attached action areas move above the keyboard (design rule).
 */
function useSoftwareKeyboard() {
  useEffect(() => {
    const viewport = window.visualViewport;
    if (!viewport) return;
    const update = () => {
      const keyboard = Math.max(0, window.innerHeight - viewport.height - viewport.offsetTop);
      document.body.classList.toggle("keyboard-open", keyboard > 120);
      document.documentElement.style.setProperty("--keyboard", `${keyboard}px`);
    };
    viewport.addEventListener("resize", update);
    viewport.addEventListener("scroll", update);
    return () => {
      viewport.removeEventListener("resize", update);
      viewport.removeEventListener("scroll", update);
      document.body.classList.remove("keyboard-open");
    };
  }, []);
}

export function AppShell() {
  const { t } = useTranslation();
  const { logout, user } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const online = useOnline();
  useSoftwareKeyboard();
  const [moreOpen, setMoreOpen] = useState(false);
  const moreButton = useRef<HTMLButtonElement>(null);
  const sheet = useRef<HTMLDivElement>(null);
  const isAdmin = user?.type === "admin";
  // The same tenant-context query the workspace uses (one shared cache entry) tells the phone bar
  // and the desktop rail which presentation grouping applies: owner sections, or the driver's work/sync.
  const contexts = useQuery({
    queryKey: ["tenant-contexts"],
    queryFn: () => apiRequest<TenantContextListResponse>("/api/v1/tenant-contexts"),
    enabled: user?.type === "client",
  });
  const onWorkspace = location.pathname === "/workspace";
  const search = new URLSearchParams(location.search);
  const section = onWorkspace ? sectionFromSearch(search) : null;
  const tenantParam = onWorkspace ? tenantFromSearch(search) : null;
  // The grouping follows the business the workspace body shows (the one named in the address,
  // else the first listed) — never the union of the member's roles. Someone who owns one
  // business and drives for another gets the driver grouping while the driver business is open.
  const selected = selectedContext(contexts.data?.tenants ?? [], tenantParam);
  // A suspended or closed business shows only its inactive notice, so it gets no section links:
  // the generic workspace entry stays, and the picker in the body still switches business.
  const activeSelection = selected?.tenant_status === "ACTIVE";
  const ownerNav = !isAdmin && activeSelection && selected?.role === "owner";
  const driverNav = !isAdmin && activeSelection && selected?.role === "driver";
  const links: readonly ShellLink[] = isAdmin ? adminLinks : [[sectionHref("work", tenantParam), "nav.overview", "work"]];
  const initials = `${user?.first_name?.[0] ?? ""}${user?.last_name?.[0] ?? ""}`;
  const roleLabel = t(isAdmin ? "roles.platformAdmin" : "roles.client");

  useEffect(() => { setMoreOpen(false); }, [location.key]);
  useEffect(() => {
    if (!moreOpen) return;
    sheet.current?.querySelector<HTMLElement>("a, button")?.focus();
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") { setMoreOpen(false); moreButton.current?.focus(); }
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [moreOpen]);

  const signOut = async () => {
    await logout();
    await navigate("/login", { replace: true });
  };

  const navItem = ([to, label, icon]: ShellLink, className = "nav-item") => {
    const pathname = to.split("?")[0];
    return (
      <NavLink className={className} end={pathname === "/admin" || pathname === "/workspace"} key={pathname} to={to}>
        <Icon name={icon} />
        <span>{t(label)}</span>
      </NavLink>
    );
  };
  // Section and anchor links keep the selected business in the address so a tap never
  // silently returns the member to their first business.
  const sectionItem = (id: (typeof WORKSPACE_SECTIONS)[number]["id"], className: string) => {
    const meta = WORKSPACE_SECTIONS.find((entry) => entry.id === id)!;
    const active = section === id;
    return (
      <Link aria-current={active ? "page" : undefined} className={`${className}${active ? " active" : ""}`} key={id} to={sectionHref(id, tenantParam)}>
        <Icon name={meta.icon} />
        <span>{t(meta.label)}</span>
      </Link>
    );
  };
  const anchorItem = (anchor: string, label: string, icon: IconName, className = "mobile-nav-item") => {
    const active = onWorkspace && (anchor === SYNC_ANCHOR ? location.hash === `#${SYNC_ANCHOR}` : location.hash !== `#${SYNC_ANCHOR}`);
    return (
      <Link aria-current={active ? "page" : undefined} className={`${className}${active ? " active" : ""}`} key={anchor} to={`${sectionHref("work", tenantParam)}#${anchor}`}>
        <Icon name={icon} />
        <span>{t(label)}</span>
      </Link>
    );
  };
  const moreSections = WORKSPACE_SECTIONS.filter((entry) => !PHONE_PRIMARY_SECTIONS.includes(entry.id));

  return (
    <div className="frame">
      <a className="skip-link" href="#main-content">{t("skipToContent")}</a>
      <aside className="rail">
        <BrandMark />
        {/* Desktop mirrors the phone grouping of the selected business: an owner's Work, Customers and
            Invoices, then the More sections; a driver's My work and Sync. Account links sit below. */}
        <nav aria-label={t("nav.workspaceNav")} className="rail-nav">
          {ownerNav ? (
            <>
              {PHONE_PRIMARY_SECTIONS.map((id) => sectionItem(id, "nav-item"))}
              <div aria-labelledby="rail-more-sections" className="rail-group" role="group">
                <p className="eyebrow rail-label" id="rail-more-sections">{t("nav.more")}</p>
                {moreSections.map((entry) => sectionItem(entry.id, "nav-item nav-item-minor"))}
              </div>
            </>
          ) : driverNav ? (
            <>{anchorItem(WORK_ANCHOR, "nav.myWork", "work", "nav-item")}{anchorItem(SYNC_ANCHOR, "nav.sync", "sync", "nav-item")}</>
          ) : links.map((link) => navItem(link))}
        </nav>
        <div aria-label={t("shell.account")} className="rail-bottom" role="group">
          <div className="rail-context">
            <span className="avatar" aria-hidden="true">{initials}</span>
            <span><strong>{user?.first_name} {user?.last_name}</strong><small>{roleLabel}</small></span>
          </div>
          {navItem(["/profile", "nav.profile", "person"], "nav-item nav-item-minor")}
          {navItem(["/stats", "nav.statistics", "chart"], "nav-item nav-item-minor")}
          <LanguageButton className="text-btn" />
          <button className="text-btn" onClick={() => void signOut()} type="button"><Icon name="logout" />{t("nav.logout")}</button>
        </div>
      </aside>
      <div className="stage">
        <div className="topline">
          <div className="topline-trail"><span>{roleLabel}</span><span aria-hidden="true">/</span><strong>{t(isAdmin ? "shell.admin" : "shell.workspace")}</strong></div>
          <BrandMark />
          <span className={`online${online ? "" : " offline"}`}>{t(online ? "shell.browserOnline" : "shell.browserOffline")}</span>
        </div>
        <main id="main-content" className="main" tabIndex={-1}>
          <Outlet />
        </main>
      </div>
      <nav aria-label={t("nav.primary")} className="mobile-nav">
        {ownerNav ? PHONE_PRIMARY_SECTIONS.map((id) => sectionItem(id, "mobile-nav-item")) : null}
        {driverNav ? <>{anchorItem(WORK_ANCHOR, "nav.myWork", "work")}{anchorItem(SYNC_ANCHOR, "nav.sync", "sync")}</> : null}
        {!ownerNav && !driverNav ? links.map((link) => navItem(link, "mobile-nav-item")) : null}
        {!ownerNav && !driverNav && !isAdmin ? navItem(["/profile", "nav.profile", "person"], "mobile-nav-item") : null}
        <button aria-controls="more-sheet" aria-expanded={moreOpen} className={`mobile-nav-item${moreOpen ? " active" : ""}`} onClick={() => setMoreOpen((open) => !open)} ref={moreButton} type="button">
          <Icon name="more" />
          <span>{t("nav.more")}</span>
        </button>
      </nav>
      {moreOpen ? (
        <div aria-label={t("nav.moreMenu")} className="more-sheet" id="more-sheet" ref={sheet} role="group">
          {ownerNav ? (
            <div className="more-group" role="group" aria-label={t("tenantWorkspace.sections")}>
              <p className="eyebrow">{t("tenantWorkspace.sections")}</p>
              {moreSections.map((entry) => sectionItem(entry.id, "more-item"))}
            </div>
          ) : null}
          <div className="more-group" role="group" aria-label={t("shell.account")}>
            <p className="eyebrow">{t("shell.account")}</p>
            {isAdmin || ownerNav || driverNav ? <NavLink className="more-item" to="/profile"><Icon name="person" />{t("nav.profile")}</NavLink> : null}
            <NavLink className="more-item" to="/stats"><Icon name="chart" />{t("nav.statistics")}</NavLink>
            <LanguageButton className="more-item" />
            <button className="more-item" onClick={() => void signOut()} type="button"><Icon name="logout" />{t("nav.logout")}</button>
          </div>
          <button className="more-item more-close" onClick={() => { setMoreOpen(false); moreButton.current?.focus(); }} type="button"><Icon name="close" />{t("nav.closeMenu")}</button>
        </div>
      ) : null}
    </div>
  );
}
