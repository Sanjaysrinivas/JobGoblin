import type { Metadata } from "next";

import { DiscoveryView } from "@/components/discovery/discovery-view";

export const metadata: Metadata = { title: "Discover" };

export default function DiscoverPage() {
  return <DiscoveryView />;
}
