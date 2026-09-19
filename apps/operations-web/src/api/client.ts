import type { TokenResponse } from "./types";

const configuredBaseUrl = import.meta.env.VITE_API_BASE_URL as string | undefined;
export const API_BASE_URL = (configuredBaseUrl ?? "http://localhost:8000").replace(/\/$/, "");

let accessToken: string | null = null;
let refreshPromise: Promise<string> | null = null;

interface ErrorEnvelope {
  detail?: {
    code?: string;
    message?: string;
  };
}

export class ApiError extends Error {
  readonly status: number;
  readonly code: string;

  constructor(status: number, code: string, message: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
  }
}

export function setAccessToken(token: string | null) {
  accessToken = token;
}

async function parseError(response: Response): Promise<ApiError> {
  let payload: ErrorEnvelope | undefined;
  try {
    payload = (await response.json()) as ErrorEnvelope;
  } catch {
    payload = undefined;
  }
  return new ApiError(
    response.status,
    payload?.detail?.code ?? "REQUEST_FAILED",
    payload?.detail?.message ?? `Request failed with status ${response.status}`,
  );
}

// The free hosting tier sleeps the API when idle and answers the first request with a bare
// gateway error that carries no CORS headers, which the browser reports as a network failure
// (TypeError "Failed to fetch"). While the browser says it is online, retry such failures once
// for the session calls that are safe to repeat (refresh, login, recovery). Everything else keeps
// the original TypeError so the offline logic (outbox, pull, offline fallbacks) and the
// lost-response handling keep recognising a real network failure.
const WAKE_DELAY_MS = 1500;
const RETRY_SAFE = ["/api/v1/auth/refresh", "/api/v1/auth/password/forgot", "/api/v1/auth/password/reset", "/login"];

export async function fetchWithWakeRetry(input: string, init: RequestInit): Promise<Response> {
  const path = input.startsWith(API_BASE_URL) ? input.slice(API_BASE_URL.length) : input;
  const safe = RETRY_SAFE.includes(path);
  try {
    return await fetch(input, init);
  } catch (error) {
    const online = typeof navigator === "undefined" || navigator.onLine !== false;
    if (!safe || !online || !(error instanceof TypeError)) throw error;
    await new Promise((resolve) => setTimeout(resolve, WAKE_DELAY_MS));
    return fetch(input, init);
  }
}

export async function refreshAccessToken(): Promise<string> {
  if (!refreshPromise) {
    refreshPromise = fetchWithWakeRetry(`${API_BASE_URL}/api/v1/auth/refresh`, {
      method: "POST",
      credentials: "include",
    })
      .then(async (response) => {
        if (!response.ok) throw await parseError(response);
        const payload = (await response.json()) as TokenResponse;
        setAccessToken(payload.access_token);
        return payload.access_token;
      })
      .catch((error: unknown) => {
        setAccessToken(null);
        throw error;
      })
      .finally(() => {
        refreshPromise = null;
      });
  }
  return refreshPromise;
}

interface RequestOptions extends RequestInit {
  authenticated?: boolean;
  retryAuthentication?: boolean;
}

export async function apiRequest<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const {
    authenticated = true,
    retryAuthentication = true,
    headers: suppliedHeaders,
    ...requestInit
  } = options;
  const headers = new Headers(suppliedHeaders);
  if (
    requestInit.body &&
    !(requestInit.body instanceof FormData) &&
    !headers.has("Content-Type")
  ) {
    headers.set("Content-Type", "application/json");
  }
  if (authenticated && accessToken) {
    headers.set("Authorization", `Bearer ${accessToken}`);
  }

  const response = await fetchWithWakeRetry(`${API_BASE_URL}${path}`, {
    ...requestInit,
    headers,
    credentials: "include",
  });
  if (response.status === 401 && authenticated && retryAuthentication) {
    await refreshAccessToken();
    return apiRequest<T>(path, { ...options, retryAuthentication: false });
  }
  if (!response.ok) throw await parseError(response);
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

export async function apiBlobRequest(
  path: string,
  options: RequestOptions = {},
): Promise<Blob> {
  const {
    authenticated = true,
    retryAuthentication = true,
    headers: suppliedHeaders,
    ...requestInit
  } = options;
  const headers = new Headers(suppliedHeaders);
  if (authenticated && accessToken) {
    headers.set("Authorization", `Bearer ${accessToken}`);
  }
  const response = await fetchWithWakeRetry(`${API_BASE_URL}${path}`, {
    ...requestInit,
    headers,
    credentials: "include",
  });
  if (response.status === 401 && authenticated && retryAuthentication) {
    await refreshAccessToken();
    return apiBlobRequest(path, { ...options, retryAuthentication: false });
  }
  if (!response.ok) throw await parseError(response);
  return response.blob();
}

export async function loginRequest(email: string, password: string): Promise<TokenResponse> {
  const tokens = await apiRequest<TokenResponse>("/login", {
    method: "POST",
    authenticated: false,
    body: JSON.stringify({ email, password }),
  });
  setAccessToken(tokens.access_token);
  return tokens;
}

export function clearSession() {
  setAccessToken(null);
}
