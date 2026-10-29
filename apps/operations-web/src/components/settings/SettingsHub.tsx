import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { Link, useOutletContext, useSearchParams } from "react-router-dom";

import { apiRequest } from "../../api/client";
import type { FinancialSettingsResponse } from "../../api/types";
import { LanguageButton, type SettingsShellContext } from "../AppShell";
import type { BackupStatus } from "../BackupPanel";
import { Icon, type IconName } from "../Icon";
import { ListHeader } from "../listKit/ListHeader";
import type { StorefrontSettingsResponse } from "../StorefrontSettings";
import { SETTINGS_PAGES, sectionHref, settingsPageFromSearch } from "../workspaceSections";
import "../../settingsHub.css";

type RowTarget = { href: string; onOpen?: never } | { onOpen: () => void; href?: never };

/** Same list kit surface, with a decorative icon and chevron and a single accessible target. */
function SettingsRow({ title, value, icon, ...target }: { title: string; value?: string | undefined; icon: IconName } & RowTarget) {
  const content = <><Icon name={icon} /><span className="list-row-text"><span className="list-row-title">{title}</span>{value ? <span className="list-row-sub" dir="auto">{value}</span> : null}</span><span aria-hidden="true" className="settings-chevron">›</span></>;
  const label = value ? `${title}, ${value}` : title;
  return <li className="list-row">{target.href !== undefined
    ? <Link aria-label={label} className="list-row-main settings-row" to={target.href}>{content}</Link>
    : <button aria-label={label} className="list-row-main settings-row" onClick={target.onOpen} type="button">{content}</button>}</li>;
}

/** Navigation only: all configuration still lives at the existing section addresses. */
export function SettingsHub({ tenantId, tenantParam, businessName, onChooseBusiness }: {
  tenantId: string;
  tenantParam: string | null;
  businessName: string;
  onChooseBusiness?: (() => void) | undefined;
}) {
  const { t, i18n } = useTranslation();
  const [search] = useSearchParams();
  const shell = useOutletContext<SettingsShellContext>();
  const page = settingsPageFromSearch(search);
  // These are the existing small settings/status requests, scoped to the page that uses them.
  // No products, debts, backup payloads or campaign lists are loaded for a summary value.
  const storefront = useQuery({
    queryKey: ["settings-hub-storefront", tenantId],
    queryFn: () => apiRequest<StorefrontSettingsResponse>(`/api/v1/tenants/${tenantId}/storefront?tenant_id=${tenantId}`),
    enabled: page.id === "business",
  });
  const financial = useQuery({
    queryKey: ["settings-hub-financial", tenantId],
    queryFn: () => apiRequest<FinancialSettingsResponse>(`/api/v1/customer-ledger/settings?tenant_id=${tenantId}`),
    enabled: page.id === "invoices",
  });
  const backup = useQuery({
    queryKey: ["settings-hub-backup", tenantId],
    queryFn: () => apiRequest<BackupStatus>(`/api/v1/tenants/${tenantId}/backup?tenant_id=${tenantId}`),
    enabled: page.id === "general",
  });
  const lastBackup = backup.data?.latest_backup?.completed_at;
  const threshold = financial.data?.customer_overdue_threshold_days;
  const balancesHref = sectionHref("invoices", tenantParam, { view: "balances" });

  return (
    <div className="settings-hub">
      <nav aria-label={t("settingsHub.pages")} className="settings-pages">
        {SETTINGS_PAGES.map((item) => <Link aria-current={page.id === item.id ? "page" : undefined} key={item.id} to={sectionHref("settings", tenantParam, { view: item.id })}>{t(item.label)}</Link>)}
      </nav>
      <ListHeader title={t(page.label)} />
      <ul aria-label={t(page.label)} className="list-rows">
        {page.id === "business" ? <>
          <SettingsRow href={sectionHref("branding", tenantParam)} icon="palette" title={t("branding.tab")} value={businessName} />
          <SettingsRow href={sectionHref("storefront", tenantParam)} icon="shop" title={t("settingsHub.storefront")} value={storefront.data?.slug} />
          {onChooseBusiness ? <SettingsRow icon="building" onOpen={onChooseBusiness} title={t("tenantWorkspace.business")} /> : null}
        </> : page.id === "invoices" ? <>
          <SettingsRow href={sectionHref("pricing", tenantParam)} icon="coin" title={t("settingsHub.gradeDiscounts")} />
          <SettingsRow href={balancesHref} icon="clock" title={t("settingsHub.overdue")} value={threshold == null ? undefined : String(threshold)} />
          <SettingsRow href={balancesHref} icon="invoice" title={t("settingsHub.openingBalances")} />
          <li className="list-row"><div className="list-row-main settings-row" role="note"><Icon name="info" /><span className="list-row-text"><span className="list-row-title">{t("settingsHub.sharing")}</span><span className="list-row-sub">{t("settingsHub.sharingNote")}</span></span></div></li>
        </> : <>
          <li className="list-row"><LanguageButton className="list-row-main settings-row" currentLanguage valueSeparator=", " /></li>
          <SettingsRow href={sectionHref("sync", tenantParam)} icon="sync" title={t("nav.offlineSync")} value={shell?.syncText} />
          <SettingsRow href={sectionHref("backup", tenantParam)} icon="cloud" title={t("backup.tab")} value={lastBackup ? new Date(lastBackup).toLocaleString(i18n.resolvedLanguage === "ar" ? "ar-LB" : "en-GB") : undefined} />
          <SettingsRow href="/profile" icon="person" title={t("nav.profile")} />
          <SettingsRow href="/stats" icon="chart" title={t("nav.statistics")} />
          <SettingsRow icon="logout" onOpen={() => void shell.signOut()} title={t("nav.logout")} />
        </>}
      </ul>
    </div>
  );
}
