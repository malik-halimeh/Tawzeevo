import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";

import { apiRequest } from "../api/client";
import type { CategoryListResponse } from "../api/types";
import { Icon } from "./Icon";
import type { StorefrontSettingsResponse } from "./StorefrontSettings";
import { sectionHref } from "./workspaceSections";

/**
 * "Get your shop ready" on Today, only while a new business still has no active category or no
 * published product. Each step is a link to the page where it is done; nothing is done for the owner.
 */
export function OwnerSetupChecklist({ tenantId }: { tenantId: string }) {
  const { t } = useTranslation();
  const categories = useQuery({
    queryKey: ["tenant-categories", tenantId],
    queryFn: () => apiRequest<CategoryListResponse>(`/api/v1/tenants/${tenantId}/categories?include_archived=true`),
  });
  const storefront = useQuery({
    queryKey: ["storefront-settings", tenantId],
    queryFn: () => apiRequest<StorefrontSettingsResponse>(`/api/v1/tenants/${tenantId}/storefront?tenant_id=${tenantId}`),
  });
  if (!categories.data || !storefront.data) return null;
  const hasCategory = categories.data.categories.some((category) => category.is_active);
  const hasProduct = storefront.data.published_products > 0;
  if (hasCategory && hasProduct) return null;
  const steps = [
    { key: "category", section: "categories", done: hasCategory },
    { key: "product", section: "products", done: hasProduct },
    { key: "link", section: "storefront", done: false },
    { key: "branding", section: "branding", done: false },
  ] as const;
  return (
    <section aria-labelledby="setup-title" className="owner-setup">
      <h2 className="section-title" id="setup-title">{t("setup.title")}</h2>
      <ol className="owner-setup-steps">
        {steps.map((step) => (
          <li className={step.done ? "is-done" : undefined} key={step.key}>
            {step.done ? <Icon name="check" small /> : null}
            <Link to={sectionHref(step.section, tenantId)}>{t(`setup.${step.key}`)}</Link>
            {step.done ? <span className="sr-only"> · {t("setup.done")}</span> : null}
          </li>
        ))}
      </ol>
    </section>
  );
}
