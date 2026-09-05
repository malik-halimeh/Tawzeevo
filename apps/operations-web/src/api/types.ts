export type SystemUserType = "admin" | "client";
export type TenantStatus = "ACTIVE" | "SUSPENDED" | "CLOSED";
export type TenantApplicationStatus = "PENDING" | "APPROVED" | "REJECTED";
export type AccessStatus = "current" | "grace" | "overdue";
export type SuspensionReason =
  | "SUBSCRIPTION_OVERDUE"
  | "ADMINISTRATIVE"
  | "SECURITY"
  | "OTHER";
export type TenantRole = "owner" | "driver";
export type CustomerGrade = "A+" | "A" | "B+" | "B";
export type BarcodePackageLevel = "PIECE" | "BOX";
export type BarcodeOwnership = "MASTER" | "TENANT";
export type ProductPriceBasis = "PIECE" | "BOX";
export type MediaOwnership = "MASTER" | "TENANT";
export type PriceResolutionSource = "NORMAL" | "GRADE_DISCOUNT" | "EXPLICIT_GRADE_PRICE";
export type InvoiceStatus = "DRAFT" | "CONFIRMED" | "CANCELLED";
export type PaymentDirection =
  | "CUSTOMER_RECEIPT"
  | "CUSTOMER_RECEIPT_REVERSAL"
  | "CUSTOMER_REFUND";
export type AllocationKind = "APPLY" | "REVERSAL";
export type CatalogMatchType = "EXACT" | "PREFIX" | "FUZZY";

export interface TenantContext {
  membership_id: string;
  tenant_id: string;
  tenant_name: string;
  tenant_status: TenantStatus;
  role: TenantRole;
}

export interface TenantContextListResponse {
  tenants: TenantContext[];
}

export interface Customer {
  id: string;
  tenant_id: string;
  name: string;
  phone: string;
  address: string | null;
  latitude: string | null;
  longitude: string | null;
  grade: CustomerGrade | null;
  created_at: string;
  updated_at: string;
}

export interface CustomerSearchResponse {
  customers: Customer[];
}

export interface Category {
  id: string;
  tenant_id: string;
  master_category_id: string | null;
  name_en: string;
  name_ar: string;
  slug: string;
  display_order: number;
  is_active: boolean;
  archived_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface CategoryListResponse {
  categories: Category[];
}

export interface ProductBarcode {
  id: string;
  barcode: string;
  package_level: BarcodePackageLevel;
  ownership: BarcodeOwnership;
}

export interface ProductImage {
  id: string;
  ownership: MediaOwnership;
  content_type: string;
  byte_size: number;
  width: number;
  height: number;
  display_order: number;
  alt_text: string | null;
  url: string;
}

export interface GradeDiscount {
  id: string;
  tenant_id: string;
  grade: CustomerGrade;
  discount_percent: string;
  created_at: string;
  updated_at: string;
}

export interface GradeDiscountListResponse {
  discounts: GradeDiscount[];
}

export interface ProductGradePrice {
  id: string;
  tenant_id: string;
  tenant_product_id: string;
  grade: CustomerGrade;
  unit_price: string;
  created_at: string;
  updated_at: string;
}

export interface ResolvedProductPrice {
  product_id: string;
  customer_id: string;
  customer_grade: CustomerGrade | null;
  source: PriceResolutionSource;
  discount_percent: string | null;
  currency: string;
  price_basis: ProductPriceBasis;
  basis_price: string;
  piece_price: string;
  box_price: string | null;
}

export interface MasterProduct {
  id: string;
  master_category_id: string | null;
  name: string;
  barcodes: ProductBarcode[];
  images: ProductImage[];
  created_at: string;
  updated_at: string;
}

export interface TenantProduct {
  id: string;
  tenant_id: string;
  category_id: string;
  master_product_id: string | null;
  name: string;
  barcode: string;
  barcodes: ProductBarcode[];
  images: ProductImage[];
  grade_prices: ProductGradePrice[];
  is_published: boolean;
  unit_price: string;
  currency: string;
  price_basis: ProductPriceBasis;
  pieces_per_box: number | null;
  piece_price: string;
  box_price: string | null;
  created_at: string;
  updated_at: string;
}

export interface TenantProductListResponse {
  products: TenantProduct[];
}

export interface BarcodeLookupResponse {
  barcode: string;
  ownership: BarcodeOwnership;
  package_level: BarcodePackageLevel;
  master_product: MasterProduct | null;
  tenant_product: TenantProduct | null;
}

export interface InvoiceCatalogMatch {
  product_id: string;
  name: string;
  barcode: string;
  package_level: ProductPriceBasis;
  currency: string;
  price_basis: ProductPriceBasis;
  unit_price: string;
  image_url: string | null;
  match_type: CatalogMatchType;
  score: string;
}

export interface InvoiceCatalogSearchResponse {
  matches: InvoiceCatalogMatch[];
}

export interface ParsedInvoiceItem {
  source_text: string;
  normalized_query: string;
  quantity: string;
  resolution: "EXACT" | "AMBIGUOUS" | "UNRESOLVED";
  selected: InvoiceCatalogMatch | null;
  suggestions: InvoiceCatalogMatch[];
}

export interface InvoiceItemParserResponse {
  threshold: string;
  items: ParsedInvoiceItem[];
}

export interface ProductCostOption {
  supplier_id: string;
  supplier_name: string;
  is_preferred: boolean;
  product_cost_entry_id: string | null;
  unit_cost: string | null;
  currency: string;
  cost_basis: ProductPriceBasis;
  pieces_per_box: number | null;
  effective_at: string | null;
}

export interface ProductCostOptionsResponse {
  options: ProductCostOption[];
}

export interface InvoiceEditorItem {
  id: string;
  line_number: number;
  product_id: string | null;
  product_name: string;
  barcode: string | null;
  media_snapshot: { images?: ProductImage[] };
  quantity: string;
  price_basis: ProductPriceBasis;
  pieces_per_box: number | null;
  normal_unit_price: string;
  effective_unit_price: string;
  customer_grade: CustomerGrade | null;
  price_source: PriceResolutionSource;
  grade_discount_percent: string | null;
  line_discount: string;
  line_markup: string;
  line_total: string;
  supplier_id: string | null;
  product_cost_entry_id: string | null;
  unit_cost: string | null;
  cost_currency: string | null;
  cost_basis: ProductPriceBasis | null;
  cost_pieces_per_box: number | null;
  cost_source_type: string | null;
  is_cost_override: boolean;
  cost_override_reason: string | null;
}

export interface InvoiceEditorResponse {
  id: string;
  tenant_id: string;
  status: InvoiceStatus;
  official_invoice_number: string | null;
  confirmed_at: string | null;
  customer_id: string;
  customer_snapshot: Record<string, unknown>;
  current_revision_id: string;
  server_revision_number: number;
  pricing_version: "pricing-v1";
  currency: string;
  prior_balance: string;
  subtotal: string;
  discount_total: string;
  markup_total: string;
  net_sales: string;
  total_due: string;
  items: InvoiceEditorItem[];
  created_at: string;
  updated_at: string;
}

export interface InvoiceHistoryRevision extends InvoiceEditorResponse {
  predecessor_revision_id: string | null;
  reason: string | null;
  revision_created_at: string;
  is_current: boolean;
  ledger_delta: string | null;
}

export interface InvoiceHistoryResponse {
  revisions: InvoiceHistoryRevision[];
}

export interface CustomerBalance {
  currency: string;
  balance: string;
}

export interface CustomerBalancesResponse {
  customer_id: string;
  customer_name: string;
  balances: CustomerBalance[];
}

export interface FinancialSettingsResponse {
  tenant_id: string;
  customer_overdue_threshold_days: number | null;
}

export interface CustomerDebt {
  customer_id: string;
  customer_name: string;
  customer_phone: string;
  currency: string;
  balance: string;
  oldest_unpaid_at: string | null;
  overdue_age_days: number | null;
  overdue_threshold_days: number | null;
  is_overdue: boolean;
  alert_key: string | null;
}

export interface CustomerDebtListResponse {
  debts: CustomerDebt[];
}

export interface CustomerObligation {
  target_ledger_entry_id: string;
  source_type: string;
  source_id: string | null;
  label: string;
  effective_at: string;
  original_amount: string;
  allocated_amount: string;
  outstanding_amount: string;
}

export interface CustomerObligationListResponse {
  customer_id: string;
  currency: string;
  obligations: CustomerObligation[];
}

export interface PaymentAllocation {
  id: string;
  target_ledger_entry_id: string;
  amount: string;
  kind: AllocationKind;
  reverses_allocation_id: string | null;
  effective_amount: string;
  created_at: string;
}

export interface CustomerPaymentResponse {
  id: string;
  tenant_id: string;
  customer_id: string;
  direction: PaymentDirection;
  amount: string;
  currency: string;
  method: string | null;
  reference: string | null;
  paid_at: string;
  recorded_at: string;
  reverses_payment_id: string | null;
  notes: string | null;
  allocated_amount: string;
  unallocated_amount: string;
  customer_balance: string;
  available_credit: string;
  allocations: PaymentAllocation[];
}

export interface User {
  id: string;
  first_name: string;
  last_name: string;
  email: string;
  phone: string;
  city: string;
  age: number;
  type: SystemUserType;
  created_at: string;
  updated_at: string;
}

export interface TokenResponse {
  access_token: string;
  token_type: "bearer";
  expires_in: number;
}

export interface UserInput {
  first_name: string;
  last_name: string;
  email: string;
  phone: string;
  city: string;
  age: number;
  password: string;
}

export interface UserListResponse {
  page: number;
  limit: number;
  total: number;
  total_pages: number;
  users: User[];
}

export interface TenantApplication {
  id: string;
  applicant_user_id: string;
  business_name: string;
  status: TenantApplicationStatus;
  reviewed_by_user_id: string | null;
  reviewed_at: string | null;
  review_notes: string | null;
  tenant_id: string | null;
  created_at: string;
  updated_at: string;
}

export interface TenantApplicationListResponse {
  page: number;
  limit: number;
  total: number;
  total_pages: number;
  applications: TenantApplication[];
}

export interface Tenant {
  id: string;
  name: string;
  status: TenantStatus;
  access_until: string | null;
  grace_until: string | null;
  access_status: AccessStatus;
  suspension_reason: SuspensionReason | null;
  activated_at: string | null;
  suspended_at: string | null;
  reactivated_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface TenantListResponse {
  page: number;
  limit: number;
  total: number;
  total_pages: number;
  tenants: Tenant[];
}

export interface CityCount {
  city: string;
  count: number;
}
