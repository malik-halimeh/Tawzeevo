/**
 * Server-side access to the public catalog API (PHASE_05.md C/L). Every function runs in a server
 * component; the browser never receives an API secret because there is none to receive.
 */
export interface PublicCategory {
  id: string;
  name_en: string;
  name_ar: string;
  slug: string;
  product_count: number;
}

export interface PublicImage {
  id: string;
  url: string;
  width: number;
  height: number;
  alt_text: string | null;
}

export interface PublicProduct {
  id: string;
  category_id: string;
  name: string;
  name_ar: string | null;
  barcode: string | null;
  currency: string;
  price: string;
  price_basis: "PIECE" | "BOX";
  packaging: { pieces_per_box: number | null; piece_price: string; box_price: string | null };
  images: PublicImage[];
}

export interface PublicProductPage {
  items: PublicProduct[];
  page: number;
  page_size: number;
  total: number;
  has_more: boolean;
}

export interface PublicStorefront {
  slug: string;
  redirected_from: string | null;
  name: string;
  accepting_orders: boolean;
  categories: PublicCategory[];
  published_products: number;
  generated_at: string;
}

export class CatalogError extends Error {
  constructor(readonly status: number, readonly code: string, message: string) {
    super(message);
  }
}

export function apiBase(): string {
  return (process.env.API_BASE_URL ?? "http://127.0.0.1:8000").replace(/\/$/, "");
}

/** The base the browser uses for image URLs returned by the API (relative paths). */
export function publicApiBase(): string {
  return (process.env.NEXT_PUBLIC_API_BASE_URL ?? process.env.API_BASE_URL ?? "http://127.0.0.1:8000").replace(/\/$/, "");
}

async function get<T>(path: string): Promise<T> {
  const response = await fetch(`${apiBase()}${path}`, { next: { revalidate: 60 } });
  if (!response.ok) {
    const body = (await response.json().catch(() => ({}))) as { detail?: { code?: string; message?: string } };
    throw new CatalogError(response.status, body.detail?.code ?? "CATALOG_ERROR", body.detail?.message ?? `Catalog request failed (${response.status})`);
  }
  return (await response.json()) as T;
}

export function fetchStorefront(slug: string): Promise<PublicStorefront> {
  return get<PublicStorefront>(`/api/v1/public/${encodeURIComponent(slug)}/catalog`);
}

export function fetchProducts(slug: string, options: { query?: string; categoryId?: string; page?: number; pageSize?: number } = {}): Promise<PublicProductPage> {
  const params = new URLSearchParams();
  if (options.query) params.set("query", options.query);
  if (options.categoryId) params.set("category_id", options.categoryId);
  if (options.page) params.set("page", String(options.page));
  if (options.pageSize) params.set("page_size", String(options.pageSize));
  const suffix = params.size ? `?${params.toString()}` : "";
  return get<PublicProductPage>(`/api/v1/public/${encodeURIComponent(slug)}/catalog/products${suffix}`);
}

export function fetchProduct(slug: string, productId: string): Promise<PublicProduct> {
  return get<PublicProduct>(`/api/v1/public/${encodeURIComponent(slug)}/catalog/products/${encodeURIComponent(productId)}`);
}

/** Validates a route slug before any request; the API repeats the check. */
export function isValidSlug(slug: string): boolean {
  return /^[a-z0-9](?:[a-z0-9-]{1,48}[a-z0-9])?$/.test(slug) && slug.length >= 3;
}

export function fetchFeatured(slug: string): Promise<{ items: PublicProduct[] }> {
  return get<{ items: PublicProduct[] }>(`/api/v1/public/${encodeURIComponent(slug)}/catalog/featured`);
}

export function fetchRecommended(slug: string, limit = 8): Promise<{ items: PublicProduct[] }> {
  return get<{ items: PublicProduct[] }>(`/api/v1/public/${encodeURIComponent(slug)}/catalog/recommended?limit=${limit}`);
}
