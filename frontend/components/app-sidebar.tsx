"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Sparkles } from "lucide-react";

import { cn } from "@/lib/utils";
import { navItems } from "@/lib/nav";
import { GoblinMark, GoblinWordmark } from "@/components/goblin-mark";

export function AppSidebar() {
  const pathname = usePathname();

  return (
    <aside className="bg-sidebar text-sidebar-foreground hidden w-64 shrink-0 flex-col border-r md:flex">
      <div className="flex h-16 items-center gap-2.5 border-b px-5">
        <GoblinMark size="sm" />
        <GoblinWordmark />
      </div>

      <nav className="flex-1 space-y-1 overflow-y-auto px-3 py-4">
        <p className="text-muted-foreground px-3 pb-2 text-xs font-medium tracking-wide uppercase">
          Workspace
        </p>
        {navItems.map((item) => {
          const active =
            pathname === item.href || pathname.startsWith(`${item.href}/`);
          const Icon = item.icon;
          return (
            <Link
              key={item.href}
              href={item.href}
              aria-current={active ? "page" : undefined}
              className={cn(
                "group relative flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-colors",
                active
                  ? "bg-sidebar-accent text-sidebar-accent-foreground"
                  : "text-sidebar-foreground/70 hover:bg-sidebar-accent/60 hover:text-sidebar-foreground"
              )}
            >
              {active && (
                <span className="bg-primary absolute top-1/2 left-0 h-5 w-1 -translate-y-1/2 rounded-r-full" />
              )}
              <Icon
                className={cn(
                  "size-4 shrink-0 transition-colors",
                  active
                    ? "text-primary"
                    : "text-muted-foreground group-hover:text-sidebar-foreground"
                )}
              />
              {item.title}
            </Link>
          );
        })}
      </nav>

      <div className="border-t p-3">
        <div className="bg-primary/8 ring-primary/15 flex items-start gap-3 rounded-lg p-3 ring-1 ring-inset">
          <Sparkles className="text-primary mt-0.5 size-4 shrink-0" />
          <div className="space-y-0.5">
            <p className="text-sm font-medium">Local AI ready</p>
            <p className="text-muted-foreground text-xs leading-snug">
              Analysis runs on your own Ollama models. Nothing leaves the box.
            </p>
          </div>
        </div>
      </div>
    </aside>
  );
}
