"use client";

import * as React from "react";
import {
  Check,
  Clipboard,
  FileText,
  Loader2,
  MailWarning,
  Plus,
  Save,
} from "lucide-react";

import { ApiError } from "@/lib/api";
import {
  createCoverLetter,
  listCoverLetters,
  updateCoverLetter,
} from "@/lib/cover-letters";
import { listResumes, type ResumeDetail } from "@/lib/resumes";
import type {
  CoverLetter,
  CoverLetterStatus,
  CoverLetterTone,
} from "@/lib/types";
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

interface CoverLetterPanelProps {
  jobId: string;
}

type DraftState = {
  content: string;
  tone: CoverLetterTone;
  status: CoverLetterStatus;
};

type Busy = "create" | `save:${string}` | `copy:${string}` | null;

const tones: CoverLetterTone[] = [
  "professional",
  "friendly",
  "concise",
  "enthusiastic",
];
const statuses: CoverLetterStatus[] = [
  "draft",
  "reviewed",
  "accepted",
  "rejected",
  "exported",
];
const selectClass =
  "border-input bg-card focus-visible:border-ring focus-visible:ring-ring/40 h-9 w-full rounded-md border px-3 text-sm shadow-xs outline-none focus-visible:ring-[3px] disabled:cursor-not-allowed disabled:opacity-50";
const textareaClass =
  "border-input bg-card focus-visible:border-ring focus-visible:ring-ring/40 min-h-72 w-full rounded-md border px-3 py-2 text-sm leading-relaxed shadow-xs outline-none focus-visible:ring-[3px] disabled:cursor-not-allowed disabled:opacity-50";

function label(value: string): string {
  return value
    .split("_")
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

function formatDate(value: string): string {
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value));
}

function resumeLabel(resumes: ResumeDetail[], resumeId: string): string {
  return resumes.find((resume) => resume.id === resumeId)?.title ?? "Resume";
}

function statusVariant(
  status: CoverLetterStatus
): "info" | "success" | "warning" | "destructive" | "outline" {
  if (status === "draft") return "info";
  if (status === "reviewed") return "warning";
  if (status === "accepted" || status === "exported") return "success";
  if (status === "rejected") return "destructive";
  return "outline";
}

function draftFromCoverLetter(coverLetter: CoverLetter): DraftState {
  return {
    content: coverLetter.content,
    tone: coverLetter.tone,
    status: coverLetter.status,
  };
}

function errorMessage(err: unknown, fallback: string): string {
  return err instanceof ApiError ? err.message || fallback : fallback;
}

export function CoverLetterPanel({ jobId }: CoverLetterPanelProps) {
  const [resumes, setResumes] = React.useState<ResumeDetail[]>([]);
  const [coverLetters, setCoverLetters] = React.useState<CoverLetter[] | null>(
    null
  );
  const [drafts, setDrafts] = React.useState<Record<string, DraftState>>({});
  const [selectedResumeId, setSelectedResumeId] = React.useState("");
  const [tone, setTone] = React.useState<CoverLetterTone>("professional");
  const [busy, setBusy] = React.useState<Busy>(null);
  const [error, setError] = React.useState<string | null>(null);
  const [actionError, setActionError] = React.useState<string | null>(null);

  React.useEffect(() => {
    let active = true;
    (async () => {
      setError(null);
      try {
        const [resumeData, coverLetterData] = await Promise.all([
          listResumes(),
          listCoverLetters(jobId),
        ]);
        if (!active) return;
        setResumes(resumeData);
        setCoverLetters(coverLetterData);
        setDrafts(
          Object.fromEntries(
            coverLetterData.map((item) => [item.id, draftFromCoverLetter(item)])
          )
        );
        const defaultResume = resumeData.find((resume) => resume.is_default);
        setSelectedResumeId(defaultResume?.id ?? resumeData[0]?.id ?? "");
      } catch (err) {
        if (!active) return;
        setError(
          err instanceof ApiError && err.isUnauthorized
            ? "Please sign in to view cover-letter drafts."
            : "Could not load cover-letter drafts. Is the backend running?"
        );
        setCoverLetters([]);
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
      setActionError(errorMessage(err, "Action failed."));
    } finally {
      setBusy(null);
    }
  }

  function updateDraft(id: string, changes: Partial<DraftState>) {
    setDrafts((current) => ({
      ...current,
      [id]: { ...current[id], ...changes },
    }));
  }

  function replaceCoverLetter(updated: CoverLetter) {
    setCoverLetters((current) =>
      (current ?? []).map((item) => (item.id === updated.id ? updated : item))
    );
    setDrafts((current) => ({
      ...current,
      [updated.id]: draftFromCoverLetter(updated),
    }));
  }

  function onCreate() {
    if (!selectedResumeId) return;
    return run("create", async () => {
      const created = await createCoverLetter({
        job_id: jobId,
        resume_id: selectedResumeId,
        tone,
      });
      setCoverLetters((current) => [created, ...(current ?? [])]);
      setDrafts((current) => ({
        ...current,
        [created.id]: draftFromCoverLetter(created),
      }));
    });
  }

  function onSave(item: CoverLetter) {
    return run(`save:${item.id}`, async () => {
      const draft = drafts[item.id] ?? draftFromCoverLetter(item);
      const updated = await updateCoverLetter(item.id, draft);
      replaceCoverLetter(updated);
    });
  }

  function onCopy(item: CoverLetter) {
    return run(`copy:${item.id}`, async () => {
      const draft = drafts[item.id] ?? draftFromCoverLetter(item);
      if (!navigator.clipboard?.writeText) {
        throw new Error("Clipboard API is not supported in this browser or context.");
      }
      await navigator.clipboard.writeText(draft.content);
      const updated = await updateCoverLetter(item.id, {
        ...draft,
        status: "exported",
      });
      replaceCoverLetter(updated);
    });
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-base">
          <FileText className="text-primary size-4" />
          Cover letters
        </CardTitle>
        <CardDescription>
          Create local drafts for this job, edit them manually, and copy text
          yourself. JobGoblin does not send or submit cover letters.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-5">
        <div className="border-border/70 bg-secondary/30 flex gap-3 rounded-lg border p-3">
          <MailWarning className="text-warning-foreground mt-0.5 size-4 shrink-0" />
          <p className="text-muted-foreground text-sm">
            Drafts stay in JobGoblin for review only. Copying puts text on your
            clipboard; it does not email anyone, open a job site, or apply for
            the role.
          </p>
        </div>

        <div className="grid grid-cols-1 gap-4 lg:grid-cols-[1fr_1fr_auto] lg:items-end">
          <div className="space-y-2">
            <Label htmlFor="cover-letter-resume">Resume</Label>
            <select
              id="cover-letter-resume"
              className={selectClass}
              value={selectedResumeId}
              disabled={busy !== null || resumes.length === 0}
              onChange={(event) => setSelectedResumeId(event.target.value)}
            >
              {resumes.length === 0 ? (
                <option value="">No resumes available</option>
              ) : (
                resumes.map((resume) => (
                  <option key={resume.id} value={resume.id}>
                    {resume.title}{resume.is_default ? " (default)" : ""}
                  </option>
                ))
              )}
            </select>
          </div>

          <div className="space-y-2">
            <Label htmlFor="cover-letter-tone">Tone</Label>
            <select
              id="cover-letter-tone"
              className={selectClass}
              value={tone}
              disabled={busy !== null}
              onChange={(event) =>
                setTone(event.target.value as CoverLetterTone)
              }
            >
              {tones.map((item) => (
                <option key={item} value={item}>
                  {label(item)}
                </option>
              ))}
            </select>
          </div>

          <Button
            type="button"
            onClick={onCreate}
            disabled={busy !== null || !selectedResumeId}
          >
            {busy === "create" ? (
              <Loader2 className="size-4 animate-spin" />
            ) : (
              <Plus className="size-4" />
            )}
            {busy === "create" ? "Creating..." : "Create draft"}
          </Button>
        </div>

        {error && (
          <p
            role="alert"
            className="bg-destructive/10 text-destructive rounded-md px-3 py-2 text-sm"
          >
            {error}
          </p>
        )}
        {actionError && (
          <p
            role="alert"
            className="bg-destructive/10 text-destructive rounded-md px-3 py-2 text-sm"
          >
            {actionError}
          </p>
        )}

        {coverLetters === null ? (
          <div className="text-muted-foreground flex items-center gap-2 text-sm">
            <Loader2 className="size-4 animate-spin" />
            Loading cover-letter drafts...
          </div>
        ) : coverLetters.length === 0 ? (
          <p className="text-muted-foreground rounded-md border border-dashed px-3 py-4 text-sm">
            No cover-letter drafts for this job yet. Pick a resume and create a
            draft to review.
          </p>
        ) : (
          <ul className="space-y-4">
            {coverLetters.map((item) => {
              const draft = drafts[item.id] ?? draftFromCoverLetter(item);
              const saving = busy === `save:${item.id}`;
              const copying = busy === `copy:${item.id}`;
              const disabled = busy !== null;
              return (
                <li
                  key={item.id}
                  className="border-border/70 rounded-lg border p-4"
                >
                  <div className="space-y-4">
                    <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
                      <div className="min-w-0 space-y-2">
                        <div className="flex flex-wrap items-center gap-2">
                          <span className="font-medium">
                            {resumeLabel(resumes, item.resume_id)}
                          </span>
                          <Badge variant={statusVariant(draft.status)}>
                            {draft.status === "exported" && (
                              <Check className="size-3" />
                            )}
                            {label(draft.status)}
                          </Badge>
                          <Badge variant="outline">{label(draft.tone)}</Badge>
                        </div>
                        <p className="text-muted-foreground text-sm">
                          Updated {formatDate(item.updated_at)}
                        </p>
                      </div>

                      <div className="flex shrink-0 flex-wrap items-center gap-2">
                        <Button
                          type="button"
                          variant="outline"
                          size="sm"
                          onClick={() => onCopy(item)}
                          disabled={disabled}
                        >
                          {copying ? (
                            <Loader2 className="size-4 animate-spin" />
                          ) : (
                            <Clipboard className="size-4" />
                          )}
                          Copy
                        </Button>
                      </div>
                    </div>

                    <div className="grid gap-3 md:grid-cols-2">
                      <div className="space-y-1.5">
                        <Label htmlFor={`cover-letter-tone-${item.id}`}>
                          Tone
                        </Label>
                        <select
                          id={`cover-letter-tone-${item.id}`}
                          className={selectClass}
                          value={draft.tone}
                          disabled={disabled}
                          onChange={(event) =>
                            updateDraft(item.id, {
                              tone: event.target.value as CoverLetterTone,
                            })
                          }
                        >
                          {tones.map((toneOption) => (
                            <option key={toneOption} value={toneOption}>
                              {label(toneOption)}
                            </option>
                          ))}
                        </select>
                      </div>

                      <div className="space-y-1.5">
                        <Label htmlFor={`cover-letter-status-${item.id}`}>
                          Status
                        </Label>
                        <select
                          id={`cover-letter-status-${item.id}`}
                          className={selectClass}
                          value={draft.status}
                          disabled={disabled}
                          onChange={(event) =>
                            updateDraft(item.id, {
                              status: event.target.value as CoverLetterStatus,
                            })
                          }
                        >
                          {statuses.map((statusOption) => (
                            <option key={statusOption} value={statusOption}>
                              {label(statusOption)}
                            </option>
                          ))}
                        </select>
                      </div>
                    </div>

                    <div className="space-y-1.5">
                      <Label htmlFor={`cover-letter-content-${item.id}`}>
                        Draft text
                      </Label>
                      <textarea
                        id={`cover-letter-content-${item.id}`}
                        className={textareaClass}
                        value={draft.content}
                        disabled={disabled}
                        onChange={(event) =>
                          updateDraft(item.id, { content: event.target.value })
                        }
                        placeholder="Review and edit the draft before copying it manually."
                      />
                    </div>

                    <div className="flex justify-end">
                      <Button
                        type="button"
                        onClick={() => onSave(item)}
                        disabled={disabled}
                      >
                        {saving ? (
                          <Loader2 className="size-4 animate-spin" />
                        ) : (
                          <Save className="size-4" />
                        )}
                        Save
                      </Button>
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