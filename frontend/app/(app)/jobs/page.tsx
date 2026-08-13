import type { Metadata } from "next";

import { JobListView } from "@/components/jobs/job-list-view";

export const metadata: Metadata = { title: "Jobs" };

export default function JobsPage() {
  return <JobListView />;
}
