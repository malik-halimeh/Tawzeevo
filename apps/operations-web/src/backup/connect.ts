import { apiRequest } from "../api/client";

/** Shared between the Backup desk and the Google callback page (kept out of components for fast refresh). */
export interface BackupConnection {
  id: string;
  provider: string;
  account_email: string;
  folder_name: string;
  scopes: string;
  connected_at: string;
  last_error: string | null;
}

/** The tenant awaiting a Google callback is kept only for the redirect round-trip. */
export const PENDING_CONNECT_KEY = "tawzeevo.backup.connect.tenant";
/** The outcome handed from the callback page to the workspace, read once. */
export const CONNECT_RESULT_KEY = "tawzeevo.backup.connect.result";

export function completeGoogleConnect(tenantId: string, code: string, state: string): Promise<BackupConnection> {
  return apiRequest<BackupConnection>(`/api/v1/tenants/${tenantId}/backup/google/connect?tenant_id=${tenantId}`, {
    method: "POST",
    body: JSON.stringify({ code, state }),
  });
}
