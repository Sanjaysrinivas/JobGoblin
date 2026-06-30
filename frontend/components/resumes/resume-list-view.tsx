"use client";

import * as React from "react";
import Link from "next/link";
import { CheckCircle2, FileText, Loader2 } from "lucide-react";

import { ApiError } from "@/lib/api";
import { listResumes, type ResumeDetail } from "@/lib/resumes";
import { PageHeader } from "@/components/page-header";
import { EmptyState } from "@/components/empty-state";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import { ResumeUpload } from "@/components/resumes/resume-upload";

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function sectionCount(resume: ResumeDetail): number {
  const p = resume.parsed_json;
  if (!p) return 0;
  return [
    p.summary ? 1 : 0,
    p.skills?.length ? 1 : 0,
    p.experience?.length ? 1 : 0,
    p.education?.length ? 1 : 0,
    p.projects?.length ? 1 : 0,
    p.certifications?.length ? 1 : 0,
  ].reduce((a, b) => a + b, 0);
}

export function ResumeListView() {
  const [resumes, setResumes] = React.useState<ResumeDetail[] | null>(null);
  const [error, setError] = React.useState<string | null>(null);

  React.useEffect(() => {
    let active = true;
    (async () => {
      try {
        const data = await listResumes();
        if (!active) return;
        setResumes(data);
      } catch (err) {
        if (!active) return;
        setError(
          err instanceof ApiError && err.isUnauthorized
            ? "Please sign in to view your resumes."
            : "Could not load resumes. Is the backend running?"
        );
        setResumes([]);
      }
    })();
    return () => {
      active = false;
    };
  }, []);

  function onUploaded(resume: ResumeDetail) {
    setResumes((prev) => [resume, ...(prev ?? [])]);
  }

  return (
    <div className="space-y-8">
      <PageHeader
        title="Resumes"
        description="Upload resumes, let AI parse the sections, and pick a default to score against jobs."
        actions={<ResumeUpload onUploaded={onUploaded} />}
      />

      {error && (
        <p
          role="alert"
          className="bg-destructive/10 text-destructive rounded-md px-3 py-2 text-sm"
        >
          {error}
        </p>
      )}

      {resumes === null ? (
        <div className="text-muted-foreground flex items-center gap-2 text-sm">
          <Loader2 className="size-4 animate-spin" />
          Loading resumes…
        </div>
      ) : resumes.length === 0 ? (
        <EmptyState
          icon={FileText}
          title="No resumes yet"
          description="Upload a PDF or DOCX. JobGoblin extracts the text and parses it into summary, skills, experience, education, and more."
          action={<ResumeUpload onUploaded={onUploaded} variant="outline" label="Upload your first resume" />}
        />
      ) : (
        <ul className="grid grid-cols-1 gap-3 sm:grid-cols-2">
          {resumes.map((resume) => (
            <li key={resume.id}>
              <Link href={`/resumes/${resume.id}`} className="block">
                <Card className="hover:border-primary/40 gap-0 py-5 transition-colors">
                  <CardContent className="space-y-3">
                    <div className="flex items-start justify-between gap-2">
                      <span className="flex items-center gap-2 font-medium">
                        <FileText className="text-primary size-4 shrink-0" />
                        <span className="truncate">{resume.title}</span>
                      </span>
                      {resume.is_default && (
                        <Badge variant="success" className="shrink-0">
                          <CheckCircle2 className="size-3" />
                          Default
                        </Badge>
                      )}
                    </div>
                    <div className="text-muted-foreground flex flex-wrap items-center gap-x-2 gap-y-1 text-xs">
                      <span className="truncate">{resume.original_filename}</span>
                      <span aria-hidden>·</span>
                      <span>{formatBytes(resume.file_size)}</span>
                      <span aria-hidden>·</span>
                      <span>{sectionCount(resume)} sections parsed</span>
                    </div>
                  </CardContent>
                </Card>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
