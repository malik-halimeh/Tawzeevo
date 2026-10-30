import i18n from "../i18n";

/** Display only: never use the result in an input, calculation, export or API payload. */
export function formatMoney(value: string | number, currency: string, lang: "en" | "ar"): string {
  const text = String(value);
  if (text === "—") return text;
  const match = /^([+-]?)(\d+)(?:\.(\d*))?(?:e([+-]?\d+))?$/i.exec(text);
  if (!match) return text;

  // Expand numeric exponent notation using strings; money strings never pass through Number.
  const digits = match[2]! + (match[3] ?? "");
  const point = match[2]!.length + Number(match[4] ?? 0);
  let integer = point <= 0 ? "0" : digits.slice(0, point).padEnd(point, "0");
  let fraction = point <= 0 ? "0".repeat(-point) + digits : digits.slice(point);
  integer = integer.replace(/^0+(?=\d)/, "");
  const max = currency === "LBP" ? 2 : 4;
  const min = currency === "LBP" ? 0 : 2;
  if (fraction.length > max) {
    // ROUND_HALF_UP on the magnitude, including carry into arbitrarily large integers.
    const units = BigInt(integer + fraction.slice(0, max).padEnd(max, "0"))
      + (fraction[max]! >= "5" ? 1n : 0n);
    const rounded = units.toString().padStart(max + 1, "0");
    integer = rounded.slice(0, -max);
    fraction = rounded.slice(-max);
  }
  fraction = fraction.replace(/0+$/, "").padEnd(min, "0");
  const number = integer.replace(/\B(?=(\d{3})+(?!\d))/g, ",") + (fraction ? `.${fraction}` : "");
  const sign = currency === "USD" ? "$" : currency === "EUR" ? "€" : currency === "LBP" && lang === "ar" ? "ل.ل" : currency;
  return `${match[1] === "-" ? "-" : ""}${number} ${sign}`;
}

/** Components already subscribe via useTranslation; read that same current language at render. */
export function money(value: string | number, currency: string): string {
  return formatMoney(value, currency, i18n.language.startsWith("ar") ? "ar" : "en");
}
