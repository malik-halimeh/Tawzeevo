export type SystemUserType = "admin" | "client";
export type TenantStatus = "ACTIVE" | "SUSPENDED" | "CLOSED";
export type TenantApplicationStatus = "PENDING" | "APPROVED" | "REJECTED";
export type AccessStatus = "current" | "grace" | "overdue";
export type SuspensionReason =
  | "SUBSCRIPTION_OVERDUE"
  | "ADMINISTRATIVE"
  | "SECURITY"
  | "OTHER";

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
