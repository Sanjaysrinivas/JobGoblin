"use client";

import * as React from "react";
import { useRouter } from "next/navigation";
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
import { Input } from "@/components/ui/input";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Label } from "@/components/ui/label";

type FormState = {
  continent: string;
  country: string;
  location: string;
  jobCategory: string;
  jobTitle: string;
  visaSponsorshipRequired: boolean;
  workMode: WorkMode;
};

const selectClass =
  "border-input bg-card focus-visible:border-ring focus-visible:ring-ring/40 h-9 w-full rounded-md border px-3 py-1 text-sm shadow-xs outline-none focus-visible:ring-[3px] disabled:opacity-50";

const continents = [
  {
    value: "north_america",
    label: "North America",
    countries: [
      { code: "us", label: "United States" },
      { code: "ca", label: "Canada" },
      { code: "mx", label: "Mexico" },
    ],
  },
  {
    value: "europe",
    label: "Europe",
    countries: [
      { code: "gb", label: "United Kingdom" },
      { code: "it", label: "Italy" },
      { code: "de", label: "Germany" },
      { code: "fr", label: "France" },
      { code: "es", label: "Spain" },
      { code: "nl", label: "Netherlands" },
      { code: "ch", label: "Switzerland" },
      { code: "at", label: "Austria" },
      { code: "be", label: "Belgium" },
      { code: "pl", label: "Poland" },
    ],
  },
  {
    value: "asia_pacific",
    label: "Asia Pacific",
    countries: [
      { code: "in", label: "India" },
      { code: "sg", label: "Singapore" },
      { code: "au", label: "Australia" },
      { code: "nz", label: "New Zealand" },
    ],
  },
  { value: "south_america", label: "South America", countries: [{ code: "br", label: "Brazil" }] },
  { value: "africa", label: "Africa", countries: [{ code: "za", label: "South Africa" }] },
];

const jobCategories = [
  {
    value: "it",
    label: "IT",
    titles: [
      "A/B Test Engineer",
      "AI Engineer",
      "AI Product Engineer",
      "AI Research Engineer",
      "API Engineer",
      "Application Analyst",
      "Application Developer",
      "Application Security Engineer",
      "Applied Machine Learning Engineer",
      "AR/VR Developer",
      "Automation Engineer",
      "Backend Developer",
      "Backend Engineer",
      "BI Analyst",
      "BI Developer",
      "Blockchain Developer",
      "Blockchain Engineer",
      "Business Intelligence Analyst",
      "Business Systems Analyst",
      "Cloud Architect",
      "Cloud Engineer",
      "Cloud Infrastructure Engineer",
      "Cloud Security Engineer",
      "Computer and Information Research Scientist",
      "Computer Network Architect",
      "Computer Network Support Specialist",
      "Computer Programmer",
      "Computer Support Specialist",
      "Computer Systems Analyst",
      "Computer Systems Engineer",
      "Computer Vision Engineer",
      "CRM Developer",
      "Cybersecurity Analyst",
      "Cybersecurity Engineer",
      "Data Analyst",
      "Data Architect",
      "Data Engineer",
      "Data Scientist",
      "Data Visualization Engineer",
      "Data Warehouse Engineer",
      "Data Warehousing Specialist",
      "Database Administrator",
      "Database Architect",
      "Database Developer",
      "DevOps Engineer",
      "DevSecOps Engineer",
      "Digital Forensics Analyst",
      "Digital Interface Designer",
      "Document Management Specialist",
      "Embedded Software Engineer",
      "Enterprise Architect",
      "ETL Developer",
      "Firmware Engineer",
      "Frontend Developer",
      "Frontend Engineer",
      "Full Stack Developer",
      "Full Stack Engineer",
      "Game Developer",
      "Geographic Information Systems Technologist",
      "Hardware Engineer",
      "Health Informatics Specialist",
      "Help Desk Analyst",
      "Help Desk Technician",
      "Information Security Analyst",
      "Information Security Engineer",
      "Information Systems Technician",
      "Infrastructure Engineer",
      "iOS Developer",
      "IT Analyst",
      "IT Architect",
      "IT Consultant",
      "IT Project Manager",
      "IT Security Specialist",
      "IT Service Manager",
      "IT Support Engineer",
      "IT Support Specialist",
      "Java Developer",
      "JavaScript Developer",
      "Kubernetes Engineer",
      "LLM Engineer",
      "Machine Learning Engineer",
      "Mainframe Developer",
      "MLOps Engineer",
      "Mobile Developer",
      "Natural Language Processing Engineer",
      "Network Administrator",
      "Network Analyst",
      "Network Engineer",
      "Network Security Engineer",
      "Network Support Specialist",
      "Platform Engineer",
      "Penetration Tester",
      "PHP Developer",
      "Power Platform Developer",
      "Prompt Engineer",
      "Python Developer",
      "QA Analyst",
      "QA Automation Engineer",
      "QA Engineer",
      "Release Engineer",
      "Reliability Engineer",
      "Research Software Engineer",
      "Robotics Software Engineer",
      "Salesforce Developer",
      "SAP Developer",
      "Scrum Master",
      "Security Architect",
      "Security Engineer",
      "Security Operations Center Analyst",
      "Site Reliability Engineer",
      "Software Architect",
      "Software Developer",
      "Software Development Engineer in Test",
      "Software Engineer",
      "Software Engineering Manager",
      "Software QA Analyst",
      "Software Test Engineer",
      "Solutions Architect",
      "Systems Administrator",
      "Systems Analyst",
      "Systems Architect",
      "Systems Engineer",
      "Technical Program Manager",
      "Technical Support Engineer",
      "Technical Writer",
      "Telecommunications Engineer",
      "Test Automation Engineer",
      "UI Developer",
      "UX Engineer",
      "Video Game Designer",
      "Web Administrator",
      "Web and Digital Interface Designer",
      "Web Developer",
      "WordPress Developer",
    ],
  },
  {
    value: "data",
    label: "Data",
    titles: [
      "Analytics Engineer",
      "BI Analyst",
      "BI Developer",
      "Business Intelligence Analyst",
      "Clinical Data Manager",
      "Data Analyst",
      "Data Architect",
      "Data Engineer",
      "Data Scientist",
      "Data Visualization Engineer",
      "Data Warehouse Engineer",
      "Database Administrator",
      "Machine Learning Engineer",
      "Marketing Analyst",
      "Operations Analyst",
      "Product Analyst",
      "Quantitative Analyst",
      "Research Analyst",
      "Statistician",
    ],
  },
  {
    value: "product_design",
    label: "Product & Design",
    titles: [
      "Digital Product Manager",
      "Product Designer",
      "Product Manager",
      "Product Owner",
      "Technical Product Manager",
      "UI Designer",
      "UX Designer",
      "UX Researcher",
      "Web and Digital Interface Designer",
    ],
  },
  {
    value: "sales_marketing",
    label: "Sales & Marketing",
    titles: ["Account Executive", "Sales Development Representative", "Marketing Manager"],
  },
  {
    value: "operations",
    label: "Operations",
    titles: ["Operations Manager", "Project Manager", "Business Analyst"],
  },
  {
    value: "finance",
    label: "Finance",
    titles: ["Financial Analyst", "Accountant", "Controller"],
  },
  {
    value: "healthcare",
    label: "Healthcare",
    titles: ["Nurse", "Healthcare Administrator", "Clinical Research Associate"],
  },
  {
    value: "education",
    label: "Education",
    titles: ["Teacher", "Instructional Designer", "Academic Advisor"],
  },
];
const workModes: { value: WorkMode; label: string }[] = [
  { value: "unknown", label: "Any" },
  { value: "remote", label: "Remote" },
  { value: "hybrid", label: "Hybrid" },
  { value: "onsite", label: "On-site" },
];

const defaultState: FormState = {
  continent: "north_america",
  country: "us",
  location: "",
  jobCategory: "it",
  jobTitle: "Software Engineer",
  visaSponsorshipRequired: false,
  workMode: "unknown",
};

function countriesForContinent(continent: string) {
  return continents.find((item) => item.value === continent)?.countries ?? continents[0].countries;
}

function titlesForCategory(category: string) {
  return jobCategories.find((item) => item.value === category)?.titles ?? jobCategories[0].titles;
}

function continentForCountry(country: string): string {
  return (
    continents.find((group) => group.countries.some((item) => item.code === country))?.value ??
    defaultState.continent
  );
}

function categoryForTitle(title: string): string {
  return jobCategories.find((group) => group.titles.includes(title))?.value ?? defaultState.jobCategory;
}

function countryName(country: string): string {
  return continents.flatMap((group) => group.countries).find((item) => item.code === country)?.label ?? country;
}

function normalizeLocation(state: FormState): string {
  const location = state.location.trim();
  const broadLocations = new Set([
    ...continents.map((continent) => continent.label.toLowerCase()),
    "any",
    "anywhere",
    "global",
    "remote",
    "worldwide",
  ]);
  const key = location.toLowerCase().replace(/\s+/g, " ");
  if (!location || broadLocations.has(key) || key === countryName(state.country).toLowerCase()) {
    return "";
  }
  return location;
}


function fromPreferences(preferences: JobSearchPreferences | null): FormState {
  if (!preferences) return defaultState;
  const country = preferences.target_countries[0] ?? defaultState.country;
  const title = preferences.desired_titles[0] ?? defaultState.jobTitle;
  const location = preferences.target_locations[0] ?? "";
  return {
    continent: continentForCountry(country),
    country,
    location: location === countryName(country) ? "" : location,
    jobCategory: categoryForTitle(title),
    jobTitle: title,
    visaSponsorshipRequired: preferences.visa_sponsorship_required,
    workMode: preferences.work_mode,
  };
}

function toPreferences(
  state: FormState,
  previous: JobSearchPreferences | null
): JobSearchPreferencesPayload {
  const location = normalizeLocation(state);
  return {
    target_countries: [state.country],
    target_locations: location ? [location] : [],
    desired_titles: [state.jobTitle],
    seniority: previous?.seniority ?? null,
    industries: previous?.industries ?? [],
    required_keywords: previous?.required_keywords ?? [],
    optional_keywords: previous?.optional_keywords ?? [],
    excluded_keywords: previous?.excluded_keywords ?? [],
    visa_sponsorship_required: state.visaSponsorshipRequired,
    blocked_companies: previous?.blocked_companies ?? [],
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
  const router = useRouter();
  const [form, setForm] = React.useState<FormState>(defaultState);
  const [savedPreferences, setSavedPreferences] = React.useState<JobSearchPreferences | null>(null);
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
        setSavedPreferences(preferences);
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

  function updateContinent(value: string) {
    setForm((prev) => ({
      ...prev,
      continent: value,
      country: countriesForContinent(value)[0].code,
    }));
  }

  function updateJobCategory(value: string) {
    setForm((prev) => ({
      ...prev,
      jobCategory: value,
      jobTitle: titlesForCategory(value)[0],
    }));
  }

  async function refreshResults() {
    setResults(await listDiscoveryResults());
  }

  async function runSearch(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const preferences = toPreferences(form, savedPreferences);
    const country = preferences.target_countries[0] ?? defaultState.country;
    const location = preferences.target_locations[0] ?? null;
    setError(null);
    setRunMessage(null);
    setRunning(true);
    try {
      const saved = await saveDiscoveryPreferences(preferences);
      setSavedPreferences(saved);
      const run = await createDiscoveryRun({
        country,
        location,
        results_per_page: 10,
      });
      await refreshResults();
      if (run.status === "failed") {
        setRunMessage(run.error || "Search failed.");
      } else {
        const countLabel = `Found ${run.result_count} new result${run.result_count === 1 ? "" : "s"}`;
        setRunMessage(
          run.provider === "mock"
            ? `${countLabel} from the mock provider. Configure Adzuna credentials to search live jobs.`
            : `${countLabel}.`
        );
      }
    } catch (err) {
      setError(errorMessage(err, "Could not run discovery."));
    } finally {
      setRunning(false);
    }
  }

  async function saveResult(resultId: string, openAfterSave = false) {
    setError(null);
    setBusyResultId(resultId);
    try {
      const job = await saveDiscoveryResult(resultId);
      setResults((prev) => prev?.filter((item) => item.id !== resultId) ?? []);
      if (openAfterSave) router.push(`/jobs/${job.id}`);
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

  const countryOptions = countriesForContinent(form.continent);
  const jobTitleOptions = titlesForCategory(form.jobCategory);
  const canSearch = form.country.length === 2 && !!form.jobTitle && !running;

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
            Pick a region, country, and role. JobGoblin uses your resume and profile to rank results.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <form className="space-y-4" onSubmit={runSearch}>
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-4">
              <div className="space-y-1.5">
                <Label htmlFor="discover-continent">Target region</Label>
                <select
                  id="discover-continent"
                  value={form.continent}
                  onChange={(e) => updateContinent(e.target.value)}
                  disabled={running}
                  className={selectClass}
                >
                  {continents.map((continent) => (
                    <option key={continent.value} value={continent.value}>
                      {continent.label}
                    </option>
                  ))}
                </select>
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="discover-country">Country</Label>
                <select
                  id="discover-country"
                  value={form.country}
                  onChange={(e) => update("country", e.target.value)}
                  disabled={running}
                  className={selectClass}
                >
                  {countryOptions.map((country) => (
                    <option key={country.code} value={country.code}>
                      {country.label}
                    </option>
                  ))}
                </select>
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="discover-location">City or region</Label>
                <Input
                  id="discover-location"
                  value={form.location}
                  onChange={(e) => update("location", e.target.value)}
                  disabled={running}
                  placeholder="Optional"
                />
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="discover-work-mode">Work mode</Label>
                <select
                  id="discover-work-mode"
                  value={form.workMode}
                  onChange={(e) => update("workMode", e.target.value as WorkMode)}
                  disabled={running}
                  className={selectClass}
                >
                  {workModes.map((mode) => (
                    <option key={mode.value} value={mode.value}>
                      {mode.label}
                    </option>
                  ))}
                </select>
              </div>
            </div>

            <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
              <div className="space-y-1.5">
                <Label htmlFor="discover-job-category">Job type</Label>
                <select
                  id="discover-job-category"
                  value={form.jobCategory}
                  onChange={(e) => updateJobCategory(e.target.value)}
                  disabled={running}
                  className={selectClass}
                >
                  {jobCategories.map((category) => (
                    <option key={category.value} value={category.value}>
                      {category.label}
                    </option>
                  ))}
                </select>
              </div>
              <div className="space-y-1.5 sm:col-span-2">
                <Label htmlFor="discover-job-title">Role</Label>
                <select
                  id="discover-job-title"
                  value={form.jobTitle}
                  onChange={(e) => update("jobTitle", e.target.value)}
                  disabled={running}
                  className={selectClass}
                >
                  {jobTitleOptions.map((title) => (
                    <option key={title} value={title}>
                      {title}
                    </option>
                  ))}
                </select>
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
              {runMessage && <p className="text-muted-foreground text-sm">{runMessage}</p>}
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
                          <span>{label(result.provider || result.source)}</span>
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

                    {result.fit_reason && <p className="text-sm">{result.fit_reason}</p>}
                    <p className="text-muted-foreground line-clamp-3 text-sm">
                      {result.description}
                    </p>

                    <div className="flex flex-wrap items-center gap-2">
                      <Button
                        type="button"
                        size="sm"
                        disabled={busyResultId !== null}
                        onClick={() => saveResult(result.id, true)}
                      >
                        {busy ? <Loader2 className="size-4 animate-spin" /> : <ExternalLink className="size-4" />}
                        Save & open
                      </Button>
                      <Button
                        type="button"
                        size="sm"
                        variant="outline"
                        disabled={busyResultId !== null}
                        onClick={() => saveResult(result.id)}
                      >
                        {busy ? <Loader2 className="size-4 animate-spin" /> : <BookmarkPlus className="size-4" />}
                        Save
                      </Button>
                      <Button
                        type="button"
                        size="sm"
                        variant="outline"
                        disabled={busyResultId !== null}
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
