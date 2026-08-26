"use client";

import * as React from "react";
import {
  Activity,
  Bell,
  CalendarClock,
  ChevronDown,
  ClipboardList,
  FileText,
  Filter,
  Mail,
  Users,
  Loader2,
  Plus,
  Save,
  Trash2,
} from "lucide-react";

import { ApiError } from "@/lib/api";
import {
  createApplication,
  getApplicationWorkflow,
  deleteApplication,
  listApplicationFollowUps,
  listApplications,
  updateApplication,
  type ApplicationFollowUp,
  type TrackedApplication,
} from "@/lib/applications";
import { listJobs } from "@/lib/jobs";
import { listCoverLetters } from "@/lib/cover-letters";
import { listResumes, type ResumeDetail } from "@/lib/resumes";
import type {
  ApplicationStatus,
  ApplicationWorkflow,
  CoverLetter,
  Job,
} from "@/lib/types";
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
  resumeId: string;
  coverLetterId: string;
};

type StatusFilter = "all" | "active" | "interviewing" | "outcome" | "archived";
type FollowUpFilter = "all" | "due" | "scheduled";

const interviewingStatuses = new Set<ApplicationStatus>([
  "phone_screen",
  "technical_interview",
  "final_interview",
]);
const outcomeStatuses = new Set<ApplicationStatus>(["offer", "rejected", "withdrawn"]);

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

function parseApiInstant(value: string): Date {
  const hasTimezone = /(?:[zZ]|[+-]\d{2}:?\d{2})$/.test(value);
  return new Date(hasTimezone ? value : `${value}Z`);
}

function formatDate(value: string | null): string {
  if (!value) return "No reminder";
  const date = parseApiInstant(value);
  if (!Number.isFinite(date.getTime())) return "No reminder";
  return new Intl.DateTimeFormat(undefined, {
    month: "short",
    day: "numeric",
    year: "numeric",
    timeZone: "UTC",
  }).format(date);
}

function isInstantDue(value: string | null): boolean {
  if (!value) return false;
  const followUpTime = parseApiInstant(value).getTime();
  return Number.isFinite(followUpTime) && followUpTime <= Date.now();
}

function isFollowUpDue(app: TrackedApplication): boolean {
  if (["offer", "rejected", "withdrawn", "archived"].includes(app.status)) {
    return false;
  }
  return isInstantDue(app.follow_up_at);
}

async function loadFollowUps(): Promise<ApplicationFollowUp[] | null> {
  try {
    return await listApplicationFollowUps(14);
  } catch {
    return null;
  }
}

function draftFromApplication(app: TrackedApplication): Draft {
  return {
    status: app.status,
    followUpDate: dateInputValue(app.follow_up_at),
    notes: app.notes ?? "",
    resumeId: app.resume_id ?? "",
    coverLetterId: app.cover_letter_id ?? "",
  };
}

export default function ApplicationsPage() {
  const [applications, setApplications] = React.useState<
    TrackedApplication[] | null
  >(null);
  const [followUps, setFollowUps] = React.useState<ApplicationFollowUp[] | null>(
    null
  );
  const [jobs, setJobs] = React.useState<Job[]>([]);
  const [resumes, setResumes] = React.useState<ResumeDetail[]>([]);
  const [coverLetters, setCoverLetters] = React.useState<CoverLetter[]>([]);
  const [drafts, setDrafts] = React.useState<Record<string, Draft>>({});
  const [showCreate, setShowCreate] = React.useState(false);
  const [statusFilter, setStatusFilter] = React.useState<StatusFilter>("all");
  const [followUpFilter, setFollowUpFilter] = React.useState<FollowUpFilter>("all");
  const [newJobId, setNewJobId] = React.useState("");
  const [newStatus, setNewStatus] =
    React.useState<ApplicationStatus>("saved");
  const [newFollowUpDate, setNewFollowUpDate] = React.useState("");
  const [newNotes, setNewNotes] = React.useState("");
  const [newResumeId, setNewResumeId] = React.useState("");
  const [newCoverLetterId, setNewCoverLetterId] = React.useState("");
  const [savingId, setSavingId] = React.useState<string | null>(null);
  const [expandedId, setExpandedId] = React.useState<string | null>(null);
  const [workflowLoadingId, setWorkflowLoadingId] = React.useState<string | null>(null);
  const [workflows, setWorkflows] = React.useState<Record<string, ApplicationWorkflow>>({});
  const [workflowErrors, setWorkflowErrors] = React.useState<Record<string, string>>({});
  const [loading, setLoading] = React.useState(true);
  const [error, setError] = React.useState<string | null>(null);
  const [formError, setFormError] = React.useState<string | null>(null);

  async function refreshFollowUps() {
    setFollowUps(await loadFollowUps());
  }

  React.useEffect(() => {
    let active = true;
    (async () => {
      try {
        const [applicationData, jobData, followUpData, resumeData, letterData] = await Promise.all([
          listApplications(),
          listJobs(),
          loadFollowUps(),
          listResumes(),
          listCoverLetters(),
        ]);
        if (!active) return;
        setApplications(applicationData);
        setFollowUps(followUpData);
        setJobs(jobData);
        setResumes(resumeData);
        setCoverLetters(letterData);
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
        setFollowUps(null);
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
  const dueCount =
    followUps === null
      ? applications?.filter(isFollowUpDue).length ?? 0
      : followUps.filter((app) => app.due).length;
  const selectedNewJobId = availableJobs.some((job) => job.id === newJobId)
    ? newJobId
    : availableJobs[0]?.id ?? "";
  const availableNewLetters = coverLetters.filter(
    (letter) => letter.job_id === selectedNewJobId
  );
  const selectedNewLetterId = availableNewLetters.some(
    (letter) => letter.id === newCoverLetterId
  )
    ? newCoverLetterId
    : "";
  const filteredApplications = (applications ?? []).filter((app) => {
    const statusMatch =
      statusFilter === "all" ||
      (statusFilter === "active" && !outcomeStatuses.has(app.status) && app.status !== "archived") ||
      (statusFilter === "interviewing" && interviewingStatuses.has(app.status)) ||
      (statusFilter === "outcome" && outcomeStatuses.has(app.status)) ||
      (statusFilter === "archived" && app.status === "archived");
    const followUpMatch =
      followUpFilter === "all" ||
      (followUpFilter === "due" && isFollowUpDue(app)) ||
      (followUpFilter === "scheduled" && Boolean(app.follow_up_at));
    return statusMatch && followUpMatch;
  });


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
        resume_id: newResumeId || null,
        cover_letter_id: selectedNewLetterId || null,
        status: newStatus,
        follow_up_at: dateToIso(newFollowUpDate),
        notes: newNotes,
      });
      setApplications((current) => [created, ...(current ?? [])]);
      setDrafts((current) => ({
        ...current,
        [created.id]: draftFromApplication(created),
      }));
      await refreshFollowUps();
      setShowCreate(false);
      setNewStatus("saved");
      setNewFollowUpDate("");
      setNewNotes("");
      setNewResumeId("");
      setNewCoverLetterId("");
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
        resume_id: draft.resumeId || null,
        cover_letter_id: draft.coverLetterId || null,
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
      await refreshFollowUps();
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
      await refreshFollowUps();
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

  async function toggleWorkflow(app: TrackedApplication) {
    if (expandedId === app.id) {
      setExpandedId(null);
      return;
    }
    setExpandedId(app.id);
    if (workflows[app.id]) return;
    setWorkflowLoadingId(app.id);
    setWorkflowErrors((current) => {
      const next = { ...current };
      delete next[app.id];
      return next;
    });
    try {
      const workflow = await getApplicationWorkflow(app.id);
      setWorkflows((current) => ({ ...current, [app.id]: workflow }));
    } catch (err) {
      setWorkflowErrors((current) => ({
        ...current,
        [app.id]: err instanceof ApiError ? err.message || "Could not load workflow." : "Could not load workflow.",
      }));
    } finally {
      setWorkflowLoadingId(null);
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

      <div className="flex flex-wrap items-end gap-3">
        <div className="space-y-1.5">
          <Label htmlFor="application-status-filter" className="flex items-center gap-2">
            <Filter className="size-4" />
            Status
          </Label>
          <select
            id="application-status-filter"
            className={selectClass}
            value={statusFilter}
            onChange={(event) => setStatusFilter(event.target.value as StatusFilter)}
          >
            <option value="all">All statuses</option>
            <option value="active">Active</option>
            <option value="interviewing">Interviewing</option>
            <option value="outcome">Offer/rejected/withdrawn</option>
            <option value="archived">Archived</option>
          </select>
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="application-follow-up-filter">Follow-up</Label>
          <select
            id="application-follow-up-filter"
            className={selectClass}
            value={followUpFilter}
            onChange={(event) => setFollowUpFilter(event.target.value as FollowUpFilter)}
          >
            <option value="all">All applications</option>
            <option value="due">Due now</option>
            <option value="scheduled">With reminder</option>
          </select>
        </div>
      </div>
      {followUps && followUps.length > 0 && (
        <section className="space-y-3">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <h2 className="font-display text-base font-semibold">
              Upcoming reminders
            </h2>
            <Badge variant="outline">
              <CalendarClock className="size-3" />
              Next 14 days
            </Badge>
          </div>
          <ul className="grid gap-3 md:grid-cols-2">
            {followUps.slice(0, 4).map((item) => (
              <li key={item.id}>
                <Card className="gap-0 py-4">
                  <CardContent className="space-y-2 px-4">
                    <div className="flex items-start justify-between gap-3">
                      <div className="min-w-0">
                        <p className="truncate text-sm font-medium">
                          {item.job.title}
                        </p>
                        <p className="text-muted-foreground truncate text-xs">
                          {item.job.company_name}
                          {item.job.location ? ` - ${item.job.location}` : ""}
                        </p>
                      </div>
                      <Badge variant={item.due ? "warning" : "outline"}>
                        {item.due ? "Due" : formatDate(item.follow_up_at)}
                      </Badge>
                    </div>
                    {item.latest_activity && (
                      <p className="text-muted-foreground line-clamp-2 text-xs">
                        {item.latest_activity.description ??
                          label(item.latest_activity.event_type)}
                      </p>
                    )}
                  </CardContent>
                </Card>
              </li>
            ))}
          </ul>
        </section>
      )}

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
                  onChange={(event) => {
                    setNewJobId(event.target.value);
                    setNewCoverLetterId("");
                  }}
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
                <Label htmlFor="application-resume">Resume</Label>
                <select
                  id="application-resume"
                  className={selectClass}
                  value={newResumeId}
                  onChange={(event) => {
                    const resumeId = event.target.value;
                    setNewResumeId(resumeId);
                    const letter = coverLetters.find(
                      (item) => item.id === selectedNewLetterId
                    );
                    if (letter && letter.resume_id !== resumeId) {
                      setNewCoverLetterId("");
                    }
                  }}
                  disabled={savingId === "new"}
                >
                  <option value="">No linked resume</option>
                  {resumes.map((resume) => (
                    <option key={resume.id} value={resume.id}>
                      {resume.title}{resume.is_default ? " (default)" : ""}
                    </option>
                  ))}
                </select>
              </div>
              <div className="space-y-1.5 md:col-span-4">
                <Label htmlFor="application-cover-letter">Cover letter</Label>
                <select
                  id="application-cover-letter"
                  className={selectClass}
                  value={selectedNewLetterId}
                  onChange={(event) => {
                    const id = event.target.value;
                    setNewCoverLetterId(id);
                    const letter = availableNewLetters.find((item) => item.id === id);
                    if (letter) setNewResumeId(letter.resume_id);
                  }}
                  disabled={savingId === "new"}
                >
                  <option value="">No linked cover letter</option>
                  {availableNewLetters.map((letter) => (
                    <option key={letter.id} value={letter.id}>
                      {label(letter.tone)} · {label(letter.status)}
                    </option>
                  ))}
                </select>
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
          {filteredApplications.map((app) => {
            const draft = drafts[app.id] ?? draftFromApplication(app);
            const saving = savingId === app.id;
            const expanded = expandedId === app.id;
            const workflow = workflows[app.id];
            const workflowError = workflowErrors[app.id];
            const workflowLoading = workflowLoadingId === app.id;
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

                    <div className="flex justify-end">
                      <Button
                        type="button"
                        variant="outline"
                        size="sm"
                        onClick={() => void toggleWorkflow(app)}
                        disabled={workflowLoading}
                      >
                        {workflowLoading ? (
                          <Loader2 className="size-4 animate-spin" />
                        ) : (
                          <ChevronDown className={`size-4 transition-transform ${expanded ? "rotate-180" : ""}`} />
                        )}
                        Workflow
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

                    <div className="grid gap-3 md:grid-cols-2">
                      <div className="space-y-1.5">
                        <Label htmlFor={`resume-${app.id}`}>Linked resume</Label>
                        <select
                          id={`resume-${app.id}`}
                          className={selectClass}
                          value={draft.resumeId}
                          onChange={(event) => {
                            const resumeId = event.target.value;
                            const letter = coverLetters.find(
                              (item) => item.id === draft.coverLetterId
                            );
                            updateDraft(app.id, {
                              resumeId,
                              coverLetterId:
                                letter && letter.resume_id !== resumeId
                                  ? ""
                                  : draft.coverLetterId,
                            });
                          }}
                          disabled={saving}
                        >
                          <option value="">No linked resume</option>
                          {resumes.map((resume) => (
                            <option key={resume.id} value={resume.id}>
                              {resume.title}{resume.is_default ? " (default)" : ""}
                            </option>
                          ))}
                        </select>
                      </div>
                      <div className="space-y-1.5">
                        <Label htmlFor={`cover-letter-${app.id}`}>Linked cover letter</Label>
                        <select
                          id={`cover-letter-${app.id}`}
                          className={selectClass}
                          value={draft.coverLetterId}
                          onChange={(event) => {
                            const id = event.target.value;
                            const letter = coverLetters.find((item) => item.id === id);
                            updateDraft(app.id, {
                              coverLetterId: id,
                              resumeId: letter?.resume_id ?? draft.resumeId,
                            });
                          }}
                          disabled={saving}
                        >
                          <option value="">No linked cover letter</option>
                          {coverLetters
                            .filter((letter) => letter.job_id === app.job_id)
                            .map((letter) => (
                              <option key={letter.id} value={letter.id}>
                                {label(letter.tone)} · {label(letter.status)}
                              </option>
                            ))}
                        </select>
                      </div>
                    </div>

                    {expanded && (
                      <div className="border-border/70 bg-secondary/25 space-y-4 rounded-lg border p-4 text-sm">
                        {workflowLoading ? (
                          <div className="text-muted-foreground flex items-center gap-2">
                            <Loader2 className="size-4 animate-spin" />
                            Loading workflow...
                          </div>
                        ) : workflowError ? (
                          <p role="alert" className="text-destructive">{workflowError}</p>
                        ) : workflow ? (
                          <div className="grid gap-4 lg:grid-cols-2">
                            <section className="space-y-2">
                              <h3 className="flex items-center gap-2 font-medium">
                                <FileText className="text-primary size-4" />
                                Materials
                              </h3>
                              <p className="text-muted-foreground">
                                Linked resume: {workflow.linked_resume?.title ?? (app.resume_id ? "Linked resume" : "None")}
                              </p>
                              <p className="text-muted-foreground">
                                Cover letter: {workflow.linked_cover_letter ? label(workflow.linked_cover_letter.status) : app.cover_letter_id ? "Linked" : "None"}
                              </p>
                              <p className="text-muted-foreground">
                                Next action: {workflow.next_action.due_at ? `${workflow.next_action.label} ${formatDate(workflow.next_action.due_at)}` : workflow.next_action.label}
                              </p>
                            </section>

                            <section className="space-y-2">
                              <h3 className="flex items-center gap-2 font-medium">
                                <Users className="text-primary size-4" />
                                Contacts
                              </h3>
                              {workflow.contacts.length > 0 ? (
                                <ul className="space-y-1">
                                  {workflow.contacts.map((contact) => (
                                    <li key={contact.id} className="text-muted-foreground">
                                      {contact.name}{contact.role ? `, ${contact.role}` : ""}{contact.email ? ` - ${contact.email}` : ""}
                                    </li>
                                  ))}
                                </ul>
                              ) : (
                                <p className="text-muted-foreground">No contacts linked.</p>
                              )}
                            </section>

                            <section className="space-y-2">
                              <h3 className="flex items-center gap-2 font-medium">
                                <Mail className="text-primary size-4" />
                                Outreach
                              </h3>
                              {workflow.outreach_drafts.length > 0 ? (
                                <ul className="flex flex-wrap gap-2">
                                  {workflow.outreach_drafts.map((item) => (
                                    <li key={item.id}>
                                      <Badge variant="outline">{label(item.message_type)} - {label(item.status)}</Badge>
                                    </li>
                                  ))}
                                </ul>
                              ) : (
                                <p className="text-muted-foreground">No outreach drafts linked.</p>
                              )}
                            </section>

                            <section className="space-y-2">
                              <h3 className="flex items-center gap-2 font-medium">
                                <Activity className="text-primary size-4" />
                                Activity
                              </h3>
                              {workflow.recent_activity.length > 0 ? (
                                <ul className="space-y-1">
                                  {workflow.recent_activity.slice(0, 5).map((event) => (
                                    <li key={`${event.entity_type}-${event.entity_id}-${event.created_at}`} className="text-muted-foreground">
                                      {event.description ?? label(event.event_type)} - {formatDate(event.created_at)}
                                    </li>
                                  ))}
                                </ul>
                              ) : (
                                <p className="text-muted-foreground">No activity yet.</p>
                              )}
                            </section>
                          </div>
                        ) : null}
                      </div>
                    )}
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
