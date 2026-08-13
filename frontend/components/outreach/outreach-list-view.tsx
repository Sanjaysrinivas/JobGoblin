"use client";

import * as React from "react";
import {
  Check,
  Clipboard,
  Download,
  Loader2,
  Mail,
  MessageSquareText,
  Plus,
  Save,
  Trash2,
} from "lucide-react";

import { ApiError } from "@/lib/api";
import { listContactJobs, listContacts } from "@/lib/contacts";
import type { ContactJobOption } from "@/lib/contacts";
import {
  createOutreach,
  generateOutreach,
  deleteOutreach,
  getOutreachEmailExport,
  listOutreach,
  updateOutreach,
  type OutreachDraft,
} from "@/lib/outreach";
import type { Contact, OutreachChannel, OutreachGeneratedType, OutreachStatus } from "@/lib/types";
import { EmptyState } from "@/components/empty-state";
import { PageHeader } from "@/components/page-header";
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

const channels: OutreachChannel[] = ["email", "linkedin", "other"];
const statuses: OutreachStatus[] = ["draft", "copied", "replied", "closed"];
const generatedMessageTypes: OutreachGeneratedType[] = [
  "recruiter_follow_up",
  "referral",
  "thank_you",
  "status_check",
];
const selectClass =
  "border-input bg-card focus-visible:border-ring focus-visible:ring-ring/40 h-9 w-full rounded-md border px-3 text-sm shadow-xs outline-none focus-visible:ring-[3px]";
const textareaClass =
  "border-input bg-card focus-visible:border-ring focus-visible:ring-ring/40 min-h-36 w-full rounded-md border px-3 py-2 text-sm shadow-xs outline-none focus-visible:ring-[3px]";

type DraftState = {
  jobId: string;
  contactId: string;
  channel: OutreachChannel;
  messageType: string;
  content: string;
  status: OutreachStatus;
};

type Busy =
  | "create"
  | "generate"
  | `save:${string}`
  | `copy:${string}`
  | `email-copy:${string}`
  | `email-open:${string}`
  | `email-download:${string}`
  | `delete:${string}`
  | null;

function label(value: string): string {
  return value
    .split("_")
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

function errorMessage(err: unknown, fallback: string): string {
  return err instanceof ApiError ? err.message || fallback : fallback;
}

function draftFromOutreach(outreach: OutreachDraft): DraftState {
  return {
    jobId: outreach.job_id ?? "",
    contactId: outreach.contact_id ?? "",
    channel: outreach.channel,
    messageType: outreach.message_type,
    content: outreach.content,
    status: outreach.status,
  };
}

function toPayload(draft: DraftState) {
  return {
    job_id: draft.jobId || null,
    contact_id: draft.contactId || null,
    channel: draft.channel,
    message_type: draft.messageType,
    content: draft.content,
    status: draft.status,
  };
}

function jobLabel(jobs: ContactJobOption[], jobId: string | null): string {
  if (!jobId) return "No job linked";
  const job = jobs.find((item) => item.id === jobId);
  return job ? `${job.title} at ${job.company_name}` : "Linked job";
}

function contactLabel(contacts: Contact[], contactId: string | null): string {
  if (!contactId) return "No contact linked";
  return contacts.find((item) => item.id === contactId)?.name ?? "Linked contact";
}

function statusVariant(
  status: OutreachStatus
): "info" | "success" | "outline" | "default" {
  if (status === "copied") return "success";
  if (status === "draft") return "info";
  if (status === "closed") return "outline";
  return "default";
}

export function OutreachListView() {
  const [outreach, setOutreach] = React.useState<OutreachDraft[] | null>(null);
  const [jobs, setJobs] = React.useState<ContactJobOption[]>([]);
  const [contacts, setContacts] = React.useState<Contact[]>([]);
  const [drafts, setDrafts] = React.useState<Record<string, DraftState>>({});
  const [showCreate, setShowCreate] = React.useState(false);
  const [newDraft, setNewDraft] = React.useState<DraftState>({
    jobId: "",
    contactId: "",
    channel: "email",
    messageType: "recruiter_follow_up",
    content: "",
    status: "draft",
  });
  const [busy, setBusy] = React.useState<Busy>(null);
  const [error, setError] = React.useState<string | null>(null);
  const [actionError, setActionError] = React.useState<string | null>(null);

  React.useEffect(() => {
    let active = true;
    (async () => {
      try {
        const [outreachData, jobData, contactData] = await Promise.all([
          listOutreach(),
          listContactJobs(),
          listContacts(),
        ]);
        if (!active) return;
        setOutreach(outreachData);
        setJobs(jobData);
        setContacts(contactData);
        setDrafts(
          Object.fromEntries(
            outreachData.map((item) => [item.id, draftFromOutreach(item)])
          )
        );
      } catch (err) {
        if (!active) return;
        setError(
          err instanceof ApiError && err.isUnauthorized
            ? "Please sign in to view outreach drafts."
            : "Could not load outreach drafts. Is the backend running?"
        );
        setOutreach([]);
      }
    })();
    return () => {
      active = false;
    };
  }, []);

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

  function onCreate(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    return run("create", async () => {
      const created = await createOutreach(toPayload(newDraft));
      setOutreach((current) => [created, ...(current ?? [])]);
      setDrafts((current) => ({
        ...current,
        [created.id]: draftFromOutreach(created),
      }));
      setNewDraft({
        jobId: "",
        contactId: "",
        channel: "email",
        messageType: "recruiter_follow_up",
        content: "",
        status: "draft",
      });
      setShowCreate(false);
    });
  }

  function onGenerateDraft() {
    return run("generate", async () => {
      if (!generatedMessageTypes.includes(newDraft.messageType as OutreachGeneratedType)) {
        throw new Error("Choose recruiter_follow_up, referral, thank_you, or status_check to generate.");
      }
      const created = await generateOutreach({
        job_id: newDraft.jobId || null,
        contact_id: newDraft.contactId || null,
        channel: newDraft.channel,
        message_type: newDraft.messageType as OutreachGeneratedType,
        notes: newDraft.content || null,
      });
      setOutreach((current) => [created, ...(current ?? [])]);
      setDrafts((current) => ({
        ...current,
        [created.id]: draftFromOutreach(created),
      }));
      setNewDraft({
        jobId: "",
        contactId: "",
        channel: "email",
        messageType: "recruiter_follow_up",
        content: "",
        status: "draft",
      });
      setShowCreate(false);
    });
  }
  function onSave(item: OutreachDraft) {
    return run(`save:${item.id}`, async () => {
      const updated = await updateOutreach(item.id, toPayload(drafts[item.id]));
      setOutreach((current) =>
        (current ?? []).map((entry) => (entry.id === updated.id ? updated : entry))
      );
      setDrafts((current) => ({
        ...current,
        [updated.id]: draftFromOutreach(updated),
      }));
    });
  }

  function onRecordCopy(item: OutreachDraft) {
    return run(`copy:${item.id}`, async () => {
      const draft = drafts[item.id] ?? draftFromOutreach(item);
      if (!navigator.clipboard?.writeText) {
        throw new Error("Clipboard API is not supported in this browser or context.");
      }
      await navigator.clipboard.writeText(draft.content);
      const updated = await updateOutreach(item.id, {
        ...toPayload(draft),
        status: "copied",
      });
      setOutreach((current) =>
        (current ?? []).map((entry) => (entry.id === updated.id ? updated : entry))
      );
      setDrafts((current) => ({
        ...current,
        [updated.id]: draftFromOutreach(updated),
      }));
    });
  }

  function onDelete(item: OutreachDraft) {
    return run(`delete:${item.id}`, async () => {
      await deleteOutreach(item.id);
      setOutreach((current) => (current ?? []).filter((entry) => entry.id !== item.id));
      setDrafts((current) => {
        const next = { ...current };
        delete next[item.id];
        return next;
      });
    });
  }

  function onCopyEmailExport(item: OutreachDraft) {
    return run(`email-copy:${item.id}`, async () => {
      if (!navigator.clipboard?.writeText) {
        throw new Error("Clipboard API is not supported in this browser or context.");
      }
      const email = await getOutreachEmailExport(item.id, "copy");
      await navigator.clipboard.writeText(email.text || `${email.subject}\n\n${email.body}`);
    });
  }

  function onOpenEmailClient(item: OutreachDraft) {
    return run(`email-open:${item.id}`, async () => {
      const email = await getOutreachEmailExport(item.id, "open");
      window.location.href = email.mailto_url;
    });
  }

  function onDownloadEmailExport(item: OutreachDraft) {
    return run(`email-download:${item.id}`, async () => {
      const email = await getOutreachEmailExport(item.id, "download");
      const blob = new Blob([email.text || `${email.subject}\n\n${email.body}`], {
        type: "text/plain;charset=utf-8",
      });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = email.filename || "email-draft.txt";
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
    });
  }
  function renderDraftFields(
    draft: DraftState,
    onChange: (changes: Partial<DraftState>) => void,
    disabled: boolean,
    prefix: string
  ) {
    return (
      <div className="grid gap-3 md:grid-cols-2">
        <div className="space-y-1.5">
          <Label htmlFor={`${prefix}-job`}>Job</Label>
          <select
            id={`${prefix}-job`}
            className={selectClass}
            value={draft.jobId}
            disabled={disabled}
            onChange={(event) => onChange({ jobId: event.target.value })}
          >
            <option value="">No job linked</option>
            {jobs.map((job) => (
              <option key={job.id} value={job.id}>
                {job.title} at {job.company_name}
              </option>
            ))}
          </select>
        </div>
        <div className="space-y-1.5">
          <Label htmlFor={`${prefix}-contact`}>Contact</Label>
          <select
            id={`${prefix}-contact`}
            className={selectClass}
            value={draft.contactId}
            disabled={disabled}
            onChange={(event) => onChange({ contactId: event.target.value })}
          >
            <option value="">No contact linked</option>
            {contacts.map((contact) => (
              <option key={contact.id} value={contact.id}>
                {contact.name}
              </option>
            ))}
          </select>
        </div>
        <div className="space-y-1.5">
          <Label htmlFor={`${prefix}-channel`}>Channel</Label>
          <select
            id={`${prefix}-channel`}
            className={selectClass}
            value={draft.channel}
            disabled={disabled}
            onChange={(event) =>
              onChange({ channel: event.target.value as OutreachChannel })
            }
          >
            {channels.map((channel) => (
              <option key={channel} value={channel}>
                {label(channel)}
              </option>
            ))}
          </select>
        </div>
        <div className="space-y-1.5">
          <Label htmlFor={`${prefix}-status`}>Status</Label>
          <select
            id={`${prefix}-status`}
            className={selectClass}
            value={draft.status}
            disabled={disabled}
            onChange={(event) =>
              onChange({ status: event.target.value as OutreachStatus })
            }
          >
            {statuses.map((status) => (
              <option key={status} value={status}>
                {label(status)}
              </option>
            ))}
          </select>
        </div>
        <div className="space-y-1.5 md:col-span-2">
          <Label htmlFor={`${prefix}-type`}>Draft type</Label>
          <Input
            id={`${prefix}-type`}
            value={draft.messageType}
            disabled={disabled}
            onChange={(event) => onChange({ messageType: event.target.value })}
            placeholder="recruiter_intro"
          />
        </div>
        <div className="space-y-1.5 md:col-span-2">
          <Label htmlFor={`${prefix}-content`}>Message draft</Label>
          <textarea
            id={`${prefix}-content`}
            className={textareaClass}
            value={draft.content}
            disabled={disabled}
            onChange={(event) => onChange({ content: event.target.value })}
            placeholder="Write a manual message, or add notes before generating a supported draft."
          />
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="Outreach"
        description="Review local email and LinkedIn drafts before copying them yourself."
        actions={
          <Button onClick={() => setShowCreate((open) => !open)}>
            <Plus className="size-4" />
            New draft
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
      {actionError && (
        <p
          role="alert"
          className="bg-destructive/10 text-destructive rounded-md px-3 py-2 text-sm"
        >
          {actionError}
        </p>
      )}

      {showCreate && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Create outreach draft</CardTitle>
            <CardDescription>
              Drafts stay local to JobGoblin until you copy them.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <form className="space-y-4" onSubmit={onCreate}>
              {renderDraftFields(
                newDraft,
                (changes) => setNewDraft((current) => ({ ...current, ...changes })),
                busy !== null,
                "new-outreach"
              )}
              <div className="flex justify-end gap-2">
                <Button
                  type="button"
                  variant="outline"
                  onClick={() => setShowCreate(false)}
                  disabled={busy !== null}
                >
                  Cancel
                </Button>
                <Button
                  type="button"
                  variant="outline"
                  onClick={onGenerateDraft}
                  disabled={busy !== null}
                >
                  {busy === "generate" && <Loader2 className="size-4 animate-spin" />}
                  Generate draft
                </Button>
                <Button type="submit" disabled={busy !== null}>
                  {busy === "create" && <Loader2 className="size-4 animate-spin" />}
                  Save draft
                </Button>
              </div>
            </form>
          </CardContent>
        </Card>
      )}

      {outreach === null ? (
        <div className="text-muted-foreground flex items-center gap-2 text-sm">
          <Loader2 className="size-4 animate-spin" />
          Loading outreach drafts...
        </div>
      ) : outreach.length === 0 ? (
        <EmptyState
          icon={MessageSquareText}
          title="No outreach drafts"
          description="Create a draft tied to a job or contact, then review it before copying."
          action={
            <Button variant="outline" onClick={() => setShowCreate(true)}>
              <Plus className="size-4" />
              Create draft
            </Button>
          }
        />
      ) : (
        <ul className="grid grid-cols-1 gap-4">
          {outreach.map((item) => {
            const draft = drafts[item.id] ?? draftFromOutreach(item);
            const saving = busy === `save:${item.id}`;
            const copying = busy === `copy:${item.id}`;
            const copyingEmail = busy === `email-copy:${item.id}`;
            const openingEmail = busy === `email-open:${item.id}`;
            const downloadingEmail = busy === `email-download:${item.id}`;
            const deleting = busy === `delete:${item.id}`;
            const disabled = busy !== null;
            const isEmail = draft.channel === "email";
            return (
              <li key={item.id}>
                <Card className="gap-0 py-5">
                  <CardContent className="space-y-4">
                    <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
                      <div className="min-w-0 space-y-2">
                        <div className="flex flex-wrap items-center gap-2">
                          <span className="font-medium">
                            {label(item.message_type)}
                          </span>
                          <Badge variant={statusVariant(item.status)}>
                            {item.status === "copied" && <Check className="size-3" />}
                            {label(item.status)}
                          </Badge>
                          <Badge variant="outline">{label(item.channel)}</Badge>
                        </div>
                        <p className="text-muted-foreground text-sm">
                          {jobLabel(jobs, item.job_id)} |{" "}
                          {contactLabel(contacts, item.contact_id)}
                        </p>
                      </div>
                      <div className="flex shrink-0 flex-wrap items-center gap-2">
                        <Button
                          type="button"
                          variant="outline"
                          size="sm"
                          onClick={() => onRecordCopy(item)}
                          disabled={disabled}
                        >
                          {copying ? (
                            <Loader2 className="size-4 animate-spin" />
                          ) : (
                            <Clipboard className="size-4" />
                          )}
                          Copy
                        </Button>
                        {isEmail && (
                          <>
                            <Button
                              type="button"
                              variant="outline"
                              size="sm"
                              onClick={() => onCopyEmailExport(item)}
                              disabled={disabled}
                            >
                              {copyingEmail ? (
                                <Loader2 className="size-4 animate-spin" />
                              ) : (
                                <Clipboard className="size-4" />
                              )}
                              Copy email
                            </Button>
                            <Button
                              type="button"
                              variant="outline"
                              size="sm"
                              onClick={() => onOpenEmailClient(item)}
                              disabled={disabled}
                            >
                              {openingEmail ? (
                                <Loader2 className="size-4 animate-spin" />
                              ) : (
                                <Mail className="size-4" />
                              )}
                              Mailto
                            </Button>
                            <Button
                              type="button"
                              variant="outline"
                              size="sm"
                              onClick={() => onDownloadEmailExport(item)}
                              disabled={disabled}
                            >
                              {downloadingEmail ? (
                                <Loader2 className="size-4 animate-spin" />
                              ) : (
                                <Download className="size-4" />
                              )}
                              .txt
                            </Button>
                          </>
                        )}
                        <Button
                          type="button"
                          variant="outline"
                          size="sm"
                          onClick={() => onDelete(item)}
                          disabled={disabled}
                        >
                          {deleting ? (
                            <Loader2 className="size-4 animate-spin" />
                          ) : (
                            <Trash2 className="size-4" />
                          )}
                          Delete
                        </Button>
                      </div>
                    </div>

                    {renderDraftFields(
                      draft,
                      (changes) => updateDraft(item.id, changes),
                      disabled,
                      `outreach-${item.id}`
                    )}

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