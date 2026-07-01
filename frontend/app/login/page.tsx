import type { Metadata } from "next";
import { Suspense } from "react";

import { GoblinMark, GoblinWordmark } from "@/components/goblin-mark";
import { LoginForm } from "@/components/login-form";

export const metadata: Metadata = {
  title: "Sign in",
  description: "Sign in to your JobGoblin workspace.",
};

export default function LoginPage() {
  return (
    <main className="relative flex min-h-svh items-center justify-center overflow-hidden px-4 py-12">
      {/* Atmospheric goblin-green glow behind the card. */}
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
              Your AI job-search assistant.
            </p>
          </div>
        </div>

        <Suspense fallback={null}>
          <LoginForm />
        </Suspense>

        <p className="text-muted-foreground mt-6 text-center text-xs leading-relaxed">
          A private productivity tool, never a spam or auto-apply bot. Every
          external action needs your explicit approval.
        </p>
      </div>
    </main>
  );
}
