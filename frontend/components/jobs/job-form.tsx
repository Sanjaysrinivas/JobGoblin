"use client";

import * as React from "react";

import type {
  Job,
  JobCreatePayload,
  JobSource,
  Priority,
  WorkMode,
} from "@/lib/types";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

const workModes: { value: WorkMode; label: string }[] = [
  { value: "unknown", label: "Unknown" },
  { value: "remote", label: "Remote" },
  { value: "hybrid", label: "Hybrid" },
  { value: "onsite", label: "On-site" },
];

const sources: { value: JobSource; label: string }[] = [
  { value: "other", label: "Other" },
  { value: "linkedin", label: "LinkedIn" },
  { value: "company_site", label: "Company site" },
  { value: "indeed", label: "Indeed" },
  { value: "referral", label: "Referral" },
  { value: "recruiter", label: "Recruiter" },
];

const priorities: { value: Priority; label: string }[] = [
  { value: "low", label: "Low" },
  { value: "medium", label: "Medium" },
  { value: "high", label: "High" },
];

type FormState = {
  company_name: string;
  title: string;
  location: string;
  work_mode: WorkMode;
  source: JobSource;
  source_url: string;
  description: string;
  salary_min: string;
  salary_max: string;
  currency: string;
  priority: Priority;
};

interface JobFormProps {
  job?: Job;
  submitLabel: string;
  disabled?: boolean;
  onSubmit: (payload: JobCreatePayload) => Promise<void> | void;
  onCancel?: () => void;
}

function toState(job?: Job): FormState {
  return {
    company_name: job?.company_name ?? "",
    title: job?.title ?? "",
    location: job?.location ?? "",
    work_mode: job?.work_mode ?? "unknown",
    source: job?.source ?? "other",
    source_url: job?.source_url ?? "",
    description: job?.description ?? "",
    salary_min: job?.salary_min?.toString() ?? "",
    salary_max: job?.salary_max?.toString() ?? "",
    currency: job?.currency ?? "",
    priority: job?.priority ?? "medium",
  };
}

function clean(value: string): string | null {
  const trimmed = value.trim();
  return trimmed.length > 0 ? trimmed : null;
}

function numberOrNull(value: string): number | null {
  const trimmed = value.trim();
  if (!trimmed) return null;
  const parsed = Number.parseInt(trimmed, 10);
  return Number.isFinite(parsed) ? parsed : null;
}

function toPayload(state: FormState): JobCreatePayload {
  return {
    company_name: state.company_name.trim(),
    title: state.title.trim(),
    location: clean(state.location),
    work_mode: state.work_mode,
    source: state.source,
    source_url: clean(state.source_url),
    description: state.description.trim(),
    salary_min: numberOrNull(state.salary_min),
    salary_max: numberOrNull(state.salary_max),
    currency: clean(state.currency)?.toUpperCase() ?? null,
    priority: state.priority,
  };
}

export function JobForm({
  job,
  submitLabel,
  disabled = false,
  onSubmit,
  onCancel,
}: JobFormProps) {
  const [state, setState] = React.useState<FormState>(() => toState(job));

  const payload = toPayload(state);
  const isSalaryRangeInvalid =
    typeof payload.salary_min === "number" &&
    typeof payload.salary_max === "number" &&
    payload.salary_min > payload.salary_max;
  const canSubmit =
    payload.company_name.length > 0 &&
    payload.title.length > 0 &&
    payload.description.length > 0 &&
    !isSalaryRangeInvalid;

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
          <Label htmlFor="job-title">Role title</Label>
          <Input
            id="job-title"
            value={state.title}
            onChange={(e) => update("title", e.target.value)}
            disabled={disabled}
            placeholder="Senior Frontend Engineer"
            required
          />
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="job-company">Company</Label>
          <Input
            id="job-company"
            value={state.company_name}
            onChange={(e) => update("company_name", e.target.value)}
            disabled={disabled}
            placeholder="Acme"
            required
          />
        </div>
      </div>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        <div className="space-y-1.5">
          <Label htmlFor="job-location">Location</Label>
          <Input
            id="job-location"
            value={state.location}
            onChange={(e) => update("location", e.target.value)}
            disabled={disabled}
            placeholder="Berlin, DE"
          />
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="job-work-mode">Work mode</Label>
          <select
            id="job-work-mode"
            value={state.work_mode}
            onChange={(e) => update("work_mode", e.target.value as WorkMode)}
            disabled={disabled}
            className="border-input bg-card focus-visible:border-ring focus-visible:ring-ring/40 h-9 w-full rounded-md border px-3 py-1 text-sm shadow-xs outline-none focus-visible:ring-[3px] disabled:opacity-50"
          >
            {workModes.map((mode) => (
              <option key={mode.value} value={mode.value}>
                {mode.label}
              </option>
            ))}
          </select>
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="job-priority">Priority</Label>
          <select
            id="job-priority"
            value={state.priority}
            onChange={(e) => update("priority", e.target.value as Priority)}
            disabled={disabled}
            className="border-input bg-card focus-visible:border-ring focus-visible:ring-ring/40 h-9 w-full rounded-md border px-3 py-1 text-sm shadow-xs outline-none focus-visible:ring-[3px] disabled:opacity-50"
          >
            {priorities.map((priority) => (
              <option key={priority.value} value={priority.value}>
                {priority.label}
              </option>
            ))}
          </select>
        </div>
      </div>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        <div className="space-y-1.5">
          <Label htmlFor="job-source">Source</Label>
          <select
            id="job-source"
            value={state.source}
            onChange={(e) => update("source", e.target.value as JobSource)}
            disabled={disabled}
            className="border-input bg-card focus-visible:border-ring focus-visible:ring-ring/40 h-9 w-full rounded-md border px-3 py-1 text-sm shadow-xs outline-none focus-visible:ring-[3px] disabled:opacity-50"
          >
            {sources.map((source) => (
              <option key={source.value} value={source.value}>
                {source.label}
              </option>
            ))}
          </select>
        </div>
        <div className="space-y-1.5 sm:col-span-2">
          <Label htmlFor="job-source-url">Source URL</Label>
          <Input
            id="job-source-url"
            type="url"
            value={state.source_url}
            onChange={(e) => update("source_url", e.target.value)}
            disabled={disabled}
            placeholder="https://..."
          />
        </div>
      </div>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        <div className="space-y-1.5">
          <Label htmlFor="job-salary-min">Salary min</Label>
          <Input
            id="job-salary-min"
            type="number"
            min="0"
            step="1"
            value={state.salary_min}
            onChange={(e) => update("salary_min", e.target.value)}
            disabled={disabled}
          />
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="job-salary-max">Salary max</Label>
          <Input
            id="job-salary-max"
            type="number"
            min="0"
            step="1"
            value={state.salary_max}
            onChange={(e) => update("salary_max", e.target.value)}
            disabled={disabled}
          />
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="job-currency">Currency</Label>
          <Input
            id="job-currency"
            value={state.currency}
            onChange={(e) => update("currency", e.target.value)}
            disabled={disabled}
            placeholder="USD"
            maxLength={3}
          />
        </div>
      </div>

      {isSalaryRangeInvalid && (
        <p className="text-destructive text-sm">
          Salary minimum must be less than or equal to salary maximum.
        </p>
      )}

      <div className="space-y-1.5">
        <Label htmlFor="job-description">Job description</Label>
        <textarea
          id="job-description"
          value={state.description}
          onChange={(e) => update("description", e.target.value)}
          disabled={disabled}
          rows={12}
          required
          placeholder="Paste the full job description here."
          className="border-input bg-card focus-visible:border-ring focus-visible:ring-ring/40 w-full rounded-md border px-3 py-2 text-sm shadow-xs outline-none focus-visible:ring-[3px] disabled:opacity-50"
        />
      </div>

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
