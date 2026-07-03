"use client";

import * as React from "react";
import {
  BookmarkPlus,
  ExternalLink,
  Loader2,
  MapPin,
  Search,
  XCircle,
} from "lucide-react";

import { ApiError } from "@/lib/api";
import {
  createDiscoveryRun,
  getDiscoveryPreferences,
  listDiscoveryResults,
  saveDiscoveryPreferences,
  saveDiscoveryResult,
  updateDiscoveryResult,
} from "@/lib/discovery";
import type {
  JobSearchPreferences,
  JobSearchPreferencesPayload,
  JobSearchResult,
  WorkMode,
} from "@/lib/types";
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

type FormState = {
  country: string;
  location: string;
  titles: string;
  requiredKeywords: string;
  optionalKeywords: string;
  excludedKeywords: string;
  blockedCompanies: string;
  visaSponsorshipRequired: boolean;
  workMode: WorkMode;
};

const defaultState: FormState = {
  country: "us",
  location: "",
  titles: "",
  requiredKeywords: "",
  optionalKeywords: "",
  excludedKeywords: "",
  blockedCompanies: "",
  visaSponsorshipRequired: false,
  workMode: "unknown",
};

const workModes: { value: WorkMode; label: string }[] = [
  { value: "unknown", label: "Any" },
  { value: "remote", label: "Remote" },
  { value: "hybrid", label: "Hybrid" },
  { value: "onsite", label: "On-site" },
];

function splitList(value: string): string[] {
  return value
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);
}

function joinList(value: string[] | undefined): string {
  return value?.join(", ") ?? "";
}

function fromPreferences(preferences: JobSearchPreferences | null): FormState {
  if (!preferences) return defaultState;
  return {
    country: preferences.target_countries[0] ?? defaultState.country,
    location: preferences.target_locations[0] ?? "",
    titles: joinList(preferences.desired_titles),
    requiredKeywords: joinList(preferences.required_keywords),
    optionalKeywords: joinList(preferences.optional_keywords),
    excludedKeywords: joinList(preferences.excluded_keywords),
    blockedCompanies: joinList(preferences.blocked_companies),
    visaSponsorshipRequired: preferences.visa_sponsorship_required,
    workMode: preferences.work_mode,
  };
}

function toPreferences(state: FormState): JobSearchPreferencesPayload {
  const country = state.country.trim().toLowerCase();
  const location = state.location.trim();
  return {
    target_countries: country ? [country] : [],
    target_locations: location ? [location] : [],
    desired_titles: splitList(state.titles),
    seniority: null,
    industries: [],
    required_keywords: splitList(state.requiredKeywords),
    optional_keywords: splitList(state.optionalKeywords),
    excluded_keywords: splitList(state.excludedKeywords),
    visa_sponsorship_required: state.visaSponsorshipRequired,
    blocked_companies: splitList(state.blockedCompanies),
    work_mode: state.workMode,
  };
}

function label(value: string): string {
  return value
    .split("_")
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

function scoreVariant(score: number): "success" | "warning" | "secondary" {
  if (score >= 75) return "success";
  if (score >= 50) return "warning";
  return "secondary";
}

function errorMessage(err: unknown, fallback: string): string {
  if (err instanceof ApiError) {
    if (err.isUnauthorized) return "Please sign in to use discovery.";
    return err.message || fallback;
  }
  return "Could not reach the server. Is the backend running?";
}

export function DiscoveryView() {
  const [form, setForm] = React.useState<FormState>(defaultState);
  const [results, setResults] = React.useState<JobSearchResult[] | null>(null);
  const [loading, setLoading] = React.useState(true);
  const [running, setRunning] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);
  const [runMessage, setRunMessage] = React.useState<string | null>(null);
  const [busyResultId, setBusyResultId] = React.useState<string | null>(null);

  React.useEffect(() => {
    let active = true;
    (async () => {
      try {
        const [preferences, loadedResults] = await Promise.all([
          getDiscoveryPreferences(),
          listDiscoveryResults(),
        ]);
        if (!active) return;
        setForm(fromPreferences(preferences));
        setResults(loadedResults);
      } catch (err) {
        if (!active) return;
        setError(errorMessage(err, "Could not load discovery."));
        setResults([]);
      } finally {
        if (active) setLoading(false);
      }
    })();
    return () => {
      active = false;
    };
  }, []);

  function update<K extends keyof FormState>(key: K, value: FormState[K]) {
    setForm((prev) => ({ ...prev, [key]: value }));
  }

  async function refreshResults() {
    setResults(await listDiscoveryResults());
  }

  async function runSearch(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const preferences = toPreferences(form);
    const country = preferences.target_countries[0] ?? "us";
    const location = preferences.target_locations[0] ?? null;
    setError(null);
    setRunMessage(null);
    setRunning(true);
    try {
      await saveDiscoveryPreferences(preferences);
      const run = await createDiscoveryRun({
        country,
        location,
        results_per_page: 10,
      });
      await refreshResults();
      setRunMessage(
        run.status === "failed"
          ? run.error || "Search failed."
          : `Found ${run.result_count} new result${run.result_count === 1 ? "" : "s"}.`
      );
    } catch (err) {
      setError(errorMessage(err, "Could not run discovery."));
    } finally {
      setRunning(false);
    }
  }

  async function saveResult(resultId: string) {
    setError(null);
    setBusyResultId(resultId);
    try {
      await saveDiscoveryResult(resultId);
      setResults((prev) => prev?.filter((item) => item.id !== resultId) ?? []);
    } catch (err) {
      setError(errorMessage(err, "Could not save this result."));
    } finally {
      setBusyResultId(null);
    }
  }

  async function dismissResult(resultId: string) {
    setError(null);
    setBusyResultId(resultId);
    try {
      await updateDiscoveryResult(resultId, "dismissed");
      setResults((prev) => prev?.filter((item) => item.id !== resultId) ?? []);
    } catch (err) {
      setError(errorMessage(err, "Could not dismiss this result."));
    } finally {
      setBusyResultId(null);
    }
  }

  const canSearch = form.country.trim().length === 2 && !running;

  return (
    <div className="space-y-6">
      <PageHeader
        title="Discover"
        description="Search for roles from your preferences, then save only the matches you want to track."
      />

      {error && (
        <p
          role="alert"
          className="bg-destructive/10 text-destructive rounded-md px-3 py-2 text-sm"
        >
          {error}
        </p>
      )}

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Search preferences</CardTitle>
          <CardDescription>
            Comma-separate titles or keywords. Country uses a two-letter code.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <form className="space-y-4" onSubmit={runSearch}>
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
              <div className="space-y-1.5">
                <Label htmlFor="discover-country">Target country</Label>
                <Input
                  id="discover-country"
                  value={form.country}
                  onChange={(e) => update("country", e.target.value)}
                  disabled={running}
                  maxLength={2}
                  placeholder="us"
                  required
                />
              </div>
              <div className="space-y-1.5 sm:col-span-2">
                <Label htmlFor="discover-location">Location</Label>
                <Input
                  id="discover-location"
                  value={form.location}
                  onChange={(e) => update("location", e.target.value)}
                  disabled={running}
                  placeholder="New York, NY"
                />
              </div>
            </div>

            <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
              <div className="space-y-1.5 sm:col-span-2">
                <Label htmlFor="discover-titles">Titles</Label>
                <Input
                  id="discover-titles"
                  value={form.titles}
                  onChange={(e) => update("titles", e.target.value)}
                  disabled={running}
                  placeholder="Frontend Engineer, Product Engineer"
                />
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="discover-work-mode">Work mode</Label>
                <select
                  id="discover-work-mode"
                  value={form.workMode}
                  onChange={(e) => update("workMode", e.target.value as WorkMode)}
                  disabled={running}
                  className="border-input bg-card focus-visible:border-ring focus-visible:ring-ring/40 h-9 w-full rounded-md border px-3 py-1 text-sm shadow-xs outline-none focus-visible:ring-[3px] disabled:opacity-50"
                >
                  {workModes.map((mode) => (
                    <option key={mode.value} value={mode.value}>
                      {mode.label}
                    </option>
                  ))}
                </select>
              </div>
            </div>

            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <div className="space-y-1.5">
                <Label htmlFor="discover-required-keywords">Keywords</Label>
                <Input
                  id="discover-required-keywords"
                  value={form.requiredKeywords}
                  onChange={(e) => update("requiredKeywords", e.target.value)}
                  disabled={running}
                  placeholder="React, TypeScript"
                />
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="discover-optional-keywords">Nice-to-have keywords</Label>
                <Input
                  id="discover-optional-keywords"
                  value={form.optionalKeywords}
                  onChange={(e) => update("optionalKeywords", e.target.value)}
                  disabled={running}
                  placeholder="Next.js, design systems"
                />
              </div>
            </div>

            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <div className="space-y-1.5">
                <Label htmlFor="discover-excluded-keywords">Excluded keywords</Label>
                <Input
                  id="discover-excluded-keywords"
                  value={form.excludedKeywords}
                  onChange={(e) => update("excludedKeywords", e.target.value)}
                  disabled={running}
                  placeholder="contract, unpaid"
                />
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="discover-blocked-companies">Blocked companies</Label>
                <Input
                  id="discover-blocked-companies"
                  value={form.blockedCompanies}
                  onChange={(e) => update("blockedCompanies", e.target.value)}
                  disabled={running}
                  placeholder="Acme Corp"
                />
              </div>
            </div>

            <label className="flex w-fit items-center gap-2 text-sm font-medium">
              <input
                type="checkbox"
                checked={form.visaSponsorshipRequired}
                onChange={(e) => update("visaSponsorshipRequired", e.target.checked)}
                disabled={running}
                className="accent-primary size-4"
              />
              Visa sponsorship required
            </label>

            <div className="flex flex-wrap items-center gap-3">
              <Button type="submit" disabled={!canSearch}>
                {running ? <Loader2 className="size-4 animate-spin" /> : <Search className="size-4" />}
                {running ? "Searching..." : "Run search"}
              </Button>
              {runMessage && (
                <p className="text-muted-foreground text-sm">{runMessage}</p>
              )}
            </div>
          </form>
        </CardContent>
      </Card>

      {loading ? (
        <div className="text-muted-foreground flex items-center gap-2 text-sm">
          <Loader2 className="size-4 animate-spin" />
          Loading discovery...
        </div>
      ) : results && results.length > 0 ? (
        <ul className="grid grid-cols-1 gap-3">
          {results.map((result) => {
            const busy = busyResultId === result.id;
            return (
              <li key={result.id}>
                <Card className="gap-0 py-5">
                  <CardContent className="space-y-3">
                    <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
                      <div className="min-w-0 space-y-1">
                        <div className="flex min-w-0 flex-wrap items-center gap-2">
                          <span className="truncate font-medium">{result.title}</span>
                          <span className="text-muted-foreground text-sm">at</span>
                          <span className="truncate text-sm font-medium">
                            {result.company_name}
                          </span>
                        </div>
                        <div className="text-muted-foreground flex flex-wrap items-center gap-x-2 gap-y-1 text-xs">
                          {result.location && (
                            <span className="inline-flex items-center gap-1">
                              <MapPin className="size-3" />
                              {result.location}
                            </span>
                          )}
                          <span>{label(result.work_mode)}</span>
                          <span>{label(result.source)}</span>
                          {result.source_url && (
                            <a
                              href={result.source_url}
                              target="_blank"
                              rel="noreferrer"
                              className="text-primary inline-flex items-center gap-1 hover:underline"
                            >
                              <ExternalLink className="size-3" />
                              Source
                            </a>
                          )}
                        </div>
                      </div>
                      <Badge variant={scoreVariant(result.fit_score)}>
                        {result.fit_score}% match
                      </Badge>
                    </div>

                    {result.fit_reason && (
                      <p className="text-sm">{result.fit_reason}</p>
                    )}
                    <p className="text-muted-foreground line-clamp-3 text-sm">
                      {result.description}
                    </p>

                    <div className="flex flex-wrap items-center gap-2">
                      <Button
                        type="button"
                        size="sm"
                        disabled={busy}
                        onClick={() => saveResult(result.id)}
                      >
                        {busy ? (
                          <Loader2 className="size-4 animate-spin" />
                        ) : (
                          <BookmarkPlus className="size-4" />
                        )}
                        Save
                      </Button>
                      <Button
                        type="button"
                        size="sm"
                        variant="outline"
                        disabled={busy}
                        onClick={() => dismissResult(result.id)}
                      >
                        <XCircle className="size-4" />
                        Dismiss
                      </Button>
                    </div>
                  </CardContent>
                </Card>
              </li>
            );
          })}
        </ul>
      ) : (
        <EmptyState
          icon={Search}
          title="No new discovery results"
          description="Run a search to bring in ranked jobs, or adjust your preferences for a broader query."
        />
      )}
    </div>
  );
}
