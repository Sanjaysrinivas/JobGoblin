"use client";

import * as React from "react";
import Link from "next/link";
import { Check, Download, ExternalLink, FileText, Loader2, Plus, Trash2 } from "lucide-react";

import { ApiError } from "@/lib/api";
import {
  createTailoredResumeDraft,
  deleteResumeVersion,
  fetchResumePdf,
  fetchResumeVersionPdf,
  listResumes,
  listResumeVersions,
  listTailoredResumeDrafts,
  makeResumeVersionCurrent,
  type ResumeDetail,
} from "@/lib/resumes";
import type { ResumeVersion } from "@/lib/types";
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

const selectClass =
  "border-input bg-card focus-visible:border-ring focus-visible:ring-ring/40 h-9 w-full rounded-md border px-3 text-sm shadow-xs outline-none focus-visible:ring-[3px] disabled:cursor-not-allowed disabled:opacity-50";

type Busy = "create" | `accept:${string}` | `reject:${string}` | `export:${string}` | null;


function formatDate(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "Unknown date";
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(date);
}

function resumeLabel(resumes: ResumeDetail[], resumeId: string): string {
  return resumes.find((resume) => resume.id === resumeId)?.title ?? "Resume";
}

function versionLabel(versions: ResumeVersion[], versionId: string | null): string {
  if (!versionId) return "Current version";
  return versions.find((version) => version.id === versionId)?.title ?? "Version";
}

function formatValue(value: unknown): string {
  if (Array.isArray(value)) return value.join(", ");
  if (typeof value === "string") return value;
  if (value == null) return "None";
  return JSON.stringify(value);
}

function actionLabel(value: string): string {
  return value
    .split("_")
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}
function downloadBlob(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

function errorMessage(err: unknown, fallback: string): string {
  if (err instanceof ApiError) return err.message || fallback;
  if (err instanceof Error) return err.message || fallback;
  return fallback;
}

export function TailoredResumePanel({ jobId }: { jobId: string }) {
  const [resumes, setResumes] = React.useState<ResumeDetail[]>([]);
  const [versions, setVersions] = React.useState<ResumeVersion[]>([]);
  const [drafts, setDrafts] = React.useState<ResumeVersion[] | null>(null);
  const [selectedResumeId, setSelectedResumeId] = React.useState("");
  const [selectedVersionId, setSelectedVersionId] = React.useState("");
  const [busy, setBusy] = React.useState<Busy>(null);
  const [loadingVersions, setLoadingVersions] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);
  const [actionError, setActionError] = React.useState<string | null>(null);

  React.useEffect(() => {
    let active = true;
    (async () => {
      setError(null);
      try {
        const [resumeData, draftData] = await Promise.all([
          listResumes(),
          listTailoredResumeDrafts(jobId),
        ]);
        if (!active) return;
        const defaultResume = resumeData.find((resume) => resume.is_default);
        const nextResumeId = defaultResume?.id ?? resumeData[0]?.id ?? "";
        setResumes(resumeData);
        setDrafts(draftData);
        setSelectedResumeId(nextResumeId);
        if (!nextResumeId) {
          setVersions([]);
          setSelectedVersionId("");
        }
      } catch (err) {
        if (!active) return;
        setError(
          err instanceof ApiError && err.isUnauthorized
            ? "Please sign in to view tailored resume drafts."
            : "Could not load tailored resume drafts. Is the backend running?"
        );
        setDrafts([]);
      }
    })();
    return () => {
      active = false;
    };
  }, [jobId]);

  React.useEffect(() => {
    if (!selectedResumeId) {
      let active = true;
      queueMicrotask(() => {
        if (!active) return;
        setVersions([]);
        setSelectedVersionId("");
      });
      return () => {
        active = false;
      };
    }

    let active = true;
    (async () => {
      setLoadingVersions(true);
      try {
        const data = await listResumeVersions(selectedResumeId);
        if (!active) return;
        setVersions(data);
        const current = data.find((version) => version.is_current);
        setSelectedVersionId(current?.id ?? data[0]?.id ?? "");
      } catch {
        if (!active) return;
        setVersions([]);
        setSelectedVersionId("");
      } finally {
        if (active) setLoadingVersions(false);
      }
    })();
    return () => {
      active = false;
    };
  }, [selectedResumeId]);

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

  function onCreate() {
    if (!selectedResumeId) return;
    return run("create", async () => {
      const created = await createTailoredResumeDraft(jobId, {
        resume_id: selectedResumeId,
        source_version_id: selectedVersionId || null,
      });
      setDrafts((current) => [created, ...(current ?? [])]);
    });
  }

  function onAccept(draft: ResumeVersion) {
    return run(`accept:${draft.id}`, async () => {
      const updated = await makeResumeVersionCurrent(draft.resume_id, draft.id);
      setDrafts((current) =>
        (current ?? []).map((item) =>
          item.resume_id === updated.resume_id
            ? { ...item, is_current: item.id === updated.id }
            : item
        )
      );
    });
  }

  function onReject(draft: ResumeVersion) {
    return run(`reject:${draft.id}`, async () => {
      await deleteResumeVersion(draft.resume_id, draft.id);
      setDrafts((current) => (current ?? []).filter((item) => item.id !== draft.id));
    });
  }

  function onExport(draft: ResumeVersion) {
    return run(`export:${draft.id}`, async () => {
      const blob = draft.id
        ? await fetchResumeVersionPdf(draft.resume_id, draft.id)
        : await fetchResumePdf(draft.resume_id);
      downloadBlob(blob, `${draft.title || "tailored-resume"}.pdf`);
    });
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-base">
          <FileText className="text-primary size-4" />
          Tailored resumes
        </CardTitle>
        <CardDescription>
          Create grounded resume-version drafts for this job, then edit and export from the resume screen.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-5">
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-[1fr_1fr_auto] lg:items-end">
          <div className="space-y-2">
            <Label htmlFor="tailored-resume">Resume</Label>
            <select
              id="tailored-resume"
              className={selectClass}
              value={selectedResumeId}
              disabled={busy !== null || resumes.length === 0}
              onChange={(event) => {
                setSelectedResumeId(event.target.value);
                if (!event.target.value) {
                  setVersions([]);
                  setSelectedVersionId("");
                }
              }}
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
            <Label htmlFor="tailored-version">Source version</Label>
            <select
              id="tailored-version"
              className={selectClass}
              value={selectedVersionId}
              disabled={busy !== null || loadingVersions || versions.length === 0}
              onChange={(event) => setSelectedVersionId(event.target.value)}
            >
              {versions.length === 0 ? (
                <option value="">Current version</option>
              ) : (
                versions.map((version) => (
                  <option key={version.id} value={version.id}>
                    {version.title}{version.is_current ? " (current)" : ""}
                  </option>
                ))
              )}
            </select>
          </div>
          <Button type="button" onClick={onCreate} disabled={busy !== null || !selectedResumeId}>
            {busy === "create" ? <Loader2 className="size-4 animate-spin" /> : <Plus className="size-4" />}
            {busy === "create" ? "Creating..." : "Create draft"}
          </Button>
        </div>

        {error && <p role="alert" className="bg-destructive/10 text-destructive rounded-md px-3 py-2 text-sm">{error}</p>}
        {actionError && <p role="alert" className="bg-destructive/10 text-destructive rounded-md px-3 py-2 text-sm">{actionError}</p>}

        {drafts === null ? (
          <div className="text-muted-foreground flex items-center gap-2 text-sm">
            <Loader2 className="size-4 animate-spin" />
            Loading tailored drafts...
          </div>
        ) : drafts.length === 0 ? (
          <p className="text-muted-foreground rounded-md border border-dashed px-3 py-4 text-sm">
            No tailored resume drafts for this job yet.
          </p>
        ) : (
          <ul className="space-y-3">
            {drafts.map((draft) => {
              const exporting = busy === `export:${draft.id}`;
              const accepting = busy === `accept:${draft.id}`;
              const rejecting = busy === `reject:${draft.id}`;
              const tailoring = draft.parsed_json?.tailoring;
              const changes = tailoring?.suggested_changes ?? [];
              const diffs = tailoring?.diff ?? [];
              const matched = tailoring?.grounding?.matched_existing_terms ?? [];
              const missing = tailoring?.grounding?.job_terms_not_added ?? [];
              const sourceTitle =
                tailoring?.source?.source_version_title ??
                versionLabel(versions, draft.source_version_id);
              return (
                <li key={draft.id} className="border-border/70 rounded-lg border p-4">
                  <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
                    <div className="min-w-0 space-y-2">
                      <div className="flex flex-wrap items-center gap-2">
                        <span className="font-medium">{draft.title || resumeLabel(resumes, draft.resume_id)}</span>
                        <Badge variant={draft.is_current ? "success" : "info"}>{draft.is_current ? "Accepted" : "Draft"}</Badge>
                        <Badge variant="outline">Source: {sourceTitle}</Badge>
                      </div>
                      <p className="text-muted-foreground text-sm">Updated {formatDate(draft.updated_at)}</p>
                      {tailoring?.grounding?.rule && (
                        <p className="text-muted-foreground text-sm">{tailoring.grounding.rule}</p>
                      )}
                    </div>
                    <div className="flex shrink-0 flex-wrap items-center gap-2">
                      <Button variant="outline" size="sm" asChild>
                        <Link href={`/resumes/${draft.resume_id}`}>
                          <ExternalLink className="size-4" />
                          Open editor
                        </Link>
                      </Button>
                      <Button type="button" variant="outline" size="sm" onClick={() => onAccept(draft)} disabled={busy !== null || draft.is_current}>
                        {accepting ? <Loader2 className="size-4 animate-spin" /> : <Check className="size-4" />}
                        Accept
                      </Button>
                      <Button type="button" variant="outline" size="sm" onClick={() => onReject(draft)} disabled={busy !== null || draft.is_current}>
                        {rejecting ? <Loader2 className="size-4 animate-spin" /> : <Trash2 className="size-4" />}
                        Reject
                      </Button>
                      <Button type="button" variant="outline" size="sm" onClick={() => onExport(draft)} disabled={busy !== null}>
                        {exporting ? <Loader2 className="size-4 animate-spin" /> : <Download className="size-4" />}
                        Export PDF
                      </Button>
                    </div>
                  </div>

                  {(changes.length > 0 || matched.length > 0 || missing.length > 0) && (
                    <div className="mt-4 grid gap-3 lg:grid-cols-2">
                      <section className="space-y-2">
                        <h4 className="text-sm font-medium">What changed</h4>
                        {changes.length > 0 ? (
                          <ul className="space-y-2 text-sm">
                            {changes.map((change, index) => (
                              <li key={`${change.section}-${change.action}-${index}`} className="text-muted-foreground">
                                <span className="text-foreground font-medium">{change.section}:</span>{" "}
                                {actionLabel(change.action)}. {change.why}
                              </li>
                            ))}
                          </ul>
                        ) : (
                          <p className="text-muted-foreground text-sm">No structured changes recorded.</p>
                        )}
                      </section>

                      <section className="space-y-2">
                        <h4 className="text-sm font-medium">Grounding</h4>
                        {matched.length > 0 && (
                          <p className="text-muted-foreground text-sm">Existing terms: {matched.join(", ")}</p>
                        )}
                        {missing.length > 0 && (
                          <p className="text-muted-foreground text-sm">Verify before adding: {missing.join(", ")}</p>
                        )}
                      </section>
                    </div>
                  )}

                  {diffs.length > 0 && (
                    <div className="mt-3 space-y-2 text-sm">
                      <h4 className="font-medium">Diff</h4>
                      {diffs.slice(0, 2).map((item, index) => (
                        <div key={`${item.section}-${index}`} className="bg-secondary/30 rounded-md p-3">
                          <p className="font-medium">{item.section}</p>
                          <p className="text-muted-foreground">Before: {formatValue(item.before)}</p>
                          <p className="text-muted-foreground">After: {formatValue(item.after)}</p>
                        </div>
                      ))}
                    </div>
                  )}
                </li>
              );
            })}
          </ul>
        )}
      </CardContent>
    </Card>
  );
}