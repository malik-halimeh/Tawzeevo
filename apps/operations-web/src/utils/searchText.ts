/**
 * The literal search folding the server uses for customer names (apps/api text_search.py), so a
 * name typed offline finds the same records it finds online: أ إ آ ٱ → ا, ى → ي, ة → ه,
 * Arabic-Indic and Extended Arabic-Indic digits → 0-9, tatweel and harakat dropped, lower case.
 */
const SOURCE = "أإآٱىة٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹";
const TARGET = "اااايه01234567890123456789";
const MAPPED = new Map([...SOURCE].map((char, index) => [char, TARGET[index]!]));
const TATWEEL = 0x0640;
const FIRST_HARAKA = 0x064b;
const LAST_HARAKA = 0x0652;

export function foldSearchText(value: string): string {
  let folded = "";
  for (const char of value) {
    const code = char.codePointAt(0)!;
    if (code === TATWEEL || (code >= FIRST_HARAKA && code <= LAST_HARAKA)) continue;
    folded += MAPPED.get(char) ?? char;
  }
  return folded.toLowerCase();
}

/** True when the text holds a letter (Latin or Arabic), so it reads as a name rather than a phone. */
export function hasLetters(value: string): boolean {
  return /\p{L}/u.test(value);
}

/** Catalog search folding; keep the customer search's literal substring semantics unchanged. */
function foldProductText(value: string): string {
  return foldSearchText(value.normalize("NFKC"))
    .replace(/[\u0610-\u061a\u0653-\u065f\u0670\u06d6-\u06ed]/gu, "")
    .replace(/ؤ/gu, "و").replace(/ئ/gu, "ي")
    .replace(/[^\p{L}\p{N}_\s-]/gu, " ").trim().replace(/\s+/gu, " ");
}

/** List filter: every query word appears somewhere in the name (any order); a barcode contains the query.
 * Kept as forgiving as the earlier substring filter; the invoice picker ranks by word starts on the server. */
export function productMatchesSearch(product: { name: string; name_ar?: string | null; barcodes: { barcode: string }[] }, query: string): boolean {
  const needle = foldProductText(query);
  if (!needle) return true;
  const words = needle.split(" ");
  return [product.name, product.name_ar ?? ""].some((name) => {
    const folded = foldProductText(name);
    return words.every((word) => folded.includes(word));
  }) || product.barcodes.some(({ barcode }) => foldProductText(barcode).includes(needle));
}
