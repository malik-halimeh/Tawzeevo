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

export async function refreshAccessToken(): Promise<string> {
  if (!refreshPromise) {
    refreshPromise = fetch(`${API_BASE_URL}/api/v1/auth/refresh`, {
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
  if (requestInit.body && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }
  if (authenticated && accessToken) {
    headers.set("Authorization", `Bearer ${accessToken}`);
  }

  const response = await fetch(`${API_BASE_URL}${path}`, {
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
