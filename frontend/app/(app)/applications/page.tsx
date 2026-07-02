"use client";

import * as React from "react";
import {
  Bell,
  ClipboardList,
  Loader2,
  Plus,
  Save,
  Trash2,
} from "lucide-react";

import { ApiError } from "@/lib/api";
import {
  createApplication,
  deleteApplication,
  listApplications,
  updateApplication,
  type TrackedApplication,
} from "@/lib/applications";
import { listJobs } from "@/lib/jobs";
import type { ApplicationStatus, Job } from "@/lib/types";
import { PageHeader } from "@/components/page-header";
import { EmptyState } from "@/components/empty-state";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

const statuses: ApplicationStatus[] = [
  "saved",
  "interested",
  "resume_tailored",
  "cover_letter_created",
  "applied",
  "contacted_recruiter",
  "referred",
  "phone_screen",
  "technical_interview",
  "final_interview",
  "offer",
  "rejected",
  "withdrawn",
  "archived",
];

const selectClass =
  "border-input bg-card focus-visible:border-ring focus-visible:ring-ring/40 h-9 w-full rounded-md border px-3 text-sm shadow-xs outline-none focus-visible:ring-[3px]";

type Draft = {
  status: ApplicationStatus;
  followUpDate: string;
  notes: string;
};

function label(value: string): string {
  return value
    .split("_")
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

function statusVariant(
  status: ApplicationStatus
): "info" | "default" | "warning" | "success" | "destructive" | "outline" {
  if (status === "offer") return "success";
  if (status === "rejected" || status === "withdrawn") return "destructive";
  if (
    status === "phone_screen" ||
    status === "technical_interview" ||
    status === "final_interview"
  ) {
    return "warning";
  }
  if (status === "archived") return "outline";
  if (status === "saved" || status === "interested") return "info";
  return "default";
}

function dateInputValue(value: string | null): string {
  return value ? value.slice(0, 10) : "";
}

function dateToIso(value: string): string | null {
  return value ? new Date(`${value}T00:00:00Z`).toISOString() : null;
}

function formatDate(value: string | null): string {
  if (!value) return "No reminder";
  return new Intl.DateTimeFormat(undefined, {
    month: "short",
    day: "numeric",
    year: "numeric",
    timeZone: "UTC",
  }).format(new Date(value));
}

function isFollowUpDue(app: TrackedApplication): boolean {
  if (!app.follow_up_at) return false;
  if (["offer", "rejected", "withdrawn", "archived"].includes(app.status)) {
    return false;
  }
  const today = new Date();
  const todayStr = `${today.getFullYear()}-${String(
    today.getMonth() + 1
  ).padStart(2, "0")}-${String(today.getDate()).padStart(2, "0")}`;
  const followUpStr = app.follow_up_at.slice(0, 10);
  return followUpStr <= todayStr;
}

function draftFromApplication(app: TrackedApplication): Draft {
  return {
    status: app.status,
    followUpDate: dateInputValue(app.follow_up_at),
    notes: app.notes ?? "",
  };
}

export default function ApplicationsPage() {
  const [applications, setApplications] = React.useState<
    TrackedApplication[] | null
  >(null);
  const [jobs, setJobs] = React.useState<Job[]>([]);
  const [drafts, setDrafts] = React.useState<Record<string, Draft>>({});
  const [showCreate, setShowCreate] = React.useState(false);
  const [newJobId, setNewJobId] = React.useState("");
  const [newStatus, setNewStatus] =
    React.useState<ApplicationStatus>("saved");
  const [newFollowUpDate, setNewFollowUpDate] = React.useState("");
  const [newNotes, setNewNotes] = React.useState("");
  const [savingId, setSavingId] = React.useState<string | null>(null);
  const [loading, setLoading] = React.useState(true);
  const [error, setError] = React.useState<string | null>(null);
  const [formError, setFormError] = React.useState<string | null>(null);

  React.useEffect(() => {
    let active = true;
    (async () => {
      try {
        const [applicationData, jobData] = await Promise.all([
          listApplications(),
          listJobs(),
        ]);
        if (!active) return;
        setApplications(applicationData);
        setJobs(jobData);
        setDrafts(
          Object.fromEntries(
            applicationData.map((app) => [app.id, draftFromApplication(app)])
          )
        );
      } catch (err) {
        if (!active) return;
        setError(
          err instanceof ApiError && err.isUnauthorized
            ? "Please sign in to view applications."
            : "Could not load applications. Is the backend running?"
        );
        setApplications([]);
      } finally {
        if (active) setLoading(false);
      }
    })();
    return () => {
      active = false;
    };
  }, []);

  const trackedJobIds = new Set(applications?.map((app) => app.job_id) ?? []);
  const availableJobs = jobs.filter((job) => !trackedJobIds.has(job.id));
  const dueCount = applications?.filter(isFollowUpDue).length ?? 0;
  const selectedNewJobId = availableJobs.some((job) => job.id === newJobId)
    ? newJobId
    : availableJobs[0]?.id ?? "";


  function updateDraft(id: string, changes: Partial<Draft>) {
    setDrafts((current) => ({
      ...current,
      [id]: { ...current[id], ...changes },
    }));
  }

  async function onCreate(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selectedNewJobId) return;
    setFormError(null);
    setSavingId("new");
    try {
      const created = await createApplication({
        job_id: selectedNewJobId,
        status: newStatus,
        follow_up_at: dateToIso(newFollowUpDate),
        notes: newNotes,
      });
      setApplications((current) => [created, ...(current ?? [])]);
      setDrafts((current) => ({
        ...current,
        [created.id]: draftFromApplication(created),
      }));
      setShowCreate(false);
      setNewStatus("saved");
      setNewFollowUpDate("");
      setNewNotes("");
    } catch (err) {
      setFormError(
        err instanceof ApiError
          ? err.message || "Could not track this application."
          : "Could not reach the server. Is the backend running?"
      );
    } finally {
      setSavingId(null);
    }
  }

  async function onSave(app: TrackedApplication) {
    const draft = drafts[app.id] ?? draftFromApplication(app);
    setFormError(null);
    setSavingId(app.id);
    try {
      const updated = await updateApplication(app.id, {
        status: draft.status,
        follow_up_at: dateToIso(draft.followUpDate),
        notes: draft.notes,
      });
      setApplications((current) =>
        (current ?? []).map((item) => (item.id === updated.id ? updated : item))
      );
      setDrafts((current) => ({
        ...current,
        [updated.id]: draftFromApplication(updated),
      }));
    } catch (err) {
      setFormError(
        err instanceof ApiError
          ? err.message || "Could not update this application."
          : "Could not reach the server. Is the backend running?"
      );
    } finally {
      setSavingId(null);
    }
  }

  async function onDelete(app: TrackedApplication) {
    setFormError(null);
    setSavingId(app.id);
    try {
      await deleteApplication(app.id);
      setApplications((current) =>
        (current ?? []).filter((item) => item.id !== app.id)
      );
      setDrafts((current) => {
        const next = { ...current };
        delete next[app.id];
        return next;
      });
    } catch (err) {
      setFormError(
        err instanceof ApiError
          ? err.message || "Could not delete this application."
          : "Could not reach the server. Is the backend running?"
      );
    } finally {
      setSavingId(null);
    }
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="Applications"
        description="Track manual application status, notes, and follow-up reminders."
        actions={
          <Button
            onClick={() => setShowCreate((open) => !open)}
            disabled={availableJobs.length === 0}
          >
            <Plus className="size-4" />
            Track application
          </Button>
        }
      />

      <div className="flex flex-wrap items-center gap-2">
        <Badge variant={dueCount > 0 ? "warning" : "outline"}>
          <Bell className="size-3" />
          {dueCount} follow-up{dueCount === 1 ? "" : "s"} due
        </Badge>
        {statuses.slice(0, 5).map((status) => (
          <Badge key={status} variant={statusVariant(status)}>
            {label(status)}
          </Badge>
        ))}
      </div>

      {error && (
        <p
          role="alert"
          className="bg-destructive/10 text-destructive rounded-md px-3 py-2 text-sm"
        >
          {error}
        </p>
      )}
      {formError && (
        <p
          role="alert"
          className="bg-destructive/10 text-destructive rounded-md px-3 py-2 text-sm"
        >
          {formError}
        </p>
      )}

      {showCreate && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Track a saved job</CardTitle>
            <CardDescription>
              This only creates a local tracker and reminder. Nothing is sent or
              submitted.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <form className="grid gap-4 md:grid-cols-4" onSubmit={onCreate}>
              <div className="space-y-1.5 md:col-span-2">
                <Label htmlFor="application-job">Saved job</Label>
                <select
                  id="application-job"
                  className={selectClass}
                  value={selectedNewJobId}
                  onChange={(event) => setNewJobId(event.target.value)}
                  disabled={savingId === "new"}
                >
                  {availableJobs.map((job) => (
                    <option key={job.id} value={job.id}>
                      {job.title} at {job.company_name}
                    </option>
                  ))}
                </select>
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="application-status">Status</Label>
                <select
                  id="application-status"
                  className={selectClass}
                  value={newStatus}
                  onChange={(event) =>
                    setNewStatus(event.target.value as ApplicationStatus)
                  }
                  disabled={savingId === "new"}
                >
                  {statuses.map((status) => (
                    <option key={status} value={status}>
                      {label(status)}
                    </option>
                  ))}
                </select>
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="application-follow-up">Follow-up</Label>
                <Input
                  id="application-follow-up"
                  type="date"
                  value={newFollowUpDate}
                  onChange={(event) => setNewFollowUpDate(event.target.value)}
                  disabled={savingId === "new"}
                />
              </div>
              <div className="space-y-1.5 md:col-span-4">
                <Label htmlFor="application-notes">Notes</Label>
                <Input
                  id="application-notes"
                  value={newNotes}
                  onChange={(event) => setNewNotes(event.target.value)}
                  placeholder="Next step, recruiter name, or portal notes"
                  disabled={savingId === "new"}
                />
              </div>
              <div className="flex justify-end gap-2 md:col-span-4">
                <Button
                  type="button"
                  variant="outline"
                  onClick={() => setShowCreate(false)}
                >
                  Cancel
                </Button>
                <Button type="submit" disabled={!selectedNewJobId || savingId === "new"}>
                  {savingId === "new" && (
                    <Loader2 className="size-4 animate-spin" />
                  )}
                  Save tracker
                </Button>
              </div>
            </form>
          </CardContent>
        </Card>
      )}

      {loading || applications === null ? (
        <div className="text-muted-foreground flex items-center gap-2 text-sm">
          <Loader2 className="size-4 animate-spin" />
          Loading applications...
        </div>
      ) : applications.length === 0 ? (
        <EmptyState
          icon={ClipboardList}
          title="No applications tracked"
          description="Start from a saved job and add the status, notes, and follow-up date you want to remember."
          action={
            <Button
              variant="outline"
              onClick={() => setShowCreate(true)}
              disabled={availableJobs.length === 0}
            >
              <Plus className="size-4" />
              Track an application
            </Button>
          }
        />
      ) : (
        <ul className="grid grid-cols-1 gap-4">
          {applications.map((app) => {
            const draft = drafts[app.id] ?? draftFromApplication(app);
            const saving = savingId === app.id;
            return (
              <li key={app.id}>
                <Card className="gap-0 py-5">
                  <CardContent className="space-y-4">
                    <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
                      <div className="min-w-0 space-y-1">
                        <div className="flex flex-wrap items-center gap-2">
                          <span className="font-medium">{app.job.title}</span>
                          <span className="text-muted-foreground text-sm">
                            at {app.job.company_name}
                          </span>
                          <Badge variant={statusVariant(app.status)}>
                            {label(app.status)}
                          </Badge>
                          {isFollowUpDue(app) && (
                            <Badge variant="warning">
                              <Bell className="size-3" />
                              Follow up
                            </Badge>
                          )}
                        </div>
                        <p className="text-muted-foreground text-sm">
                          Reminder: {formatDate(app.follow_up_at)}
                        </p>
                      </div>
                      <Button
                        type="button"
                        variant="ghost"
                        size="icon"
                        aria-label="Stop tracking application"
                        onClick={() => void onDelete(app)}
                        disabled={saving}
                      >
                        {saving ? (
                          <Loader2 className="size-4 animate-spin" />
                        ) : (
                          <Trash2 className="size-4" />
                        )}
                      </Button>
                    </div>

                    <div className="grid gap-3 md:grid-cols-[minmax(0,1fr)_12rem_minmax(0,2fr)_auto] md:items-end">
                      <div className="space-y-1.5">
                        <Label htmlFor={`status-${app.id}`}>Status</Label>
                        <select
                          id={`status-${app.id}`}
                          className={selectClass}
                          value={draft.status}
                          onChange={(event) =>
                            updateDraft(app.id, {
                              status: event.target.value as ApplicationStatus,
                            })
                          }
                          disabled={saving}
                        >
                          {statuses.map((status) => (
                            <option key={status} value={status}>
                              {label(status)}
                            </option>
                          ))}
                        </select>
                      </div>
                      <div className="space-y-1.5">
                        <Label htmlFor={`follow-up-${app.id}`}>Follow-up</Label>
                        <Input
                          id={`follow-up-${app.id}`}
                          type="date"
                          value={draft.followUpDate}
                          onChange={(event) =>
                            updateDraft(app.id, {
                              followUpDate: event.target.value,
                            })
                          }
                          disabled={saving}
                        />
                      </div>
                      <div className="space-y-1.5">
                        <Label htmlFor={`notes-${app.id}`}>Notes</Label>
                        <Input
                          id={`notes-${app.id}`}
                          value={draft.notes}
                          onChange={(event) =>
                            updateDraft(app.id, { notes: event.target.value })
                          }
                          placeholder="Next step or context"
                          disabled={saving}
                        />
                      </div>
                      <Button
                        type="button"
                        onClick={() => void onSave(app)}
                        disabled={saving}
                      >
                        {saving ? (
                          <Loader2 className="size-4 animate-spin" />
                        ) : (
                          <Save className="size-4" />
                        )}
                        Save
                      </Button>
                    </div>
                  </CardContent>
                </Card>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
