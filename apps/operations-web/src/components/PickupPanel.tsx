import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";

import { apiRequest } from "../api/client";
import type { ProductPriceBasis } from "../api/types";
import { ErrorState } from "./Ui";

/**
 * Runner projection (PHASE_06.md F): the procurement lists assigned to the signed-in member,
 * grouped by supplier with identity and location, quantities only. The API never sends a price,
 * cost or estimate here, so none can be shown.
 */
interface PickupItem { item_id: string; product_name: string; price_basis: ProductPriceBasis; pieces_per_box: number | null; remaining_quantity: string; notes: string | null }
interface PickupSupplier { supplier_id: string | null; supplier_name: string | null; contact_name: string | null; contact_phone: string | null; address: string | null; latitude: string | null; longitude: string | null; items: PickupItem[] }
interface PickupList { list_id: string; title: string; status: string; notes: string | null; suppliers: PickupSupplier[] }

export function PickupPanel({ tenantId }: { tenantId: string }) {
  const { t } = useTranslation();
  const [lists, setLists] = useState<PickupList[]>();
  const [error, setError] = useState<unknown>();

  useEffect(() => {
    apiRequest<{ lists: PickupList[] }>(`/api/v1/procurement/my-pickups?tenant_id=${tenantId}`).then((body) => setLists(body.lists)).catch(setError);
  }, [tenantId]);

  return (
    <section className="pickup-panel" aria-labelledby="pickup-title">
      <header>
        <p className="section-kicker">{t("pickup.kicker")}</p>
        <h3 id="pickup-title">{t("pickup.title")}</h3>
        <p>{t("pickup.body")}</p>
      </header>
      {error ? <ErrorState error={error} /> : null}
      {lists && lists.length === 0 ? <p className="muted">{t("pickup.empty")}</p> : null}
      {lists?.map((list) => (
        <article className="content-card" key={list.list_id} aria-label={list.title}>
          <h4>{list.title}</h4>
          {list.notes ? <p className="muted">{list.notes}</p> : null}
          {list.suppliers.map((supplier) => (
            <div className="pickup-supplier" key={supplier.supplier_id ?? "none"}>
              <h5>{supplier.supplier_name ?? t("pickup.noSupplier")}</h5>
              {supplier.contact_name || supplier.contact_phone ? <p className="muted">{supplier.contact_name}{supplier.contact_phone ? <> · <a dir="ltr" href={`tel:${supplier.contact_phone}`}>{supplier.contact_phone}</a></> : null}</p> : null}
              {supplier.address ? <p className="muted">{supplier.address}</p> : null}
              {supplier.latitude && supplier.longitude ? <p className="muted"><a href={`https://www.google.com/maps?q=${supplier.latitude},${supplier.longitude}`} rel="noreferrer" target="_blank">{t("pickup.openMap")}</a></p> : null}
              <ul className="pickup-items">
                {supplier.items.map((item) => (
                  <li key={item.item_id}><strong dir="ltr">{item.remaining_quantity}</strong> × {item.product_name} <small className="muted">({item.price_basis === "BOX" ? t("tenantWorkspace.box") : t("tenantWorkspace.piece")}{item.pieces_per_box ? ` ×${item.pieces_per_box}` : ""})</small>{item.notes ? <> — <span className="muted">{item.notes}</span></> : null}</li>
                ))}
              </ul>
            </div>
          ))}
        </article>
      ))}
    </section>
  );
}
