"use client";

import * as React from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Eye, EyeOff, Loader2, UserPlus } from "lucide-react";

import { ApiError } from "@/lib/api";
import { register } from "@/lib/auth";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

type SignupFormProps = {
  publicSignupEnabled?: boolean;
};

export function SignupForm({ publicSignupEnabled = false }: SignupFormProps) {
  const router = useRouter();
  const searchParams = useSearchParams();
  const initialInviteToken =
    searchParams.get("invite_token") ?? searchParams.get("invite") ?? "";

  const [email, setEmail] = React.useState("");
  const [password, setPassword] = React.useState("");
  const [inviteToken, setInviteToken] = React.useState(initialInviteToken);
  const [showPassword, setShowPassword] = React.useState(false);
  const [pending, setPending] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);

  async function onSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setError(null);
    setPending(true);
    try {
      await register({
        email: email.trim(),
        password,
        ...(publicSignupEnabled ? {} : { invite_token: inviteToken.trim() }),
      });
      router.push("/dashboard");
      router.refresh();
    } catch (err) {
      if (err instanceof ApiError) {
        if (err.code === "invalid_invite") {
          setError("That invite token is invalid or expired.");
        } else if (err.code === "email_taken") {
          setError("That email is already registered. Sign in instead.");
        } else {
          setError(err.message || "Could not create the account.");
        }
      } else {
        setError("Could not reach the server. Is the backend running?");
      }
    } finally {
      setPending(false);
    }
  }

  return (
    <Card className="shadow-sm">
      <CardHeader>
        <CardTitle className="text-xl">Create account</CardTitle>
        <CardDescription>
          {publicSignupEnabled
            ? "Create your account to join this JobGoblin workspace."
            : "JobGoblin is invite-only. Use the token from your admin to join this private workspace."}
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
                autoComplete="new-password"
                placeholder="********"
                required
                minLength={8}
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

          {!publicSignupEnabled && (
            <div className="space-y-1.5">
              <Label htmlFor="invite-token">Invite token</Label>
              <Input
                id="invite-token"
                name="invite_token"
                autoComplete="one-time-code"
                placeholder="Paste invite token"
                required
                value={inviteToken}
                onChange={(e) => setInviteToken(e.target.value)}
                disabled={pending}
              />
            </div>
          )}

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
                Creating account...
              </>
            ) : (
              <>
                <UserPlus className="size-4" />
                Create account
              </>
            )}
          </Button>
        </form>

        <p className="text-muted-foreground mt-4 text-center text-sm">
          Already have an account?{" "}
          <Link className="text-primary underline-offset-4 hover:underline" href="/login">
            Sign in
          </Link>
        </p>
      </CardContent>
    </Card>
  );
}
