/**
 * Auth helpers — thin wrappers over the `/api/auth/*` contract (design.md §4.1).
 *
 * The session itself lives in an HTTP-only cookie that JS cannot read, so these
 * helpers never touch tokens directly; they just drive the endpoints and return
 * the `User` the server reports.
 */

import { api, ApiError } from "@/lib/api";
import type { LoginPayload, RegisterPayload, User } from "@/lib/types";

interface AuthResponse {
  user: User;
}

/** POST /api/auth/login — sets the session cookie, returns the user. */
export async function login(payload: LoginPayload): Promise<User> {
  const { user } = await api.post<AuthResponse>("/auth/login", payload);
  return user;
}

/** POST /api/auth/register — invite-only registration. */
export async function register(payload: RegisterPayload): Promise<User> {
  const { user } = await api.post<AuthResponse>("/auth/register", payload);
  return user;
}

/** POST /api/auth/logout — clears the session cookie. */
export async function logout(): Promise<void> {
  await api.post<void>("/auth/logout");
}

/**
 * GET /api/auth/me — resolve the current user from the session cookie.
 * Returns `null` when unauthenticated rather than throwing, so callers can
 * branch on "logged out" without a try/catch.
 */
export async function getCurrentUser(): Promise<User | null> {
  try {
    const { user } = await api.get<AuthResponse>("/auth/me");
    return user;
  } catch (err) {
    if (err instanceof ApiError && err.isUnauthorized) {
      return null;
    }
    throw err;
  }
}
