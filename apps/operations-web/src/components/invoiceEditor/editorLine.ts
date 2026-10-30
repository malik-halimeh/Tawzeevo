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
  unitPrice?: string | undefined;
  initialBasis?: ProductPriceBasis | undefined;
  supplierTouched?: boolean | undefined;
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

/** Display/stepper convenience only. The server remains authoritative for validation and pricing.
 * Parse the calculator's numeric grammar without evaluating JavaScript. */
export function quantityValue(expression: string): number | undefined {
  const text = expression.replace(/[٠-٩۰-۹]/g, (digit) => String(digit.charCodeAt(0) - (digit <= "٩" ? 0x660 : 0x6f0)));
  const tokens = text.match(/\d+(?:\.\d+)?|[-+*/()]/g) ?? [];
  if (!text || text.length > 256 || tokens.join("") !== text.replace(/\s/g, "")) return undefined;
  let cursor = 0;
  const factor = (): number => {
    const token = tokens[cursor++];
    if (token === "+") return factor();
    if (token === "-") return -factor();
    if (token === "(") {
      const value = sum();
      if (tokens[cursor++] !== ")") throw new Error("parenthesis");
      return value;
    }
    if (!token || !/^(?:\d|\.)/.test(token)) throw new Error("number");
    return Number(token);
  };
  const term = (): number => {
    let value = factor();
    while (tokens[cursor] === "*" || tokens[cursor] === "/") {
      const operator = tokens[cursor++];
      const right = factor();
      value = operator === "*" ? value * right : value / right;
    }
    return value;
  };
  const sum = (): number => {
    let value = term();
    while (tokens[cursor] === "+" || tokens[cursor] === "-") {
      const operator = tokens[cursor++];
      const right = term();
      value = operator === "+" ? value + right : value - right;
    }
    return value;
  };
  try {
    const value = sum();
    return cursor === tokens.length && Number.isFinite(value) && Math.abs(value) < Number.MAX_SAFE_INTEGER ? Number(value.toFixed(4)) : undefined;
  } catch { return undefined; }
}
