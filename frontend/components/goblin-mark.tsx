import { cn } from "@/lib/utils";

/**
 * The JobGoblin mark — a small goblin-green badge with the mascot emoji.
 * Used in the sidebar header and the login card. Kept as a component so the
 * lockup stays consistent everywhere it appears.
 */
export function GoblinMark({
  className,
  size = "md",
}: {
  className?: string;
  size?: "sm" | "md" | "lg";
}) {
  const dims = {
    sm: "size-7 text-base rounded-md",
    md: "size-9 text-lg rounded-lg",
    lg: "size-12 text-2xl rounded-xl",
  }[size];

  return (
    <span
      aria-hidden
      className={cn(
        "inline-flex items-center justify-center bg-primary/12 text-primary ring-1 ring-inset ring-primary/20 select-none",
        dims,
        className
      )}
    >
      <span className="-mt-px">👺</span>
    </span>
  );
}

export function GoblinWordmark({ className }: { className?: string }) {
  return (
    <span
      className={cn(
        "font-display text-lg font-semibold tracking-tight",
        className
      )}
    >
      Job<span className="text-primary">Goblin</span>
    </span>
  );
}
