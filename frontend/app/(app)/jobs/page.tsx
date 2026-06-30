import type { Metadata } from "next";
import { Briefcase, Plus } from "lucide-react";

import { PageHeader } from "@/components/page-header";
import { EmptyState } from "@/components/empty-state";
import { Button } from "@/components/ui/button";

export const metadata: Metadata = { title: "Jobs" };

export default function JobsPage() {
  return (
    <div className="space-y-8">
      <PageHeader
        title="Jobs"
        description="Save roles you care about, then run a resume-to-job analysis for an ATS-style match score."
        actions={
          <Button>
            <Plus className="size-4" />
            Add a job
          </Button>
        }
      />
      <EmptyState
        icon={Briefcase}
        title="No jobs saved"
        description="Paste a job description to save it. Then pick a resume and run the analysis to see your match score and missing keywords."
        action={
          <Button variant="outline">
            <Plus className="size-4" />
            Add your first job
          </Button>
        }
      />
    </div>
  );
}
