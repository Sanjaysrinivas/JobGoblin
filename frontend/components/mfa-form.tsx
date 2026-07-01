"use client";

import * as React from "react";
import { Loader2, ShieldCheck } from "lucide-react";

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

/**
 * Second-factor UI used on the login page.
 *
 * - `mode="challenge"`: the user has TOTP enabled and just passed primary auth
 *   (an mfa_pending cookie is set). They enter the 6-digit code to obtain a full
 *   session.
 * - `mode="enroll"`: the user signed in without a second factor yet. We fetch a
 *   provisioning QR, they scan it, then verify a code to turn MFA on.
 *
 * On success the parent is notified via `onComplete` so it can route onward.
 */

interface EnrollData {
  secret: string;
  provisioning_uri: string;
  qr_data_uri: string;
}

function CodeInput({
  value,
  onChange,
  disabled,
}: {
  value: string;
  onChange: (v: string) => void;
  disabled?: boolean;
}) {
  return (
    <div className="space-y-1.5">
      <Label htmlFor="mfa-code">Authentication code</Label>
      <Input
        id="mfa-code"
        name="code"
        inputMode="numeric"
        autoComplete="one-time-code"
        pattern="[0-9]*"
        maxLength={6}
        placeholder="123456"
        required
        autoFocus
        value={value}
        // Keep only digits so the 6-char limit is meaningful.
        onChange={(e) => onChange(e.target.value.replace(/\D/g, "").slice(0, 6))}
        disabled={disabled}
        className="text-center text-lg tracking-[0.5em]"
      />
    </div>
  );
}

export function MfaForm({
  mode,
  onComplete,
  onSkip,
}: {
  mode: "challenge" | "enroll";
  onComplete: () => void;
  onSkip?: () => void;
}) {
  const [code, setCode] = React.useState("");
  const [pending, setPending] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);
  const [enroll, setEnroll] = React.useState<EnrollData | null>(null);
  const [loadingEnroll, setLoadingEnroll] = React.useState(mode === "enroll");

  // For enrollment, fetch the provisioning QR once.
  React.useEffect(() => {
    if (mode !== "enroll") return;
    let active = true;
    (async () => {
      try {
        const data = await api.get<EnrollData>("/auth/mfa/enroll");
        if (active) setEnroll(data);
      } catch (err) {
        if (active) {
          setError(
            err instanceof ApiError
              ? err.message
              : "Could not start MFA enrollment."
          );
        }
      } finally {
        if (active) setLoadingEnroll(false);
      }
    })();
    return () => {
      active = false;
    };
  }, [mode]);

  async function onSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setError(null);
    setPending(true);
    try {
      const path = mode === "challenge" ? "/auth/mfa/challenge" : "/auth/mfa/verify";
      await api.post(path, { code });
      onComplete();
    } catch (err) {
      if (err instanceof ApiError) {
        setError(
          err.code === "invalid_code"
            ? "That code is incorrect or expired. Try the current one."
            : err.message || "Verification failed. Please try again."
        );
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
        <CardTitle className="text-xl">
          {mode === "challenge" ? "Two-factor authentication" : "Set up two-factor auth"}
        </CardTitle>
        <CardDescription>
          {mode === "challenge"
            ? "Enter the 6-digit code from your authenticator app."
            : "Scan the QR code with an authenticator app, then enter a code to confirm."}
        </CardDescription>
      </CardHeader>
      <CardContent>
        {mode === "enroll" && (
          <div className="mb-4 flex flex-col items-center gap-3">
            {loadingEnroll ? (
              <Loader2 className="text-muted-foreground size-6 animate-spin" />
            ) : enroll ? (
              <>
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img
                  src={enroll.qr_data_uri}
                  alt="Authenticator setup QR code"
                  width={180}
                  height={180}
                  className="rounded-md border bg-white p-2"
                />
                <p className="text-muted-foreground text-center text-xs leading-relaxed">
                  Can&apos;t scan? Enter this key manually:
                  <br />
                  <code className="text-foreground break-all">{enroll.secret}</code>
                </p>
              </>
            ) : null}
          </div>
        )}

        <form onSubmit={onSubmit} className="space-y-4">
          <CodeInput value={code} onChange={setCode} disabled={pending} />

          {error && (
            <p
              role="alert"
              className="bg-destructive/10 text-destructive rounded-md px-3 py-2 text-sm"
            >
              {error}
            </p>
          )}

          <Button
            type="submit"
            className="w-full"
            disabled={pending || code.length !== 6 || (mode === "enroll" && !enroll)}
          >
            {pending ? (
              <>
                <Loader2 className="size-4 animate-spin" />
                Verifying...
              </>
            ) : (
              <>
                <ShieldCheck className="size-4" />
                {mode === "challenge" ? "Verify" : "Enable two-factor auth"}
              </>
            )}
          </Button>
          {mode === "enroll" && onSkip && (
            <Button
              type="button"
              variant="ghost"
              className="w-full"
              disabled={pending}
              onClick={onSkip}
            >
              Skip for now
            </Button>
          )}
        </form>
      </CardContent>
    </Card>
  );
}
