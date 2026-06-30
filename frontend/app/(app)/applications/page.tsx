import type { Metadata } from "next";
import { ClipboardList, Plus } from "lucide-react";

import { PageHeader } from "@/components/page-header";
import { EmptyState } from "@/components/empty-state";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";

export const metadata: Metadata = { title: "Applications" };

const stages: { label: string; variant: "info" | "default" | "warning" | "success" | "destructive" }[] =
  [
    { label: "Saved", variant: "info" },
    { label: "Applied", variant: "default" },
    { label: "Interviewing", variant: "warning" },
    { label: "Offer", variant: "success" },
    { label: "Rejected", variant: "destructive" },
  ];

export default function ApplicationsPage() {
  return (
    <div className="space-y-8">
      <PageHeader
        title="Applications"
        description="Track every application from saved to offer. Status changes are logged to your activity timeline."
        actions={
          <Button>
            <Plus className="size-4" />
            New application
          </Button>
        }
      />

      <div className="flex flex-wrap items-center gap-2">
        <span className="text-muted-foreground text-sm">Pipeline stages:</span>
        {stages.map((s) => (
          <Badge key={s.label} variant={s.variant}>
            {s.label}
          </Badge>
        ))}
      </div>

      <EmptyState
        icon={ClipboardList}
        title="No applications tracked"
        description="When you apply to a saved job, track it here. JobGoblin will remind you when a follow-up is due."
        action={
          <Button variant="outline">
            <Plus className="size-4" />
            Track an application
          </Button>
        }
      />
    </div>
  );
}
