import type { Metadata } from "next";
import { FileText, Upload } from "lucide-react";

import { PageHeader } from "@/components/page-header";
import { EmptyState } from "@/components/empty-state";
import { Button } from "@/components/ui/button";

export const metadata: Metadata = { title: "Resumes" };

export default function ResumesPage() {
  return (
    <div className="space-y-8">
      <PageHeader
        title="Resumes"
        description="Upload resumes, let AI parse the sections, and pick a default to score against jobs."
        actions={
          <Button>
            <Upload className="size-4" />
            Upload resume
          </Button>
        }
      />
      <EmptyState
        icon={FileText}
        title="No resumes yet"
        description="Upload a PDF or DOCX. JobGoblin extracts the text and parses it into summary, skills, experience, education, and more."
        action={
          <Button variant="outline">
            <Upload className="size-4" />
            Upload your first resume
          </Button>
        }
      />
    </div>
  );
}
