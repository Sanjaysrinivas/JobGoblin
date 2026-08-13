import * as React from "react";
import { type LucideIcon } from "lucide-react";

import { cn } from "@/lib/utils";

interface EmptyStateProps {
  icon: LucideIcon;
  title: string;
  description: string;
  action?: React.ReactNode;
  className?: string;
}

/**
 * Centered empty state used across not-yet-wired pages. Matches the design
 * system's EMPTY pattern: icon + message + optional CTA.
 */
export function EmptyState({
  icon: Icon,
  title,
  description,
  action,
  className,
}: EmptyStateProps) {
  return (
    <div
      className={cn(
        "border-border/70 flex flex-col items-center justify-center rounded-xl border border-dashed px-6 py-16 text-center",
        className
      )}
    >
      <span className="bg-primary/10 text-primary ring-primary/15 mb-4 flex size-12 items-center justify-center rounded-xl ring-1 ring-inset">
        <Icon className="size-6" />
      </span>
      <h3 className="font-display text-base font-semibold">{title}</h3>
      <p className="text-muted-foreground mt-1 max-w-sm text-sm">
        {description}
      </p>
      {action && <div className="mt-5">{action}</div>}
    </div>
  );
}
