"use client";

import * as React from "react";
import { useRouter } from "next/navigation";
import {
  ArrowLeft,
  Download,
  Loader2,
  RefreshCw,
  Save,
  Star,
  Trash2,
} from "lucide-react";

import { ApiError } from "@/lib/api";
import {
  deleteResume,
  fetchResumePdf,
  getResume,
  reparseResume,
  updateResume,
  type ResumeDetail,
} from "@/lib/resumes";
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
import { ParsedSections } from "@/components/resumes/parsed-sections";

type Busy = "save" | "parse" | "default" | "delete" | "export" | null;

export function ResumeDetailView({ resumeId }: { resumeId: string }) {
  const router = useRouter();
  const [resume, setResume] = React.useState<ResumeDetail | null>(null);
  const [loadError, setLoadError] = React.useState<string | null>(null);
  const [actionError, setActionError] = React.useState<string | null>(null);
  const [busy, setBusy] = React.useState<Busy>(null);

  // Editable fields.
  const [title, setTitle] = React.useState("");
  const [text, setText] = React.useState("");

  React.useEffect(() => {
    let active = true;
    (async () => {
      try {
        const data = await getResume(resumeId);
        if (!active) return;
        setResume(data);
        setTitle(data.title);
        setText(data.extracted_text ?? "");
      } catch (err) {
        if (!active) return;
        setLoadError(
          err instanceof ApiError && err.status === 404
            ? "Resume not found."
            : "Could not load this resume."
        );
      }
    })();
    return () => {
      active = false;
    };
  }, [resumeId]);

  function applyUpdate(updated: ResumeDetail) {
    setResume(updated);
    setTitle(updated.title);
    setText(updated.extracted_text ?? "");
  }

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

  const dirty =
    resume !== null &&
    (title !== resume.title || text !== (resume.extracted_text ?? ""));

  function onSave() {
    return run("save", async () => {
      const updated = await updateResume(resumeId, {
        title,
        extracted_text: text,
      });
      applyUpdate(updated);
    });
  }

  function onReparse() {
    return run("parse", async () => {
      applyUpdate(await reparseResume(resumeId));
    });
  }

  function onToggleDefault() {
    return run("default", async () => {
      applyUpdate(
        await updateResume(resumeId, { is_default: !resume!.is_default })
      );
    });
  }

  function onDelete() {
    return run("delete", async () => {
      await deleteResume(resumeId);
      router.push("/resumes");
      router.refresh();
    });
  }

  function onExport() {
    return run("export", async () => {
      const blob = await fetchResumePdf(resumeId);
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `${resume?.title || "resume"}.pdf`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
    });
  }

  if (loadError) {
    return (
      <div className="space-y-4">
        <Button variant="ghost" size="sm" onClick={() => router.push("/resumes")}>
          <ArrowLeft className="size-4" />
          Back to resumes
        </Button>
        <p role="alert" className="bg-destructive/10 text-destructive rounded-md px-3 py-2 text-sm">
          {loadError}
        </p>
      </div>
    );
  }

  if (!resume) {
    return (
      <div className="text-muted-foreground flex items-center gap-2 text-sm">
        <Loader2 className="size-4 animate-spin" />
        Loading resume…
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div className="space-y-1">
          <Button
            variant="ghost"
            size="sm"
            className="-ml-2"
            onClick={() => router.push("/resumes")}
          >
            <ArrowLeft className="size-4" />
            Resumes
          </Button>
          <h1 className="font-display flex items-center gap-2 text-2xl font-semibold tracking-tight">
            {resume.title}
            {resume.is_default && (
              <Badge variant="success">
                <Star className="size-3" />
                Default
              </Badge>
            )}
          </h1>
          <p className="text-muted-foreground text-sm">
            {resume.original_filename}
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={onToggleDefault}
            disabled={busy !== null}
          >
            {busy === "default" ? (
              <Loader2 className="size-4 animate-spin" />
            ) : (
              <Star className="size-4" />
            )}
            {resume.is_default ? "Unset default" : "Set default"}
          </Button>
          <Button
            variant="outline"
            size="sm"
            onClick={onExport}
            disabled={busy !== null}
          >
            {busy === "export" ? (
              <Loader2 className="size-4 animate-spin" />
            ) : (
              <Download className="size-4" />
            )}
            Export PDF
          </Button>
          <Button
            variant="outline"
            size="sm"
            onClick={onDelete}
            disabled={busy !== null}
          >
            {busy === "delete" ? (
              <Loader2 className="size-4 animate-spin" />
            ) : (
              <Trash2 className="size-4" />
            )}
            Delete
          </Button>
        </div>
      </div>

      {actionError && (
        <p role="alert" className="bg-destructive/10 text-destructive rounded-md px-3 py-2 text-sm">
          {actionError}
        </p>
      )}

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-5">
        {/* Edit panel */}
        <Card className="lg:col-span-2">
          <CardHeader>
            <CardTitle className="text-base">Source</CardTitle>
            <CardDescription>
              Edit the title or extracted text, then re-parse to refresh sections.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-1.5">
              <Label htmlFor="title">Title</Label>
              <Input
                id="title"
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                disabled={busy !== null}
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="extracted">Extracted text</Label>
              <textarea
                id="extracted"
                value={text}
                onChange={(e) => setText(e.target.value)}
                disabled={busy !== null}
                rows={14}
                className="border-input bg-card focus-visible:border-ring focus-visible:ring-ring/40 w-full rounded-md border px-3 py-2 font-mono text-xs shadow-xs outline-none focus-visible:ring-[3px] disabled:opacity-50"
              />
            </div>
            <div className="flex flex-wrap gap-2">
              <Button onClick={onSave} disabled={busy !== null || !dirty} size="sm">
                {busy === "save" ? (
                  <Loader2 className="size-4 animate-spin" />
                ) : (
                  <Save className="size-4" />
                )}
                Save changes
              </Button>
              <Button
                variant="secondary"
                size="sm"
                onClick={onReparse}
                disabled={busy !== null}
              >
                {busy === "parse" ? (
                  <Loader2 className="size-4 animate-spin" />
                ) : (
                  <RefreshCw className="size-4" />
                )}
                Re-parse
              </Button>
            </div>
          </CardContent>
        </Card>

        {/* Parsed sections */}
        <div className="lg:col-span-3">
          <ParsedSections parsed={resume.parsed_json} />
        </div>
      </div>
    </div>
  );
}
