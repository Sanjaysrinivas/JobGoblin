import type { Metadata } from "next";

import { PageHeader } from "@/components/page-header";
import { SettingsView } from "@/components/settings/settings-view";

export const metadata: Metadata = { title: "Settings" };

export default function SettingsPage() {
  return (
    <div className="space-y-8">
      <PageHeader
        title="Settings"
        description="Review your account and configured workspace providers."
      />
      <SettingsView />
    </div>
  );
}
