import "fake-indexeddb/auto";

import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";

import { deleteLocalDatabase } from "./db";
import { MEDIA_MAX_ATTEMPTS, flushMedia, listMedia, queueProductImage, setMediaTokenProvider } from "./media";

const tenant = "11111111-1111-4111-8111-111111111111";
const membership = "22222222-2222-4222-8222-222222222222";
const product = "33333333-3333-4333-8333-333333333333";

type Mode = "ok" | "network" | "server-error" | "rejected";
type Seen = { url: string; auth: string | undefined; file: File | null };

function installUpload(mode: Mode, seen: Seen[]) {
  vi.stubGlobal("fetch", vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
    const url = input instanceof Request ? input.url : input.toString();
    const form = init?.body instanceof FormData ? init.body : null;
    const file = form?.get("file");
    seen.push({ url, auth: (init?.headers as Record<string, string> | undefined)?.Authorization, file: file instanceof File ? file : null });
    if (mode === "network") return Promise.reject(new TypeError("Failed to fetch"));
    if (mode === "server-error") return Promise.resolve(Response.json({ detail: { code: "DOWN", message: "maintenance" } }, { status: 503 }));
    if (mode === "rejected") return Promise.resolve(Response.json({ detail: { code: "UNSUPPORTED_MEDIA_TYPE", message: "not an image" } }, { status: 415 }));
    return Promise.resolve(Response.json({ id: "asset-1" }, { status: 201 }));
  }));
}

describe("offline media queue", () => {
  beforeEach(async () => { localStorage.clear(); await deleteLocalDatabase(tenant, membership); setMediaTokenProvider(() => "token-1"); });
  afterEach(() => { vi.unstubAllGlobals(); });

  test("a picked image is stored with its checksum and uploaded once with the bearer token", async () => {
    const seen: Seen[] = [];
    installUpload("ok", seen);
    const blob = new Blob([new Uint8Array([137, 80, 78, 71, 1, 2, 3])], { type: "image/png" });
    const record = await queueProductImage(tenant, membership, product, blob);
    expect(record).toMatchObject({ state: "queued", byte_size: 7, content_type: "image/png", attempts: 0 });
    expect(record.checksum).toMatch(/^[0-9a-f]{64}$/);

    expect(await flushMedia(tenant, membership)).toEqual({ uploaded: 1, failed: 0, remaining: 0 });
    expect(seen).toHaveLength(1);
    expect(seen[0]?.url).toContain(`/api/v1/tenants/${tenant}/products/${product}/images`);
    expect(seen[0]?.auth).toBe("Bearer token-1");
    expect(seen[0]?.file?.name).toBe(`${record.local_id}.png`);
    expect((await listMedia(tenant, membership))[0]).toMatchObject({ state: "uploaded", remote_id: "asset-1", attempts: 1 });
    // Uploaded media is never sent again.
    expect(await flushMedia(tenant, membership)).toEqual({ uploaded: 0, failed: 0, remaining: 0 });
    expect(seen).toHaveLength(1);
  });

  test("network and server failures stay retryable; a rejected file stops retrying", async () => {
    const seen: Seen[] = [];
    installUpload("network", seen);
    await queueProductImage(tenant, membership, product, new Blob(["x"], { type: "image/jpeg" }));
    expect(await flushMedia(tenant, membership)).toEqual({ uploaded: 0, failed: 1, remaining: 0 });
    expect((await listMedia(tenant, membership))[0]).toMatchObject({ state: "failed", attempts: 1 });

    installUpload("server-error", seen);
    expect(await flushMedia(tenant, membership)).toEqual({ uploaded: 0, failed: 1, remaining: 0 });
    expect((await listMedia(tenant, membership))[0]).toMatchObject({ state: "failed", attempts: 2 });

    installUpload("ok", seen);
    expect(await flushMedia(tenant, membership)).toEqual({ uploaded: 1, failed: 0, remaining: 0 });
    expect((await listMedia(tenant, membership))[0]).toMatchObject({ state: "uploaded", attempts: 3, remote_id: "asset-1" });

    installUpload("rejected", seen);
    await queueProductImage(tenant, membership, product, new Blob(["not an image"], { type: "text/plain" }));
    expect(await flushMedia(tenant, membership)).toEqual({ uploaded: 0, failed: 1, remaining: 0 });
    const rejected = (await listMedia(tenant, membership)).find((row) => row.content_type === "text/plain");
    expect(rejected).toMatchObject({ state: "failed", attempts: MEDIA_MAX_ATTEMPTS });
    const before = seen.length;
    expect(await flushMedia(tenant, membership)).toEqual({ uploaded: 0, failed: 0, remaining: 1 });
    expect(seen).toHaveLength(before);
  });
});
