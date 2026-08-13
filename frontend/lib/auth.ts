/**
 * Auth helpers over the `/api/auth/*` contract.
 *
 * The session itself lives in an HTTP-only cookie that JS cannot read. These
 * helpers drive the endpoints and return the user or MFA state the server
 * reports.
 */

import { api, ApiError } from "@/lib/api";
import type {
  LoginPayload,
  PrimaryAuthResponse,
  RegisterPayload,
  User,
} from "@/lib/types";

/** POST /api/auth/login: sets a session cookie or an MFA-pending cookie. */
export async function login(
  payload: LoginPayload
): Promise<PrimaryAuthResponse> {
  return api.post<PrimaryAuthResponse>("/auth/login", payload);
}

/** POST /api/auth/register: invite-only registration, returns a flat user. */
export async function register(payload: RegisterPayload): Promise<User> {
  return api.post<User>("/auth/register", payload);
}

/** POST /api/auth/logout: clears the session cookie. */
export async function logout(): Promise<void> {
  await api.post<void>("/auth/logout");
}

/**
 * GET /api/auth/me: resolve the current user from the session cookie.
 * Returns null when unauthenticated rather than throwing.
 */
export async function getCurrentUser(): Promise<User | null> {
  try {
    return await api.get<User>("/auth/me");
  } catch (err) {
    if (err instanceof ApiError && err.isUnauthorized) {
      return null;
    }
    throw err;
  }
}
