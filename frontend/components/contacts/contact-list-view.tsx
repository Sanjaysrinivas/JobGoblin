"use client";

import * as React from "react";
import {
  Briefcase,
  Building2,
  CheckCircle2,
  Circle,
  ExternalLink,
  Link2,
  Loader2,
  Mail,
  Pencil,
  Plus,
  Trash2,
  UserRound,
} from "lucide-react";

import { ApiError } from "@/lib/api";
import {
  createContact,
  deleteContact,
  listContactJobs,
  listContacts,
  updateContact,
} from "@/lib/contacts";
import type { ContactJobOption } from "@/lib/contacts";
import type { Contact, ContactCreatePayload } from "@/lib/types";
import { EmptyState } from "@/components/empty-state";
import { PageHeader } from "@/components/page-header";
import { ContactForm } from "@/components/contacts/contact-form";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";

type Busy = "create" | `save:${string}` | `delete:${string}` | null;

function formatDate(value: string): string {
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
  }).format(new Date(value));
}

function jobLabel(jobs: ContactJobOption[], jobId: string | null): string | null {
  if (!jobId) return null;
  const job = jobs.find((item) => item.id === jobId);
  return job ? `${job.title} at ${job.company_name}` : "Linked job";
}

function errorMessage(err: unknown, fallback: string): string {
  return err instanceof ApiError ? err.message || fallback : fallback;
}

export function ContactListView() {
  const [contacts, setContacts] = React.useState<Contact[] | null>(null);
  const [jobs, setJobs] = React.useState<ContactJobOption[]>([]);
  const [error, setError] = React.useState<string | null>(null);
  const [actionError, setActionError] = React.useState<string | null>(null);
  const [showCreate, setShowCreate] = React.useState(false);
  const [editingId, setEditingId] = React.useState<string | null>(null);
  const [confirmingDeleteId, setConfirmingDeleteId] = React.useState<
    string | null
  >(null);
  const [busy, setBusy] = React.useState<Busy>(null);

  React.useEffect(() => {
    let active = true;
    (async () => {
      try {
        const [contactData, jobData] = await Promise.all([
          listContacts(),
          listContactJobs(),
        ]);
        if (!active) return;
        setContacts(contactData);
        setJobs(jobData);
      } catch (err) {
        if (!active) return;
        setError(
          err instanceof ApiError && err.isUnauthorized
            ? "Please sign in to view your contacts."
            : "Could not load contacts. Is the backend running?"
        );
        setContacts([]);
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

  function onCreate(payload: ContactCreatePayload) {
    return run("create", async () => {
      const created = await createContact(payload);
      setContacts((prev) => [created, ...(prev ?? [])]);
      setShowCreate(false);
    });
  }

  function onSave(contactId: string, payload: ContactCreatePayload) {
    return run(`save:${contactId}`, async () => {
      const updated = await updateContact(contactId, payload);
      setContacts((prev) =>
        (prev ?? []).map((contact) =>
          contact.id === contactId ? updated : contact
        )
      );
      setEditingId(null);
    });
  }

  function onDelete(contactId: string) {
    return run(`delete:${contactId}`, async () => {
      await deleteContact(contactId);
      setContacts((prev) =>
        (prev ?? []).filter((contact) => contact.id !== contactId)
      );
      setConfirmingDeleteId(null);
    });
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="Contacts"
        description="Recruiters, hiring managers, and referrals behind your outreach."
        actions={
          <Button onClick={() => setShowCreate((open) => !open)}>
            <Plus className="size-4" />
            Add contact
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
            <CardTitle className="text-base">Add contact</CardTitle>
            <CardDescription>
              Store outreach context separately from applications and drafts.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <ContactForm
              jobs={jobs}
              submitLabel={busy === "create" ? "Saving..." : "Save contact"}
              disabled={busy !== null}
              onSubmit={onCreate}
              onCancel={() => setShowCreate(false)}
            />
          </CardContent>
        </Card>
      )}

      {contacts === null ? (
        <div className="text-muted-foreground flex items-center gap-2 text-sm">
          <Loader2 className="size-4 animate-spin" />
          Loading contacts...
        </div>
      ) : contacts.length === 0 ? (
        <EmptyState
          icon={UserRound}
          title="No contacts yet"
          description="Add recruiters and referrals so future outreach has the right context."
          action={
            <Button variant="outline" onClick={() => setShowCreate(true)}>
              <Plus className="size-4" />
              Add your first contact
            </Button>
          }
        />
      ) : (
        <ul className="grid grid-cols-1 gap-3">
          {contacts.map((contact) => {
            const relatedJob = jobLabel(jobs, contact.job_id);
            const isEditing = editingId === contact.id;
            const isDeleting = busy === `delete:${contact.id}`;
            return (
              <li key={contact.id}>
                <Card className="gap-0 py-5">
                  <CardContent className="space-y-4">
                    <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
                      <div className="min-w-0 space-y-2">
                        <div className="flex min-w-0 items-center gap-2">
                          <UserRound className="text-primary size-4 shrink-0" />
                          <span className="truncate font-medium">
                            {contact.name}
                          </span>
                          {contact.role && (
                            <span className="text-muted-foreground truncate text-sm">
                              {contact.role}
                            </span>
                          )}
                        </div>
                        <div className="text-muted-foreground flex flex-wrap items-center gap-x-3 gap-y-1 text-xs">
                          {contact.company && (
                            <span className="inline-flex items-center gap-1">
                              <Building2 className="size-3" />
                              {contact.company}
                            </span>
                          )}
                          {relatedJob && (
                            <span className="inline-flex items-center gap-1">
                              <Briefcase className="size-3" />
                              {relatedJob}
                            </span>
                          )}
                          {contact.email && (
                            <a
                              href={`mailto:${contact.email}`}
                              className="hover:text-foreground inline-flex items-center gap-1"
                            >
                              <Mail className="size-3" />
                              {contact.email}
                            </a>
                          )}
                          {contact.linkedin_url && (
                            <a
                              href={contact.linkedin_url}
                              target="_blank"
                              rel="noreferrer"
                              className="hover:text-foreground inline-flex items-center gap-1"
                            >
                              <Link2 className="size-3" />
                              LinkedIn
                              <ExternalLink className="size-3" />
                            </a>
                          )}
                        </div>
                      </div>

                      <div className="flex shrink-0 flex-wrap items-center gap-2">
                        <Badge variant={contact.contacted ? "info" : "outline"}>
                          {contact.contacted ? (
                            <CheckCircle2 className="size-3" />
                          ) : (
                            <Circle className="size-3" />
                          )}
                          {contact.contacted ? "Contacted" : "Not contacted"}
                        </Badge>
                        <Button
                          variant={isEditing ? "secondary" : "outline"}
                          size="sm"
                          onClick={() =>
                            setEditingId((value) =>
                              value === contact.id ? null : contact.id
                            )
                          }
                          disabled={busy !== null}
                        >
                          <Pencil className="size-4" />
                          Edit
                        </Button>
                        {confirmingDeleteId === contact.id ? (
                          <div className="flex items-center gap-2">
                            <span className="text-muted-foreground text-xs">
                              Delete?
                            </span>
                            <Button
                              variant="destructive"
                              size="sm"
                              onClick={() => onDelete(contact.id)}
                              disabled={busy !== null}
                            >
                              {isDeleting ? (
                                <Loader2 className="size-4 animate-spin" />
                              ) : (
                                <Trash2 className="size-4" />
                              )}
                              Confirm
                            </Button>
                            <Button
                              variant="ghost"
                              size="sm"
                              onClick={() => setConfirmingDeleteId(null)}
                              disabled={busy !== null}
                            >
                              Cancel
                            </Button>
                          </div>
                        ) : (
                          <Button
                            variant="outline"
                            size="sm"
                            onClick={() => setConfirmingDeleteId(contact.id)}
                            disabled={busy !== null}
                          >
                            <Trash2 className="size-4" />
                            Delete
                          </Button>
                        )}
                      </div>
                    </div>

                    {contact.notes && (
                      <p className="bg-secondary/35 text-muted-foreground whitespace-pre-wrap rounded-md p-3 text-sm">
                        {contact.notes}
                      </p>
                    )}

                    <p className="text-muted-foreground text-xs">
                      Added {formatDate(contact.created_at)}
                    </p>

                    {isEditing && (
                      <div className="border-t pt-4">
                        <ContactForm
                          contact={contact}
                          jobs={jobs}
                          submitLabel={
                            busy === `save:${contact.id}`
                              ? "Saving..."
                              : "Save changes"
                          }
                          disabled={busy !== null}
                          onSubmit={(payload) => onSave(contact.id, payload)}
                          onCancel={() => setEditingId(null)}
                        />
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
