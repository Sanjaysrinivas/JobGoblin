"use client";

import * as React from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { LogOut, Menu, X } from "lucide-react";

import { getCurrentUser, logout } from "@/lib/auth";
import { navItems } from "@/lib/nav";
import { cn } from "@/lib/utils";
import { GoblinMark, GoblinWordmark } from "@/components/goblin-mark";
import { ThemeToggle } from "@/components/theme-toggle";
import { Button } from "@/components/ui/button";

export function AppTopbar() {
  const pathname = usePathname();
  const router = useRouter();
  const [mobileOpen, setMobileOpen] = React.useState(false);
  const [initials, setInitials] = React.useState("JG");

  React.useEffect(() => {
    let active = true;
    getCurrentUser()
      .then((user) => {
        if (!active || !user) return;
        const value = user.display_name
          .split(/\s+/)
          .map((part) => part[0])
          .join("")
          .slice(0, 2)
          .toUpperCase();
        setInitials(value || user.email.slice(0, 2).toUpperCase());
      })
      .catch(() => undefined);
    return () => {
      active = false;
    };
  }, []);

  async function signOut() {
    try {
      await logout();
    } finally {
      router.push("/login");
      router.refresh();
    }
  }

  return (
    <header className="bg-background/80 sticky top-0 z-30 flex h-16 items-center gap-3 border-b px-4 backdrop-blur-md md:px-6">
      <Button
        variant="ghost"
        size="icon"
        className="md:hidden"
        aria-label="Open navigation"
        aria-expanded={mobileOpen}
        onClick={() => setMobileOpen((value) => !value)}
      >
        {mobileOpen ? <X className="size-5" /> : <Menu className="size-5" />}
      </Button>

      <div className="ml-auto flex items-center gap-1.5">
        <ThemeToggle />
        <Link
          href="/settings"
          className="bg-primary/12 text-primary ring-primary/20 flex size-8 items-center justify-center rounded-full text-sm font-semibold ring-1 ring-inset"
          aria-label="Account settings"
          title="Account settings"
        >
          {initials}
        </Link>
        <Button
          variant="ghost"
          size="icon"
          aria-label="Sign out"
          title="Sign out"
          onClick={() => void signOut()}
        >
          <LogOut className="size-4" />
        </Button>
      </div>

      {mobileOpen && (
        <div className="fixed inset-0 top-16 z-40 md:hidden">
          <button
            type="button"
            aria-label="Close navigation"
            className="bg-foreground/30 absolute inset-0"
            onClick={() => setMobileOpen(false)}
          />
          <nav className="bg-sidebar text-sidebar-foreground animate-rise absolute inset-x-0 top-0 space-y-1 border-b p-3 shadow-lg">
            <div className="flex items-center gap-2 px-2 pb-2">
              <GoblinMark size="sm" />
              <GoblinWordmark />
            </div>
            {navItems.map((item) => {
              const active =
                pathname === item.href || pathname.startsWith(`${item.href}/`);
              const Icon = item.icon;
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  onClick={() => setMobileOpen(false)}
                  className={cn(
                    "flex items-center gap-3 rounded-md px-3 py-2.5 text-sm font-medium",
                    active
                      ? "bg-sidebar-accent text-sidebar-accent-foreground"
                      : "text-sidebar-foreground/75"
                  )}
                >
                  <Icon
                    className={cn(
                      "size-4",
                      active ? "text-primary" : "text-muted-foreground"
                    )}
                  />
                  {item.title}
                </Link>
              );
            })}
          </nav>
        </div>
      )}
    </header>
  );
}
