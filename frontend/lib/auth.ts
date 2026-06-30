/**
 * Auth helpers — thin wrappers over the `/api/auth/*` contract (design.md §4.1).
 *
 * The session itself lives in an HTTP-only cookie that JS cannot read, so these
 * helpers never touch tokens directly; they just drive the endpoints and return
 * the `User` the server reports.
 */

import { api, ApiError } from "@/lib/api";
import type { LoginPayload, RegisterPayload, User } from "@/lib/types";

// The body may be empty on edge cases (e.g. a 204), so treat `user` as
// possibly-absent and access it defensively rather than destructuring.
interface AuthResponse {
  user?: User;
}

/** POST /api/auth/login — sets the session cookie, returns the user. */
export async function login(payload: LoginPayload): Promise<User> {
  const res = await api.post<AuthResponse>("/auth/login", payload);
  if (!res?.user) throw new Error("Login succeeded but no user was returned.");
  return res.user;
}

/** POST /api/auth/register — invite-only registration. */
export async function register(payload: RegisterPayload): Promise<User> {
  const res = await api.post<AuthResponse>("/auth/register", payload);
  if (!res?.user) {
    throw new Error("Registration succeeded but no user was returned.");
  }
  return res.user;
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
    // A 204/empty response makes api.get return undefined; coalesce to null.
    const res = await api.get<AuthResponse>("/auth/me");
    return res?.user ?? null;
  } catch (err) {
    if (err instanceof ApiError && err.isUnauthorized) {
      return null;
    }
    throw err;
  }
}
