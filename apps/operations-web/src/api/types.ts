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
