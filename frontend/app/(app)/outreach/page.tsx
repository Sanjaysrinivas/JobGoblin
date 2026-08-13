import type { Metadata } from "next";

import { OutreachListView } from "@/components/outreach/outreach-list-view";

export const metadata: Metadata = { title: "Outreach" };

export default function OutreachPage() {
  return <OutreachListView />;
}