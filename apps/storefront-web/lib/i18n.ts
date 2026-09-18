/**
 * Storefront copy in English and Arabic. The language comes from the `lang` query parameter or the
 * `lang` cookie; Arabic renders right-to-left. No translation service, no runtime loading.
 */
export type Lang = "en" | "ar";

export const LANGS: Lang[] = ["en", "ar"];

export function normalizeLang(value: string | null | undefined): Lang {
  return value === "ar" ? "ar" : "en";
}

export function dirFor(lang: Lang): "rtl" | "ltr" {
  return lang === "ar" ? "rtl" : "ltr";
}

const COPY = {
  en: {
    storefront: "Storefront",
    categories: "Categories",
    allProducts: "All products",
    search: "Search",
    searchPlaceholder: "Product name or barcode",
    searchResults: "Results for “{query}”",
    noResults: "No products match.",
    noProducts: "This shop has not published any products yet.",
    products: "{count} product(s)",
    piece: "piece",
    box: "box",
    perPiece: "per piece",
    perBox: "per box of {count}",
    barcode: "Barcode",
    notAccepting: "This shop is not taking new orders at the moment. You can still browse.",
    pausedTitle: "Orders paused",
    backToShop: "Back to the shop",
    page: "Page {page}",
    next: "Next",
    previous: "Previous",
    language: "العربية",
    notFoundTitle: "No shop at this address",
    notFoundBody: "Check the link you were given; the shop may have changed its address.",
    productNotFound: "This product is not available in this shop.",
    poweredBy: "Powered by Tawzeevo",
    skipToContent: "Skip to content",
  },
  ar: {
    storefront: "المتجر",
    categories: "الفئات",
    allProducts: "كل المنتجات",
    search: "بحث",
    searchPlaceholder: "اسم المنتج أو الباركود",
    searchResults: "نتائج البحث عن «{query}»",
    noResults: "لا توجد منتجات مطابقة.",
    noProducts: "لم ينشر هذا المتجر أي منتجات بعد.",
    products: "{count} منتج",
    piece: "قطعة",
    box: "صندوق",
    perPiece: "للقطعة",
    perBox: "للصندوق ({count} قطعة)",
    barcode: "الباركود",
    notAccepting: "هذا المتجر لا يستقبل طلبات جديدة حالياً. يمكنك التصفح.",
    pausedTitle: "الطلبات متوقفة مؤقتاً",
    backToShop: "العودة إلى المتجر",
    page: "الصفحة {page}",
    next: "التالي",
    previous: "السابق",
    language: "English",
    notFoundTitle: "لا يوجد متجر على هذا العنوان",
    notFoundBody: "تحقق من الرابط الذي وصلك؛ ربما غيّر المتجر عنوانه.",
    productNotFound: "هذا المنتج غير متاح في هذا المتجر.",
    poweredBy: "بدعم من توزيعو",
    skipToContent: "انتقل إلى المحتوى",
  },
} as const;

export type CopyKey = keyof (typeof COPY)["en"];

export function t(lang: Lang, key: CopyKey, values: Record<string, string | number> = {}): string {
  let text: string = COPY[lang][key];
  for (const [name, value] of Object.entries(values)) text = text.replaceAll(`{${name}}`, String(value));
  return text;
}

export function otherLang(lang: Lang): Lang {
  return lang === "ar" ? "en" : "ar";
}
