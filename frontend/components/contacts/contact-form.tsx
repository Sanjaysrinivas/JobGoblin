"use client";

import * as React from "react";

import type { ContactJobOption } from "@/lib/contacts";
import type { Contact, ContactCreatePayload } from "@/lib/types";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

type FormState = {
  job_id: string;
  name: string;
  company: string;
  role: string;
  email: string;
  linkedin_url: string;
  notes: string;
  contacted: boolean;
};

interface ContactFormProps {
  contact?: Contact;
  jobs: ContactJobOption[];
  submitLabel: string;
  disabled?: boolean;
  onSubmit: (payload: ContactCreatePayload) => Promise<void> | void;
  onCancel?: () => void;
}

function toState(contact?: Contact): FormState {
  return {
    job_id: contact?.job_id ?? "",
    name: contact?.name ?? "",
    company: contact?.company ?? "",
    role: contact?.role ?? "",
    email: contact?.email ?? "",
    linkedin_url: contact?.linkedin_url ?? "",
    notes: contact?.notes ?? "",
    contacted: contact?.contacted ?? false,
  };
}

function clean(value: string): string | null {
  const trimmed = value.trim();
  return trimmed.length > 0 ? trimmed : null;
}

function toPayload(state: FormState): ContactCreatePayload {
  return {
    job_id: clean(state.job_id),
    name: state.name.trim(),
    company: clean(state.company),
    role: clean(state.role),
    email: clean(state.email),
    linkedin_url: clean(state.linkedin_url),
    notes: clean(state.notes),
    contacted: state.contacted,
  };
}

export function ContactForm({
  contact,
  jobs,
  submitLabel,
  disabled = false,
  onSubmit,
  onCancel,
}: ContactFormProps) {
  const id = React.useId();
  const [state, setState] = React.useState<FormState>(() => toState(contact));

  const payload = toPayload(state);
  const canSubmit = payload.name.length > 0;

  function update<K extends keyof FormState>(key: K, value: FormState[K]) {
    setState((prev) => ({ ...prev, [key]: value }));
  }

  async function handleSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    if (!canSubmit || disabled) return;
    await onSubmit(payload);
  }

  return (
    <form className="space-y-5" onSubmit={handleSubmit}>
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        <div className="space-y-1.5">
          <Label htmlFor={`${id}-name`}>Name</Label>
          <Input
            id={`${id}-name`}
            value={state.name}
            onChange={(e) => update("name", e.target.value)}
            disabled={disabled}
            placeholder="Taylor Recruiter"
            required
          />
        </div>
        <div className="space-y-1.5">
          <Label htmlFor={`${id}-company`}>Company</Label>
          <Input
            id={`${id}-company`}
            value={state.company}
            onChange={(e) => update("company", e.target.value)}
            disabled={disabled}
            placeholder="Acme"
          />
        </div>
      </div>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        <div className="space-y-1.5">
          <Label htmlFor={`${id}-role`}>Role</Label>
          <Input
            id={`${id}-role`}
            value={state.role}
            onChange={(e) => update("role", e.target.value)}
            disabled={disabled}
            placeholder="Technical recruiter"
          />
        </div>
        <div className="space-y-1.5">
          <Label htmlFor={`${id}-job`}>Related job</Label>
          <select
            id={`${id}-job`}
            value={state.job_id}
            onChange={(e) => update("job_id", e.target.value)}
            disabled={disabled}
            className="border-input bg-card focus-visible:border-ring focus-visible:ring-ring/40 h-9 w-full rounded-md border px-3 py-1 text-sm shadow-xs outline-none focus-visible:ring-[3px] disabled:opacity-50"
          >
            <option value="">No linked job</option>
            {jobs.map((job) => (
              <option key={job.id} value={job.id}>
                {job.title} at {job.company_name}
              </option>
            ))}
          </select>
        </div>
      </div>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        <div className="space-y-1.5">
          <Label htmlFor={`${id}-email`}>Email</Label>
          <Input
            id={`${id}-email`}
            type="email"
            value={state.email}
            onChange={(e) => update("email", e.target.value)}
            disabled={disabled}
            placeholder="taylor@example.com"
          />
        </div>
        <div className="space-y-1.5">
          <Label htmlFor={`${id}-linkedin`}>LinkedIn URL</Label>
          <Input
            id={`${id}-linkedin`}
            type="url"
            value={state.linkedin_url}
            onChange={(e) => update("linkedin_url", e.target.value)}
            disabled={disabled}
            placeholder="https://www.linkedin.com/in/..."
          />
        </div>
      </div>

      <div className="space-y-1.5">
        <Label htmlFor={`${id}-notes`}>Notes</Label>
        <textarea
          id={`${id}-notes`}
          value={state.notes}
          onChange={(e) => update("notes", e.target.value)}
          disabled={disabled}
          rows={5}
          placeholder="Referral source, prior conversation, or follow-up context."
          className="border-input bg-card focus-visible:border-ring focus-visible:ring-ring/40 w-full rounded-md border px-3 py-2 text-sm shadow-xs outline-none focus-visible:ring-[3px] disabled:opacity-50"
        />
      </div>

      <label className="flex items-center gap-2 text-sm">
        <input
          type="checkbox"
          checked={state.contacted}
          onChange={(e) => update("contacted", e.target.checked)}
          disabled={disabled}
          className="border-input size-4 rounded"
        />
        Contacted
      </label>

      <div className="flex flex-wrap items-center gap-2">
        <Button type="submit" disabled={disabled || !canSubmit}>
          {submitLabel}
        </Button>
        {onCancel && (
          <Button
            type="button"
            variant="ghost"
            disabled={disabled}
            onClick={onCancel}
          >
            Cancel
          </Button>
        )}
      </div>
    </form>
  );
}
