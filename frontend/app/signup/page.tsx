import type { Metadata } from "next";
import { Suspense } from "react";

import { GoblinMark, GoblinWordmark } from "@/components/goblin-mark";
import { SignupForm } from "@/components/signup-form";

export const metadata: Metadata = {
  title: "Create account",
  description: "Create your invite-only JobGoblin account.",
};

export default function SignupPage() {
  return (
    <main className="relative flex min-h-svh items-center justify-center overflow-hidden px-4 py-12">
      <div
        aria-hidden
        className="pointer-events-none absolute inset-0 -z-10"
        style={{
          background:
            "radial-gradient(60rem 40rem at 50% -10%, color-mix(in oklch, var(--primary) 18%, transparent), transparent 70%)",
        }}
      />

      <div className="animate-rise w-full max-w-sm">
        <div className="mb-8 flex flex-col items-center gap-3 text-center">
          <GoblinMark size="lg" />
          <div className="space-y-1">
            <GoblinWordmark className="text-2xl" />
            <p className="text-muted-foreground text-sm">
              Invite-only access for your job-search workspace.
            </p>
          </div>
        </div>

        <Suspense fallback={null}>
          <SignupForm />
        </Suspense>

        <p className="text-muted-foreground mt-6 text-center text-xs leading-relaxed">
          A private productivity tool, never a spam or auto-apply bot. Every
          external action needs your explicit approval.
        </p>
      </div>
    </main>
  );
}
