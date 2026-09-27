import type { InvoiceEditorResponse, ProductPriceBasis } from "../api/types";

/**
 * Editor lines rebuilt from a saved revision, exactly as the server rebuilds them for orders
 * (orders._items_from_revision), so an invoice opened by link can be edited or revised (D-101):
 * product lines keep product, barcode, quantity, basis, line discount and markup, supplier and any
 * cost override with its reason; manual lines keep name, unit price and pieces per box. The
 * invoice-level discount and markup are what remains after the line amounts.
 */
export interface RebuiltLine {
  productId?: string | undefined;
  manualName?: string | undefined;
  name: string;
  imageUrl?: string | undefined;
  barcode?: string | undefined;
  quantity: string;
  basis: ProductPriceBasis;
  piecesPerBox?: number | undefined;
  manualUnitPrice?: string | undefined;
  lineDiscount: string;
  lineMarkup: string;
  supplierId?: string | undefined;
  costOverride: string;
  costOverrideReason: string;
}

const SCALE = 10000n;

/** A server money string ("12.5000", "-3", "0.25") as ten-thousandths, without floating point. */
function toUnits(value: string): bigint {
  const trimmed = value.trim();
  const negative = trimmed.startsWith("-");
  const [whole = "0", fraction = ""] = trimmed.replace(/^[-+]/, "").split(".");
  const units = BigInt(whole || "0") * SCALE + BigInt((fraction + "0000").slice(0, 4));
  return negative ? -units : units;
}

function fromUnits(units: bigint): string {
  if (units === 0n) return "0";
  const negative = units < 0n;
  const absolute = negative ? -units : units;
  const whole = absolute / SCALE;
  const fraction = (absolute % SCALE).toString().padStart(4, "0").replace(/0+$/, "");
  return `${negative ? "-" : ""}${whole}${fraction ? `.${fraction}` : ""}`;
}

/** `total` minus every part, exactly (4 decimal places, as the server stores money). */
export function moneyMinus(total: string, parts: string[]): string {
  return fromUnits(parts.reduce((left, part) => left - toUnits(part), toUnits(total)));
}

/** A stored amount as an editor expression: "2.0000" becomes "2". */
export function plainAmount(value: string): string {
  return fromUnits(toUnits(value));
}

export function rebuildFromRevision(invoice: InvoiceEditorResponse): { lines: RebuiltLine[]; invoiceDiscount: string; invoiceMarkup: string } {
  const lines = invoice.items.map((item): RebuiltLine => {
    const common = {
      name: item.product_name,
      quantity: plainAmount(item.quantity),
      basis: item.price_basis,
      lineDiscount: plainAmount(item.line_discount),
      lineMarkup: plainAmount(item.line_markup),
      costOverride: item.is_cost_override && item.unit_cost !== null ? plainAmount(item.unit_cost) : "",
      costOverrideReason: item.is_cost_override ? item.cost_override_reason ?? "" : "",
    };
    if (item.product_id) {
      return {
        ...common,
        productId: item.product_id,
        barcode: item.barcode ?? undefined,
        piecesPerBox: item.pieces_per_box ?? undefined,
        supplierId: item.supplier_id ?? undefined,
        imageUrl: item.media_snapshot.images?.[0]?.url,
      };
    }
    return {
      ...common,
      manualName: item.product_name,
      manualUnitPrice: plainAmount(item.effective_unit_price),
      piecesPerBox: item.pieces_per_box ?? undefined,
      supplierId: item.supplier_id ?? undefined,
    };
  });
  return {
    lines,
    invoiceDiscount: moneyMinus(invoice.discount_total, invoice.items.map((item) => item.line_discount)),
    invoiceMarkup: moneyMinus(invoice.markup_total, invoice.items.map((item) => item.line_markup)),
  };
}
