"use client";

import * as React from "react";
import { useRouter } from "next/navigation";
import { Eye, EyeOff, Loader2, LogIn } from "lucide-react";

import { api, ApiError } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { MfaForm } from "@/components/mfa-form";

/**
 * Shape returned by the primary-auth endpoints (password + Google callback).
 * Either a full user (session set) with an enrollment hint, or just the
 * `mfa_required` flag when a second factor is pending.
 */
interface AuthResult {
  email?: string;
  mfa_required?: boolean;
  mfa_enrollment_required?: boolean;
}

type Step = "credentials" | "challenge" | "enroll";

// The backend builds Google's consent URL; we just send the browser there.
// Same-origin in production (Caddy); in dev it's proxied via the API base.
const GOOGLE_LOGIN_URL = `${
  process.env.NEXT_PUBLIC_API_BASE_URL ?? ""
}/api/auth/google/login`;

export function LoginForm() {
  const router = useRouter();
  const [email, setEmail] = React.useState("");
  const [password, setPassword] = React.useState("");
  const [showPassword, setShowPassword] = React.useState(false);
  const [pending, setPending] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);
  const [step, setStep] = React.useState<Step>("credentials");

  function goToWorkspace() {
    router.push("/dashboard");
    router.refresh();
  }

  function routeAfterPrimaryAuth(result: AuthResult) {
    if (result.mfa_required) {
      // TOTP enabled: only an mfa_pending cookie was set — challenge required.
      setStep("challenge");
    } else if (result.mfa_enrollment_required) {
      // Session set, but no second factor yet — guide enrollment.
      setStep("enroll");
    } else {
      goToWorkspace();
    }
  }

  async function onSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setError(null);
    setPending(true);
    try {
      // POSTs to /api/auth/login with credentials: "include", so the session or
      // mfa_pending cookie is set on success. We read the result to branch.
      const result = await api.post<AuthResult>("/auth/login", { email, password });
      routeAfterPrimaryAuth(result ?? {});
    } catch (err) {
      if (err instanceof ApiError) {
        setError(
          err.isUnauthorized
            ? "Invalid email or password."
            : err.message || "Sign in failed. Please try again."
        );
      } else {
        setError("Could not reach the server. Is the backend running?");
      }
    } finally {
      setPending(false);
    }
  }

  if (step === "challenge") {
    return <MfaForm mode="challenge" onComplete={goToWorkspace} />;
  }
  if (step === "enroll") {
    // Session is already set; enrolling enables MFA, then on to the workspace.
    return <MfaForm mode="enroll" onComplete={goToWorkspace} />;
  }

  return (
    <Card className="shadow-sm">
      <CardHeader>
        <CardTitle className="text-xl">Welcome back</CardTitle>
        <CardDescription>
          Sign in to your workspace to keep your search moving.
        </CardDescription>
      </CardHeader>
      <CardContent>
        <form onSubmit={onSubmit} className="space-y-4">
          <div className="space-y-1.5">
            <Label htmlFor="email">Email</Label>
            <Input
              id="email"
              name="email"
              type="email"
              autoComplete="email"
              placeholder="you@example.com"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              disabled={pending}
            />
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="password">Password</Label>
            <div className="relative">
              <Input
                id="password"
                name="password"
                type={showPassword ? "text" : "password"}
                autoComplete="current-password"
                placeholder="••••••••"
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                disabled={pending}
                className="pr-10"
              />
              <button
                type="button"
                onClick={() => setShowPassword((v) => !v)}
                className="text-muted-foreground hover:text-foreground absolute top-1/2 right-2 -translate-y-1/2 rounded-sm p-1 transition-colors"
                aria-label={showPassword ? "Hide password" : "Show password"}
                tabIndex={-1}
              >
                {showPassword ? (
                  <EyeOff className="size-4" />
                ) : (
                  <Eye className="size-4" />
                )}
              </button>
            </div>
          </div>

          {error && (
            <p
              role="alert"
              className="bg-destructive/10 text-destructive rounded-md px-3 py-2 text-sm"
            >
              {error}
            </p>
          )}

          <Button type="submit" className="w-full" disabled={pending}>
            {pending ? (
              <>
                <Loader2 className="size-4 animate-spin" />
                Signing in…
              </>
            ) : (
              <>
                <LogIn className="size-4" />
                Sign in
              </>
            )}
          </Button>
        </form>

        <div className="my-4 flex items-center gap-3" aria-hidden>
          <span className="bg-border h-px flex-1" />
          <span className="text-muted-foreground text-xs">or</span>
          <span className="bg-border h-px flex-1" />
        </div>

        <Button asChild variant="outline" className="w-full" disabled={pending}>
          <a href={GOOGLE_LOGIN_URL}>
            <GoogleIcon className="size-4" />
            Sign in with Google
          </a>
        </Button>
      </CardContent>
    </Card>
  );
}

/** Inline multi-color Google "G" mark (no external asset / network request). */
function GoogleIcon({ className }: { className?: string }) {
  return (
    <svg
      className={className}
      viewBox="0 0 48 48"
      aria-hidden
      focusable="false"
      xmlns="http://www.w3.org/2000/svg"
    >
      <path
        fill="#EA4335"
        d="M24 9.5c3.54 0 6.71 1.22 9.21 3.6l6.85-6.85C35.9 2.38 30.47 0 24 0 14.62 0 6.51 5.38 2.56 13.22l7.98 6.19C12.43 13.72 17.74 9.5 24 9.5z"
      />
      <path
        fill="#4285F4"
        d="M46.98 24.55c0-1.57-.15-3.09-.38-4.55H24v9.02h12.94c-.58 2.96-2.26 5.48-4.78 7.18l7.73 6c4.51-4.18 7.09-10.36 7.09-17.65z"
      />
      <path
        fill="#FBBC05"
        d="M10.53 28.59c-.48-1.45-.76-2.99-.76-4.59s.27-3.14.76-4.59l-7.98-6.19C.92 16.46 0 20.12 0 24c0 3.88.92 7.54 2.56 10.78l7.97-6.19z"
      />
      <path
        fill="#34A853"
        d="M24 48c6.48 0 11.93-2.13 15.89-5.81l-7.73-6c-2.15 1.45-4.92 2.3-8.16 2.3-6.26 0-11.57-4.22-13.47-9.91l-7.98 6.19C6.51 42.62 14.62 48 24 48z"
      />
    </svg>
  );
}
