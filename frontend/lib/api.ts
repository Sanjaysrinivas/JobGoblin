/**
 * Typed fetch wrapper for the JobGoblin backend.
 *
 * In production the frontend and backend sit behind Caddy on a single origin,
 * so the browser only ever needs the relative `/api` prefix and the session
 * cookie rides along automatically. In local dev (running `next dev` outside
 * Docker) we point at the backend directly via NEXT_PUBLIC_API_BASE_URL.
 *
 * Every request uses `credentials: "include"` so the HTTP-only session cookie
 * is sent on same-origin and (in dev) cross-origin calls alike.
 */

import type { ApiErrorBody } from "@/lib/types";

/**
 * Base URL for API calls.
 *
 * - In the **browser** the frontend and backend share an origin (behind Caddy),
 *   so "" is correct: requests go to same-origin `/api/...`. For dev outside
 *   Docker, set NEXT_PUBLIC_API_BASE_URL=http://localhost:8000.
 * - On the **server** (Server Components / Actions / Route Handlers) `fetch`
 *   needs an absolute URL - a bare `/api/...` throws "Failed to parse URL".
 *   There is no Caddy hop server-side, so we talk to the backend container
 *   directly. Configure INTERNAL_API_BASE_URL in the server environment
 *   (docker-compose sets it to http://backend:8000); fall back to that host.
 */
const API_BASE_URL =
  typeof window === "undefined"
    ? process.env.INTERNAL_API_BASE_URL ?? "http://backend:8000"
    : process.env.NEXT_PUBLIC_API_BASE_URL ?? "";

export class ApiError extends Error {
  readonly status: number;
  readonly code?: string;

  constructor(status: number, message: string, code?: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
  }

  /** True when the failure is an unauthenticated/expired-session response. */
  get isUnauthorized(): boolean {
    return this.status === 401;
  }
}

export interface RequestOptions extends Omit<RequestInit, "body"> {
  /** JSON-serializable body. Mutually exclusive with `formData`. */
  json?: unknown;
  /** Multipart body (e.g. resume upload). Mutually exclusive with `json`. */
  formData?: FormData;
}

function buildUrl(path: string): string {
  const normalized = path.startsWith("/") ? path : `/${path}`;
  // Callers pass paths relative to the API root (e.g. "/auth/login"); the
  // shared "/api" prefix is applied here so it lives in exactly one place.
  return `${API_BASE_URL}/api${normalized}`;
}

async function parseError(res: Response): Promise<ApiError> {
  let detail = res.statusText || "Request failed";
  let code: string | undefined;
  try {
    const body = (await res.json()) as ApiErrorBody;
    if (body?.detail) detail = body.detail;
    code = body?.code;
  } catch {
    // Non-JSON error body - fall back to the status text.
  }
  return new ApiError(res.status, detail, code);
}

/**
 * Core request function. Returns parsed JSON typed as `T`, or `undefined` for
 * 204 No Content responses. Throws {@link ApiError} on non-2xx.
 */
export async function apiFetch<T = unknown>(
  path: string,
  options: RequestOptions = {}
): Promise<T> {
  const { json, formData, headers, ...rest } = options;

  const finalHeaders = new Headers(headers);
  let body: BodyInit | undefined;

  if (formData) {
    body = formData; // Browser sets the multipart boundary itself.
  } else if (json !== undefined) {
    finalHeaders.set("Content-Type", "application/json");
    body = JSON.stringify(json);
  }
  finalHeaders.set("Accept", "application/json");

  const res = await fetch(buildUrl(path), {
    ...rest,
    headers: finalHeaders,
    body,
    // Always send/receive the session cookie.
    credentials: "include",
  });

  if (!res.ok) {
    throw await parseError(res);
  }

  if (res.status === 204 || res.headers.get("content-length") === "0") {
    return undefined as T;
  }

  const contentType = res.headers.get("content-type") ?? "";
  if (contentType.includes("application/json")) {
    return (await res.json()) as T;
  }
  return undefined as T;
}

/** Convenience verbs over {@link apiFetch}. */
export const api = {
  get: <T>(path: string, options?: RequestOptions) =>
    apiFetch<T>(path, { ...options, method: "GET" }),
  post: <T>(path: string, json?: unknown, options?: RequestOptions) =>
    apiFetch<T>(path, { ...options, method: "POST", json }),
  put: <T>(path: string, json?: unknown, options?: RequestOptions) =>
    apiFetch<T>(path, { ...options, method: "PUT", json }),
  patch: <T>(path: string, json?: unknown, options?: RequestOptions) =>
    apiFetch<T>(path, { ...options, method: "PATCH", json }),
  delete: <T>(path: string, options?: RequestOptions) =>
    apiFetch<T>(path, { ...options, method: "DELETE" }),
  upload: <T>(path: string, formData: FormData, options?: RequestOptions) =>
    apiFetch<T>(path, { ...options, method: "POST", formData }),
};
