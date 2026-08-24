"use client";

import * as React from "react";
import Link from "next/link";
import { Briefcase, ExternalLink, Loader2, MapPin, Plus, Wand2 } from "lucide-react";

import { ApiError } from "@/lib/api";
import { createJob, importJob, listJobs } from "@/lib/jobs";
import type { Job, JobCreatePayload, Priority, WorkMode } from "@/lib/types";
import { EmptyState } from "@/components/empty-state";
import { PageHeader } from "@/components/page-header";
import { JobForm } from "@/components/jobs/job-form";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";

function label(value: string): string {
  return value
    .split("_")
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

function priorityVariant(
  priority: Priority
): "outline" | "secondary" | "warning" {
  if (priority === "high") return "warning";
  if (priority === "low") return "outline";
  return "secondary";
}

function workModeVariant(workMode: WorkMode): "outline" | "info" | "default" {
  if (workMode === "remote") return "info";
  if (workMode === "unknown") return "outline";
  return "default";
}

function salary(job: Job): string | null {
  if (job.salary_min == null && job.salary_max == null) return null;
  const currency = job.currency ? `${job.currency} ` : "";
  if (job.salary_min != null && job.salary_max != null) {
    return `${currency}${job.salary_min.toLocaleString()}-${job.salary_max.toLocaleString()}`;
  }
  if (job.salary_min != null) return `${currency}${job.salary_min.toLocaleString()}+`;
  return `${currency}up to ${job.salary_max!.toLocaleString()}`;
}

export function JobListView() {
  const [jobs, setJobs] = React.useState<Job[] | null>(null);
  const [error, setError] = React.useState<string | null>(null);
  const [createError, setCreateError] = React.useState<string | null>(null);
  const [showCreate, setShowCreate] = React.useState(false);
  const [creating, setCreating] = React.useState(false);
  const [importMode, setImportMode] = React.useState<"text" | "url">("text");
  const [importContent, setImportContent] = React.useState("");
  const [importing, setImporting] = React.useState(false);
  const [draftJob, setDraftJob] = React.useState<JobCreatePayload | null>(null);

  React.useEffect(() => {
    let active = true;
    (async () => {
      try {
        const data = await listJobs();
        if (!active) return;
        setJobs(data);
      } catch (err) {
        if (!active) return;
        setError(
          err instanceof ApiError && err.isUnauthorized
            ? "Please sign in to view your jobs."
            : "Could not load jobs. Is the backend running?"
        );
        setJobs([]);
      }
    })();
    return () => {
      active = false;
    };
  }, []);

  async function onCreate(payload: JobCreatePayload) {
    setCreateError(null);
    setCreating(true);
    try {
      const created = await createJob(payload);
      setJobs((prev) => [created, ...(prev ?? [])]);
      setShowCreate(false);
      setDraftJob(null);
      setImportContent("");
    } catch (err) {
      setCreateError(
        err instanceof ApiError
          ? err.message || "Could not save this job."
          : "Could not reach the server. Is the backend running?"
      );
    } finally {
      setCreating(false);
    }
  }

  async function onImport(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const content = importContent.trim();
    if (!content) return;
    setCreateError(null);
    setImporting(true);
    try {
      setDraftJob(await importJob({ mode: importMode, content }));
    } catch (err) {
      setCreateError(
        err instanceof ApiError
          ? err.message || "Could not parse this job."
          : "Could not reach the server. Is the backend running?"
      );
    } finally {
      setImporting(false);
    }
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="Jobs"
        description="Save roles, keep the original description, and prepare them for resume-to-job analysis."
        actions={
          <Button onClick={() => setShowCreate((open) => !open)}>
            <Plus className="size-4" />
            Add a job
          </Button>
        }
      />

      {error && (
        <p
          role="alert"
          className="bg-destructive/10 text-destructive rounded-md px-3 py-2 text-sm"
        >
          {error}
        </p>
      )}

      {showCreate && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Add job</CardTitle>
            <CardDescription>
              Choose whether you want to parse a pasted posting or a source link,
              then review the fields before saving.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            {createError && (
              <p
                role="alert"
                className="bg-destructive/10 text-destructive rounded-md px-3 py-2 text-sm"
              >
                {createError}
              </p>
            )}
            <form onSubmit={onImport} className="space-y-3 rounded-md border p-3">
              <div className="flex flex-wrap gap-2">
                <Button
                  type="button"
                  size="sm"
                  variant={importMode === "text" ? "default" : "outline"}
                  disabled={creating || importing}
                  onClick={() => setImportMode("text")}
                >
                  Paste posting
                </Button>
                <Button
                  type="button"
                  size="sm"
                  variant={importMode === "url" ? "default" : "outline"}
                  disabled={creating || importing}
                  onClick={() => setImportMode("url")}
                >
                  Paste link
                </Button>
              </div>
              {importMode === "url" ? (
                <input
                  type="url"
                  value={importContent}
                  onChange={(e) => setImportContent(e.target.value)}
                  disabled={creating || importing}
                  placeholder="https://company.com/careers/job"
                  className="border-input bg-card focus-visible:border-ring focus-visible:ring-ring/40 h-9 w-full rounded-md border px-3 py-1 text-sm shadow-xs outline-none focus-visible:ring-[3px] disabled:opacity-50"
                />
              ) : (
                <textarea
                  value={importContent}
                  onChange={(e) => setImportContent(e.target.value)}
                  disabled={creating || importing}
                  rows={7}
                  placeholder="Paste the full job posting here."
                  className="border-input bg-card focus-visible:border-ring focus-visible:ring-ring/40 w-full rounded-md border px-3 py-2 text-sm shadow-xs outline-none focus-visible:ring-[3px] disabled:opacity-50"
                />
              )}
              <Button
                type="submit"
                variant="outline"
                disabled={creating || importing || !importContent.trim()}
              >
                {importing ? <Loader2 className="size-4 animate-spin" /> : <Wand2 className="size-4" />}
                {importing ? "Parsing..." : "Parse job"}
              </Button>
            </form>
            <JobForm
              key={draftJob ? JSON.stringify(draftJob) : "blank-job-form"}
              initialPayload={draftJob}
              submitLabel={creating ? "Saving..." : "Save job"}
              disabled={creating || importing}
              onSubmit={onCreate}
              onCancel={() => setShowCreate(false)}
            />
          </CardContent>
        </Card>
      )}

      {jobs === null ? (
        <div className="text-muted-foreground flex items-center gap-2 text-sm">
          <Loader2 className="size-4 animate-spin" />
          Loading jobs...
        </div>
      ) : jobs.length === 0 ? (
        <EmptyState
          icon={Briefcase}
          title="No jobs saved"
          description="Paste a job description to save it. Later, pick a resume and run analysis against this source text."
          action={
            <Button variant="outline" onClick={() => setShowCreate(true)}>
              <Plus className="size-4" />
              Add your first job
            </Button>
          }
        />
      ) : (
        <ul className="grid grid-cols-1 gap-3">
          {jobs.map((job) => {
            const pay = salary(job);
            return (
              <li key={job.id}>
                <Link href={`/jobs/${job.id}`} className="block">
                  <Card className="hover:border-primary/40 gap-0 py-5 transition-colors">
                    <CardContent className="space-y-3">
                      <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
                        <div className="min-w-0 space-y-1">
                          <div className="flex min-w-0 items-center gap-2">
                            <Briefcase className="text-primary size-4 shrink-0" />
                            <span className="truncate font-medium">
                              {job.title}
                            </span>
                            <span className="text-muted-foreground shrink-0 text-sm">
                              at
                            </span>
                            <span className="truncate text-sm font-medium">
                              {job.company_name}
                            </span>
                          </div>
                          <div className="text-muted-foreground flex flex-wrap items-center gap-x-2 gap-y-1 text-xs">
                            {job.location && (
                              <span className="inline-flex items-center gap-1">
                                <MapPin className="size-3" />
                                {job.location}
                              </span>
                            )}
                            {pay && <span>{pay}</span>}
                            {job.source_url && (
                              <span className="inline-flex items-center gap-1">
                                <ExternalLink className="size-3" />
                                Source link
                              </span>
                            )}
                          </div>
                        </div>
                        <div className="flex shrink-0 flex-wrap gap-2">
                          <Badge variant={priorityVariant(job.priority)}>
                            {label(job.priority)}
                          </Badge>
                          <Badge variant={workModeVariant(job.work_mode)}>
                            {label(job.work_mode)}
                          </Badge>
                          <Badge variant="outline">{label(job.source)}</Badge>
                        </div>
                      </div>
                      <p className="text-muted-foreground line-clamp-2 text-sm">
                        {job.description}
                      </p>
                    </CardContent>
                  </Card>
                </Link>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
