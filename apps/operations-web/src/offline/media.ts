import { API_BASE_URL, ApiError, refreshAccessToken } from "../api/client";
import { type LocalMedia, openLocalDatabase } from "./db";

/**
 * Offline media queue (PHASE_04.md K). A picked image is stored as bytes with its checksum and
 * the entity it belongs to; the upload retries idempotently (the server maps identical bytes for
 * the same product to the existing asset). Object URLs are render-only and never persisted.
 */
export const MEDIA_MAX_ATTEMPTS = 8;

function blobBytes(blob: Blob): Promise<ArrayBuffer> {
  if (typeof blob.arrayBuffer === "function") return blob.arrayBuffer();
  // Older WebViews expose only FileReader.
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(reader.result as ArrayBuffer);
    reader.onerror = () => reject(reader.error ?? new Error("read failed"));
    reader.readAsArrayBuffer(blob);
  });
}

async function sha256Hex(bytes: ArrayBuffer): Promise<string> {
  const digest = await crypto.subtle.digest("SHA-256", bytes);
  return [...new Uint8Array(digest)].map((byte) => byte.toString(16).padStart(2, "0")).join("");
}

export async function queueProductImage(
  tenantId: string,
  membershipId: string,
  productId: string,
  blob: Blob,
  altText: string | null = null,
): Promise<LocalMedia> {
  const db = openLocalDatabase(tenantId, membershipId);
  const bytes = await blobBytes(blob);
  const record: LocalMedia = {
    local_id: crypto.randomUUID(),
    tenant_id: tenantId,
    entity_type: "tenant_product",
    entity_id: productId,
    bytes,
    checksum: await sha256Hex(bytes),
    content_type: blob.type || "application/octet-stream",
    byte_size: blob.size,
    state: "queued",
    attempts: 0,
    remote_id: null,
    last_error: altText,
  };
  await db.media.put(record);
  return record;
}

let accessTokenProvider: () => string | null = () => null;
/** The app registers how to read the in-memory access token (never persisted here). */
export function setMediaTokenProvider(provider: () => string | null): void {
  accessTokenProvider = provider;
}

async function upload(tenantId: string, record: LocalMedia, token: string | null): Promise<Response> {
  const form = new FormData();
  const file = new Blob([record.bytes], { type: record.content_type });
  form.append("file", file, `${record.local_id}.${record.content_type.split("/")[1] ?? "bin"}`);
  if (record.last_error) form.append("alt_text", record.last_error);
  const init: RequestInit = { method: "POST", body: form, credentials: "include" };
  if (token) init.headers = { Authorization: `Bearer ${token}` };
  return fetch(`${API_BASE_URL}/api/v1/tenants/${tenantId}/products/${record.entity_id}/images?tenant_id=${tenantId}`, init);
}

export interface MediaFlushSummary {
  uploaded: number;
  failed: number;
  remaining: number;
}

/** Upload queued media in order; identical retries are deduplicated by the server. */
export async function flushMedia(tenantId: string, membershipId: string): Promise<MediaFlushSummary> {
  const db = openLocalDatabase(tenantId, membershipId);
  const queued = await db.media.where("state").anyOf(["queued", "failed"]).toArray();
  const summary: MediaFlushSummary = { uploaded: 0, failed: 0, remaining: 0 };
  for (const record of queued) {
    if (record.attempts >= MEDIA_MAX_ATTEMPTS) { summary.remaining += 1; continue; }
    await db.media.put({ ...record, state: "uploading", attempts: record.attempts + 1 });
    try {
      let response = await upload(tenantId, record, accessTokenProvider());
      if (response.status === 401) response = await upload(tenantId, record, await refreshAccessToken());
      if (!response.ok) {
        const detail = (await response.json().catch(() => ({}))) as { detail?: { code?: string; message?: string } };
        throw new ApiError(response.status, detail.detail?.code ?? "UPLOAD_FAILED", detail.detail?.message ?? `Upload failed (${response.status})`);
      }
      const asset = (await response.json()) as { id: string };
      await db.media.put({ ...record, state: "uploaded", attempts: record.attempts + 1, remote_id: asset.id });
      summary.uploaded += 1;
    } catch (error) {
      const retryable = error instanceof TypeError || (error instanceof ApiError && error.status >= 500);
      await db.media.put({ ...record, state: "failed", attempts: record.attempts + 1, last_error: record.last_error });
      summary.failed += 1;
      if (!retryable) await db.media.put({ ...record, state: "failed", attempts: MEDIA_MAX_ATTEMPTS });
    }
  }
  return summary;
}

export async function listMedia(tenantId: string, membershipId: string): Promise<LocalMedia[]> {
  return openLocalDatabase(tenantId, membershipId).media.toArray();
}
