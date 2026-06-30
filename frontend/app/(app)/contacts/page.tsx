import type { Metadata } from "next";
import { Users, UserPlus } from "lucide-react";

import { PageHeader } from "@/components/page-header";
import { EmptyState } from "@/components/empty-state";
import { Button } from "@/components/ui/button";

export const metadata: Metadata = { title: "Contacts" };

export default function ContactsPage() {
  return (
    <div className="space-y-8">
      <PageHeader
        title="Contacts"
        description="Recruiters, hiring managers, and referrals — the people behind your outreach."
        actions={
          <Button>
            <UserPlus className="size-4" />
            Add contact
          </Button>
        }
      />
      <EmptyState
        icon={Users}
        title="No contacts yet"
        description="Add recruiters and referrals so you can draft tailored outreach. Every message stays a reviewable draft — never auto-sent."
        action={
          <Button variant="outline">
            <UserPlus className="size-4" />
            Add your first contact
          </Button>
        }
      />
    </div>
  );
}
