import type { ProductCostOption, ProductPriceBasis } from "../../api/types";

export interface AcceptedMatch {
  query: string;
  selected_product_id: string;
  score: string;
}

export interface EditorLine {
  key: string;
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
  acceptedMatch?: AcceptedMatch | undefined;
  costOptions: ProductCostOption[];
  supplierId?: string | undefined;
  costOverride: string;
  costOverrideReason: string;
}

export function money(value: string, currency: string) {
  return `${value} ${currency}`;
}

/**
 * Whether a line carries anything beyond its defaults behind "More": a discount or markup other
 * than 0, a cost override, a supplier other than the preferred one (a manual line: any supplier),
 * or a cost override still waiting for its required reason.
 */
export function lineNeedsMore(line: EditorLine): boolean {
  const preferred = line.costOptions.find((option) => option.is_preferred)?.supplier_id;
  const otherSupplier = line.productId
    ? line.costOptions.length > 0 && line.supplierId !== undefined && line.supplierId !== preferred
    : line.supplierId !== undefined;
  const missingReason = line.costOverride !== "" && !line.costOverrideReason.trim();
  return line.lineDiscount.trim() !== "0" || line.lineMarkup.trim() !== "0" || line.costOverride !== "" || otherSupplier || missingReason;
}
