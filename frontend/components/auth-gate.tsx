"use client";

import * as React from "react";
import { usePathname, useRouter } from "next/navigation";
import { Loader2 } from "lucide-react";

import { getCurrentUser } from "@/lib/auth";

export function AuthGate({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const [authorized, setAuthorized] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);

  React.useEffect(() => {
    if (authorized) return;
    let active = true;

    (async () => {
      try {
        const user = await getCurrentUser();
        if (!active) return;
        if (!user) {
          const next = encodeURIComponent(pathname || "/dashboard");
          router.replace(`/login?next=${next}`);
          return;
        }
        setAuthorized(true);
      } catch {
        if (!active) return;
        setError("Could not verify your session. Refresh or sign in again.");
      }
    })();

    return () => {
      active = false;
    };
  }, [pathname, router, authorized]);

  if (error) {
    return (
      <main className="mx-auto flex min-h-svh w-full max-w-md items-center px-4">
        <p
          role="alert"
          className="bg-destructive/10 text-destructive rounded-md px-3 py-2 text-sm"
        >
          {error}
        </p>
      </main>
    );
  }

  if (!authorized) {
    return (
      <main className="text-muted-foreground flex min-h-svh items-center justify-center gap-2 text-sm">
        <Loader2 className="size-4 animate-spin" />
        Checking session...
      </main>
    );
  }

  return <>{children}</>;
}
