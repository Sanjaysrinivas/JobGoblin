"use client";

import * as React from "react";
import { Check, Clipboard, Loader2, MessageSquareText, Plus, Save } from "lucide-react";

import { ApiError } from "@/lib/api";
import {
  createInterviewPrep,
  listInterviewPrep,
  updateInterviewPrep,
} from "@/lib/interview-prep";
import { listResumes, type ResumeDetail } from "@/lib/resumes";
import type { InterviewPrep, InterviewPrepStatus } from "@/lib/types";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Label } from "@/components/ui/label";

const statuses: InterviewPrepStatus[] = ["draft", "reviewed", "ready", "archived"];
const selectClass =
  "border-input bg-card focus-visible:border-ring focus-visible:ring-ring/40 h-9 w-full rounded-md border px-3 text-sm shadow-xs outline-none focus-visible:ring-[3px] disabled:cursor-not-allowed disabled:opacity-50";
const textareaClass =
  "border-input bg-card focus-visible:border-ring focus-visible:ring-ring/40 min-h-24 w-full rounded-md border px-3 py-2 text-sm shadow-xs outline-none focus-visible:ring-[3px] disabled:cursor-not-allowed disabled:opacity-50";

type DraftState = {
  notes: string;
  status: InterviewPrepStatus;
};

type Busy = "create" | `save:${string}` | `copy:${string}` | null;

function label(value: string | null | undefined): string {
  if (!value) return "Unknown";
  return value
    .split("_")
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

function formatDate(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "Unknown date";
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(date);
}

function statusVariant(status: InterviewPrepStatus): "info" | "warning" | "success" | "outline" {
  if (status === "draft") return "info";
  if (status === "reviewed") return "warning";
  if (status === "ready") return "success";
  return "outline";
}

function resumeLabel(resumes: ResumeDetail[], resumeId: string | null): string {
  if (!resumeId) return "No resume linked";
  return resumes.find((resume) => resume.id === resumeId)?.title ?? "Resume";
}

function draftFromPrep(prep: InterviewPrep): DraftState {
  return { notes: prep.notes ?? "", status: prep.status };
}

function groupedQuestions(prep: InterviewPrep) {
  const groups = new Map<string, typeof prep.questions>();
  for (const question of prep.questions) {
    const key = question.category || "General";
    groups.set(key, [...(groups.get(key) ?? []), question]);
  }
  return Array.from(groups, ([title, questions]) => ({ title, questions }));
}

function prepText(prep: InterviewPrep, draft: DraftState): string {
  const groups = groupedQuestions(prep)
    .map((group) => [
      group.title,
      ...group.questions.map(
        (item) => `${item.question}\n${item.answer_outline}`
      ),
    ].join("\n\n"))
    .join("\n\n");
  return [groups, draft.notes ? `Notes\n${draft.notes}` : ""].filter(Boolean).join("\n\n");
}
function errorMessage(err: unknown, fallback: string): string {
  if (err instanceof ApiError) return err.message || fallback;
  if (err instanceof Error) return err.message || fallback;
  return fallback;
}

export function InterviewPrepPanel({
  jobId,
  applicationId = null,
}: {
  jobId: string;
  applicationId?: string | null;
}) {
  const [resumes, setResumes] = React.useState<ResumeDetail[]>([]);
  const [prep, setPrep] = React.useState<InterviewPrep[] | null>(null);
  const [drafts, setDrafts] = React.useState<Record<string, DraftState>>({});
  const [selectedResumeId, setSelectedResumeId] = React.useState("");
  const [newNotes, setNewNotes] = React.useState("");
  const [busy, setBusy] = React.useState<Busy>(null);
  const [error, setError] = React.useState<string | null>(null);
  const [actionError, setActionError] = React.useState<string | null>(null);

  React.useEffect(() => {
    let active = true;
    (async () => {
      setError(null);
      try {
        const [resumeData, prepData] = await Promise.all([
          listResumes(),
          listInterviewPrep(jobId, applicationId),
        ]);
        if (!active) return;
        setResumes(resumeData);
        setPrep(prepData);
        setDrafts(Object.fromEntries(prepData.map((item) => [item.id, draftFromPrep(item)])));
        const defaultResume = resumeData.find((resume) => resume.is_default);
        setSelectedResumeId(defaultResume?.id ?? resumeData[0]?.id ?? "");
      } catch (err) {
        if (!active) return;
        setError(
          err instanceof ApiError && err.isUnauthorized
            ? "Please sign in to view interview prep."
            : "Could not load interview prep. Is the backend running?"
        );
        setPrep([]);
      }
    })();
    return () => {
      active = false;
    };
  }, [jobId, applicationId]);

  async function run(kind: Exclude<Busy, null>, fn: () => Promise<void>) {
    setActionError(null);
    setBusy(kind);
    try {
      await fn();
    } catch (err) {
      setActionError(errorMessage(err, "Action failed."));
    } finally {
      setBusy(null);
    }
  }

  function draftForPrep(item: InterviewPrep): DraftState {
    return { ...draftFromPrep(item), ...drafts[item.id] };
  }

  function updateDraft(id: string, changes: Partial<DraftState>) {
    setDrafts((current) => ({
      ...current,
      [id]: { ...(current[id] ?? { notes: "", status: "draft" }), ...changes },
    }));
  }

  function replacePrep(updated: InterviewPrep) {
    setPrep((current) => (current ?? []).map((item) => (item.id === updated.id ? updated : item)));
    setDrafts((current) => ({ ...current, [updated.id]: draftFromPrep(updated) }));
  }

  function onCreate() {
    return run("create", async () => {
      const created = await createInterviewPrep({
        job_id: jobId,
        application_id: applicationId,
        resume_id: selectedResumeId || null,
        notes: newNotes || null,
      });
      setNewNotes("");
      setPrep((current) => [created, ...(current ?? [])]);
      setDrafts((current) => ({ ...current, [created.id]: draftFromPrep(created) }));
    });
  }

  function onSave(item: InterviewPrep) {
    return run(`save:${item.id}`, async () => {
      const draft = draftForPrep(item);
      replacePrep(await updateInterviewPrep(item.id, draft));
    });
  }

  function onCopy(item: InterviewPrep) {
    return run(`copy:${item.id}`, async () => {
      if (!navigator.clipboard?.writeText) {
        throw new Error("Clipboard API is not supported in this browser or context.");
      }
      await navigator.clipboard.writeText(prepText(item, draftForPrep(item)));
    });
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-base">
          <MessageSquareText className="text-primary size-4" />
          Interview prep
        </CardTitle>
        <CardDescription>
          Generate local prep packets from this job, review question outlines, and keep your notes here.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-5">
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-[1fr_1fr_auto] lg:items-end">
          <div className="space-y-2">
            <Label htmlFor="interview-prep-resume">Resume context</Label>
            <select
              id="interview-prep-resume"
              className={selectClass}
              value={selectedResumeId}
              disabled={busy !== null}
              onChange={(event) => setSelectedResumeId(event.target.value)}
            >
              <option value="">No resume context</option>
              {resumes.map((resume) => (
                <option key={resume.id} value={resume.id}>
                  {resume.title}{resume.is_default ? " (default)" : ""}
                </option>
              ))}
            </select>
          </div>
          <div className="space-y-2">
            <Label htmlFor="interview-prep-new-notes">Prep notes</Label>
            <textarea
              id="interview-prep-new-notes"
              className={textareaClass}
              value={newNotes}
              disabled={busy !== null}
              onChange={(event) => setNewNotes(event.target.value)}
              placeholder="Paste application notes, interview round details, or STAR-story reminders."
            />
          </div>
          <Button type="button" onClick={onCreate} disabled={busy !== null}>
            {busy === "create" ? <Loader2 className="size-4 animate-spin" /> : <Plus className="size-4" />}
            {busy === "create" ? "Creating..." : "Create prep"}
          </Button>
        </div>

        {error && <p role="alert" className="bg-destructive/10 text-destructive rounded-md px-3 py-2 text-sm">{error}</p>}
        {actionError && <p role="alert" className="bg-destructive/10 text-destructive rounded-md px-3 py-2 text-sm">{actionError}</p>}

        {prep === null ? (
          <div className="text-muted-foreground flex items-center gap-2 text-sm">
            <Loader2 className="size-4 animate-spin" />
            Loading interview prep...
          </div>
        ) : prep.length === 0 ? (
          <p className="text-muted-foreground rounded-md border border-dashed px-3 py-4 text-sm">
            No interview prep for this job yet.
          </p>
        ) : (
          <ul className="space-y-4">
            {prep.map((item) => {
              const draft = draftForPrep(item);
              const saving = busy === `save:${item.id}`;
              const copying = busy === `copy:${item.id}`;
              const disabled = busy !== null;
              return (
                <li key={item.id} className="border-border/70 rounded-lg border p-4">
                  <div className="space-y-4">
                    <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
                      <div className="min-w-0 space-y-2">
                        <div className="flex flex-wrap items-center gap-2">
                          <span className="font-medium">{resumeLabel(resumes, item.resume_id)}</span>
                          <Badge variant={statusVariant(draft.status)}>
                            {draft.status === "ready" && <Check className="size-3" />}
                            {label(draft.status)}
                          </Badge>
                        </div>
                        <p className="text-muted-foreground text-sm">Updated {formatDate(item.updated_at)}</p>
                      </div>
                      <Button type="button" variant="outline" size="sm" onClick={() => onCopy(item)} disabled={disabled}>
                        {copying ? <Loader2 className="size-4 animate-spin" /> : <Clipboard className="size-4" />}
                        Copy prep
                      </Button>
                    </div>

                    <div className="grid gap-3 md:grid-cols-[12rem_minmax(0,1fr)_auto] md:items-end">
                      <div className="space-y-1.5">
                        <Label htmlFor={`prep-status-${item.id}`}>Status</Label>
                        <select
                          id={`prep-status-${item.id}`}
                          className={selectClass}
                          value={draft.status}
                          disabled={disabled}
                          onChange={(event) => updateDraft(item.id, { status: event.target.value as InterviewPrepStatus })}
                        >
                          {statuses.map((status) => (
                            <option key={status} value={status}>{label(status)}</option>
                          ))}
                        </select>
                      </div>
                      <div className="space-y-1.5">
                        <Label htmlFor={`prep-notes-${item.id}`}>Notes</Label>
                        <textarea
                          id={`prep-notes-${item.id}`}
                          className={textareaClass}
                          value={draft.notes}
                          disabled={disabled}
                          onChange={(event) => updateDraft(item.id, { notes: event.target.value })}
                          placeholder="Add examples, gaps to review, or reminders."
                        />
                      </div>
                      <Button type="button" onClick={() => onSave(item)} disabled={disabled}>
                        {saving ? <Loader2 className="size-4 animate-spin" /> : <Save className="size-4" />}
                        Save
                      </Button>
                    </div>

                    <div className="space-y-4">
                      {groupedQuestions(item).map((group) => (
                        <section key={group.title} className="space-y-2">
                          <h3 className="text-sm font-medium">{group.title}</h3>
                          <ul className="space-y-2">
                            {group.questions.map((question) => (
                              <li key={question.question} className="bg-secondary/35 rounded-md p-3">
                                <p className="text-sm font-medium">{question.question}</p>
                                <p className="text-muted-foreground mt-2 whitespace-pre-wrap text-sm">{question.answer_outline}</p>
                                <p className="text-muted-foreground mt-2 text-xs">{question.why}</p>
                                {question.evidence.length > 0 && (
                                  <div className="mt-2 flex flex-wrap gap-1">
                                    {question.evidence.map((item) => (
                                      <Badge key={item} variant="outline">{item}</Badge>
                                    ))}
                                  </div>
                                )}
                              </li>
                            ))}
                          </ul>
                        </section>
                      ))}
                    </div>
                  </div>
                </li>
              );
            })}
          </ul>
        )}
      </CardContent>
    </Card>
  );
}