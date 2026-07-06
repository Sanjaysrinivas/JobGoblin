"use client";

import * as React from "react";
import { useRouter } from "next/navigation";
import {
  ArrowLeft,
  ExternalLink,
  Loader2,
  Pencil,
  Save,
  Trash2,
} from "lucide-react";

import { ApiError } from "@/lib/api";
import { deleteJob, getJob, updateJob } from "@/lib/jobs";
import type { Job, JobCreatePayload, Priority, WorkMode } from "@/lib/types";
import { JobForm } from "@/components/jobs/job-form";
import { JobAnalysisPanel } from "@/components/jobs/job-analysis-panel";
import { CoverLetterPanel } from "@/components/jobs/cover-letter-panel";
import { TailoredResumePanel } from "@/components/jobs/tailored-resume-panel";
import { InterviewPrepPanel } from "@/components/jobs/interview-prep-panel";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";

type Busy = "save" | "delete" | null;

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

function salary(job: Job): string {
  if (job.salary_min == null && job.salary_max == null) return "Not provided";
  const currency = job.currency ? `${job.currency} ` : "";
  if (job.salary_min != null && job.salary_max != null) {
    return `${currency}${job.salary_min.toLocaleString()}-${job.salary_max.toLocaleString()}`;
  }
  if (job.salary_min != null) return `${currency}${job.salary_min.toLocaleString()}+`;
  return `${currency}up to ${job.salary_max!.toLocaleString()}`;
}

function formatDate(value: string): string {
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value));
}

export function JobDetailView({ jobId }: { jobId: string }) {
  const router = useRouter();
  const [job, setJob] = React.useState<Job | null>(null);
  const [loadError, setLoadError] = React.useState<string | null>(null);
  const [actionError, setActionError] = React.useState<string | null>(null);
  const [busy, setBusy] = React.useState<Busy>(null);
  const [editing, setEditing] = React.useState(false);
  const [confirmingDelete, setConfirmingDelete] = React.useState(false);

  React.useEffect(() => {
    let active = true;
    (async () => {
      try {
        const data = await getJob(jobId);
        if (!active) return;
        setJob(data);
      } catch (err) {
        if (!active) return;
        setLoadError(
          err instanceof ApiError && err.status === 404
            ? "Job not found."
            : "Could not load this job."
        );
      }
    })();
    return () => {
      active = false;
    };
  }, [jobId]);

  async function run(kind: Exclude<Busy, null>, fn: () => Promise<void>) {
    setActionError(null);
    setBusy(kind);
    try {
      await fn();
    } catch (err) {
      setActionError(
        err instanceof ApiError ? err.message || "Action failed." : "Action failed."
      );
    } finally {
      setBusy(null);
    }
  }

  function onSave(payload: JobCreatePayload) {
    return run("save", async () => {
      const updated = await updateJob(jobId, payload);
      setJob(updated);
      setEditing(false);
    });
  }

  function onDelete() {
    return run("delete", async () => {
      await deleteJob(jobId);
      router.push("/jobs");
      router.refresh();
    });
  }

  if (loadError) {
    return (
      <div className="space-y-4">
        <Button variant="ghost" size="sm" onClick={() => router.push("/jobs")}>
          <ArrowLeft className="size-4" />
          Back to jobs
        </Button>
        <p
          role="alert"
          className="bg-destructive/10 text-destructive rounded-md px-3 py-2 text-sm"
        >
          {loadError}
        </p>
      </div>
    );
  }

  if (!job) {
    return (
      <div className="text-muted-foreground flex items-center gap-2 text-sm">
        <Loader2 className="size-4 animate-spin" />
        Loading job...
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="space-y-4">
        <Button
          variant="ghost"
          size="sm"
          className="-ml-2"
          onClick={() => router.push("/jobs")}
        >
          <ArrowLeft className="size-4" />
          Jobs
        </Button>

        <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
          <div className="min-w-0 space-y-3">
            <div className="flex flex-wrap gap-2">
              <Badge variant={priorityVariant(job.priority)}>
                {label(job.priority)} priority
              </Badge>
              <Badge variant={workModeVariant(job.work_mode)}>
                {label(job.work_mode)}
              </Badge>
              <Badge variant="outline">{label(job.source)}</Badge>
            </div>
            <h1 className="font-display max-w-5xl break-words text-2xl leading-tight font-semibold tracking-tight sm:text-3xl">
              {job.title}
            </h1>
            <p className="text-muted-foreground flex flex-wrap gap-x-2 gap-y-1 text-sm">
              <span>{job.company_name}</span>
              {job.location && <span>- {job.location}</span>}
            </p>
          </div>

          <div className="flex shrink-0 flex-wrap items-center gap-2">
            <Button
              variant={editing ? "secondary" : "outline"}
              size="sm"
              onClick={() => setEditing((value) => !value)}
              disabled={busy !== null}
            >
              {editing ? <Save className="size-4" /> : <Pencil className="size-4" />}
              {editing ? "Editing" : "Edit"}
            </Button>
            {job.source_url && (
              <Button variant="outline" size="sm" asChild>
                <a href={job.source_url} target="_blank" rel="noreferrer">
                  <ExternalLink className="size-4" />
                  Open source
                </a>
              </Button>
            )}
            {confirmingDelete ? (
              <div className="flex items-center gap-2">
                <span className="text-muted-foreground text-xs">Delete this job?</span>
                <Button
                  variant="destructive"
                  size="sm"
                  onClick={onDelete}
                  disabled={busy !== null}
                >
                  {busy === "delete" ? (
                    <Loader2 className="size-4 animate-spin" />
                  ) : (
                    <Trash2 className="size-4" />
                  )}
                  Confirm
                </Button>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => setConfirmingDelete(false)}
                  disabled={busy !== null}
                >
                  Cancel
                </Button>
              </div>
            ) : (
              <Button
                variant="outline"
                size="sm"
                onClick={() => setConfirmingDelete(true)}
                disabled={busy !== null}
              >
                <Trash2 className="size-4" />
                Delete
              </Button>
            )}
          </div>
        </div>
      </div>

      {actionError && (
        <p
          role="alert"
          className="bg-destructive/10 text-destructive rounded-md px-3 py-2 text-sm"
        >
          {actionError}
        </p>
      )}

      <div className="grid grid-cols-1 gap-6 xl:grid-cols-[minmax(0,1fr)_20rem]">
        <Card className="xl:order-1">
          <CardHeader>
            <CardTitle className="text-base">
              {editing ? "Edit posting" : "Posting"}
            </CardTitle>
            <CardDescription>
              Full role description used for resume matching and application prep.
            </CardDescription>
          </CardHeader>
          <CardContent>
            {editing ? (
              <JobForm
                job={job}
                submitLabel={busy === "save" ? "Saving..." : "Save changes"}
                disabled={busy !== null}
                onSubmit={onSave}
                onCancel={() => setEditing(false)}
              />
            ) : (
              <article className="text-foreground whitespace-pre-wrap break-words text-sm leading-7 md:text-[0.95rem]">
                {job.description || "No description saved."}
              </article>
            )}
          </CardContent>
        </Card>

        <aside className="space-y-4 xl:order-2">
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Quick facts</CardTitle>
              <CardDescription>Tracking metadata for this role.</CardDescription>
            </CardHeader>
            <CardContent>
              <dl className="grid grid-cols-2 gap-x-4 gap-y-4 text-sm xl:grid-cols-1">
                <div>
                  <dt className="text-muted-foreground">Company</dt>
                  <dd className="break-words font-medium">{job.company_name}</dd>
                </div>
                <div>
                  <dt className="text-muted-foreground">Location</dt>
                  <dd className="font-medium">{job.location || "Not provided"}</dd>
                </div>
                <div>
                  <dt className="text-muted-foreground">Salary</dt>
                  <dd className="font-medium">{salary(job)}</dd>
                </div>
                <div>
                  <dt className="text-muted-foreground">Created</dt>
                  <dd className="font-medium">{formatDate(job.created_at)}</dd>
                </div>
                <div>
                  <dt className="text-muted-foreground">Updated</dt>
                  <dd className="font-medium">{formatDate(job.updated_at)}</dd>
                </div>
              </dl>
            </CardContent>
          </Card>
        </aside>
      </div>

      <JobAnalysisPanel jobId={job.id} />
      <TailoredResumePanel jobId={job.id} />
      <CoverLetterPanel jobId={job.id} />
      <InterviewPrepPanel jobId={job.id} />
    </div>
  );
}
