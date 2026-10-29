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
