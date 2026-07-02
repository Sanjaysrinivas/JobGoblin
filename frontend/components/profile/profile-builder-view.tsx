"use client";

import * as React from "react";
import {
  Briefcase,
  GraduationCap,
  Loader2,
  Plus,
  RotateCcw,
  Save,
  Sparkles,
  Trash2,
  UserRound,
} from "lucide-react";

import { ApiError } from "@/lib/api";
import { getProfile, saveProfile, seedProfileFromResume } from "@/lib/profile";
import { listResumes, type ResumeDetail } from "@/lib/resumes";
import type { ParsedEducation, ParsedExperience, UserProfile, UserProfilePayload } from "@/lib/types";
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

interface DraftProfile {
  full_name: string;
  headline: string;
  location: string;
  website_url: string;
  linkedin_url: string;
  summary: string;
  skills: string;
  experience: DraftExperience[];
  education: ParsedEducation[];
  projects: string;
  certifications: string;
}

type Busy = "load" | "save" | "seed" | null;
type DraftExperience = Omit<ParsedExperience, "highlights"> & { highlights: string };

const emptyDraft: DraftProfile = {
  full_name: "",
  headline: "",
  location: "",
  website_url: "",
  linkedin_url: "",
  summary: "",
  skills: "",
  experience: [],
  education: [],
  projects: "",
  certifications: "",
};

function linesToList(value: string): string[] {
  return value
    .split("\n")
    .map((line) => line.trim())
    .filter(Boolean);
}

function listToLines(value: string[]): string {
  return value.join("\n");
}

function blankToNull(value: string): string | null {
  const trimmed = value.trim();
  return trimmed ? trimmed : null;
}

function toDraft(profile: UserProfile | null): DraftProfile {
  if (!profile) return { ...emptyDraft, experience: [], education: [] };
  return {
    full_name: profile.full_name ?? "",
    headline: profile.headline ?? "",
    location: profile.location ?? "",
    website_url: profile.website_url ?? "",
    linkedin_url: profile.linkedin_url ?? "",
    summary: profile.summary ?? "",
    skills: listToLines(profile.skills ?? []),
    experience: (profile.experience ?? []).map((item) => ({
      ...item,
      highlights: listToLines(item.highlights ?? []),
    })),
    education: profile.education ?? [],
    projects: listToLines(profile.projects ?? []),
    certifications: listToLines(profile.certifications ?? []),
  };
}

function toPayload(draft: DraftProfile): UserProfilePayload {
  return {
    full_name: blankToNull(draft.full_name),
    headline: blankToNull(draft.headline),
    location: blankToNull(draft.location),
    website_url: blankToNull(draft.website_url),
    linkedin_url: blankToNull(draft.linkedin_url),
    summary: blankToNull(draft.summary),
    skills: linesToList(draft.skills),
    experience: draft.experience.map((item) => ({
      ...item,
      highlights: linesToList(item.highlights),
    })),
    education: draft.education,
    projects: linesToList(draft.projects),
    certifications: linesToList(draft.certifications),
  };
}

function emptyExperience(): DraftExperience {
  return { company: "", role: "", start: null, end: null, highlights: "" };
}

function emptyEducation(): ParsedEducation {
  return { institution: "", credential: "", year: null };
}

function FieldGroup({ children }: { children: React.ReactNode }) {
  return <div className="space-y-1.5">{children}</div>;
}

export function ProfileBuilderView() {
  const [profile, setProfile] = React.useState<UserProfile | null>(null);
  const [draft, setDraft] = React.useState<DraftProfile>(emptyDraft);
  const [resumes, setResumes] = React.useState<ResumeDetail[]>([]);
  const [seedResumeId, setSeedResumeId] = React.useState("");
  const [busy, setBusy] = React.useState<Busy>("load");
  const [error, setError] = React.useState<string | null>(null);
  const [notice, setNotice] = React.useState<string | null>(null);

  React.useEffect(() => {
    let active = true;
    (async () => {
      setBusy("load");
      try {
        const [profileResult, resumeList] = await Promise.allSettled([
          getProfile(),
          listResumes(),
        ]);
        if (!active) return;

        if (profileResult.status === "fulfilled") {
          setProfile(profileResult.value);
          setDraft(toDraft(profileResult.value));
        } else if (
          profileResult.reason instanceof ApiError &&
          profileResult.reason.code === "profile_not_found"
        ) {
          setProfile(null);
          setDraft(toDraft(null));
        } else {
          throw profileResult.reason;
        }

        if (resumeList.status === "fulfilled") {
          setResumes(resumeList.value.filter((resume) => resume.parsed_json));
          setSeedResumeId(resumeList.value.find((resume) => resume.parsed_json)?.id ?? "");
        }
      } catch (err) {
        if (!active) return;
        setError(
          err instanceof ApiError && err.isUnauthorized
            ? "Please sign in to edit your profile."
            : "Could not load your profile."
        );
      } finally {
        if (active) setBusy(null);
      }
    })();
    return () => {
      active = false;
    };
  }, []);

  function update<K extends keyof DraftProfile>(key: K, value: DraftProfile[K]) {
    setDraft((current) => ({ ...current, [key]: value }));
  }

  function updateExperience(index: number, patch: Partial<DraftExperience>) {
    setDraft((current) => ({
      ...current,
      experience: current.experience.map((item, i) =>
        i === index ? { ...item, ...patch } : item
      ),
    }));
  }

  function updateEducation(index: number, patch: Partial<ParsedEducation>) {
    setDraft((current) => ({
      ...current,
      education: current.education.map((item, i) =>
        i === index ? { ...item, ...patch } : item
      ),
    }));
  }

  async function onSave(event: React.FormEvent) {
    event.preventDefault();
    setError(null);
    setNotice(null);
    setBusy("save");
    try {
      const saved = await saveProfile(toPayload(draft));
      setProfile(saved);
      setDraft(toDraft(saved));
      setNotice("Profile saved.");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not save profile.");
    } finally {
      setBusy(null);
    }
  }

  async function onSeed() {
    if (!seedResumeId) return;
    setError(null);
    setNotice(null);
    setBusy("seed");
    try {
      const seeded = await seedProfileFromResume(seedResumeId);
      setProfile(seeded);
      setDraft(toDraft(seeded));
      setNotice("Profile seeded from parsed resume sections.");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not seed profile.");
    } finally {
      setBusy(null);
    }
  }

  return (
    <form onSubmit={onSave} className="space-y-8">
      <PageHeader
        title="Profile"
        description="Build a private master profile from your own resume facts and edits."
        actions={
          <Button type="submit" disabled={busy !== null}>
            {busy === "save" ? <Loader2 className="size-4 animate-spin" /> : <Save className="size-4" />}
            Save profile
          </Button>
        }
      />

      {error && (
        <p role="alert" className="bg-destructive/10 text-destructive rounded-md px-3 py-2 text-sm">
          {error}
        </p>
      )}
      {notice && (
        <p role="status" className="bg-primary/10 text-primary rounded-md px-3 py-2 text-sm">
          {notice}
        </p>
      )}

      {busy === "load" ? (
        <div className="text-muted-foreground flex items-center gap-2 text-sm">
          <Loader2 className="size-4 animate-spin" />
          Loading profile...
        </div>
      ) : (
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-5">
          <div className="space-y-6 lg:col-span-2">
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2 text-base">
                  <UserRound className="text-primary size-4" />
                  Basics
                </CardTitle>
                <CardDescription>Identity and positioning you want reused across applications.</CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <FieldGroup>
                  <Label htmlFor="full_name">Full name</Label>
                  <Input id="full_name" value={draft.full_name} onChange={(e) => update("full_name", e.target.value)} />
                </FieldGroup>
                <FieldGroup>
                  <Label htmlFor="headline">Headline</Label>
                  <Input id="headline" value={draft.headline} onChange={(e) => update("headline", e.target.value)} />
                </FieldGroup>
                <FieldGroup>
                  <Label htmlFor="location">Location</Label>
                  <Input id="location" value={draft.location} onChange={(e) => update("location", e.target.value)} />
                </FieldGroup>
                <FieldGroup>
                  <Label htmlFor="website_url">Website</Label>
                  <Input id="website_url" value={draft.website_url} onChange={(e) => update("website_url", e.target.value)} />
                </FieldGroup>
                <FieldGroup>
                  <Label htmlFor="linkedin_url">LinkedIn</Label>
                  <Input id="linkedin_url" value={draft.linkedin_url} onChange={(e) => update("linkedin_url", e.target.value)} />
                </FieldGroup>
                <FieldGroup>
                  <Label htmlFor="summary">Summary</Label>
                  <textarea
                    id="summary"
                    value={draft.summary}
                    onChange={(e) => update("summary", e.target.value)}
                    rows={5}
                    className="border-input bg-card focus-visible:border-ring focus-visible:ring-ring/40 w-full rounded-md border px-3 py-2 text-sm shadow-xs outline-none focus-visible:ring-[3px]"
                  />
                </FieldGroup>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2 text-base">
                  <Sparkles className="text-primary size-4" />
                  Seed from resume
                </CardTitle>
                <CardDescription>Copy parsed sections from one of your uploaded resumes.</CardDescription>
              </CardHeader>
              <CardContent className="space-y-3">
                <select
                  value={seedResumeId}
                  onChange={(e) => setSeedResumeId(e.target.value)}
                  className="border-input bg-card focus-visible:border-ring focus-visible:ring-ring/40 h-9 w-full rounded-md border px-3 text-sm shadow-xs outline-none focus-visible:ring-[3px]"
                  disabled={resumes.length === 0 || busy !== null}
                >
                  {resumes.length === 0 ? (
                    <option value="">No parsed resumes available</option>
                  ) : (
                    resumes.map((resume) => (
                      <option key={resume.id} value={resume.id}>
                        {resume.title}
                      </option>
                    ))
                  )}
                </select>
                <div className="flex flex-wrap items-center gap-2">
                  <Button type="button" variant="secondary" onClick={onSeed} disabled={!seedResumeId || busy !== null}>
                    {busy === "seed" ? <Loader2 className="size-4 animate-spin" /> : <RotateCcw className="size-4" />}
                    Seed sections
                  </Button>
                  {profile?.source_resume_id && <Badge variant="secondary">Seeded</Badge>}
                </div>
              </CardContent>
            </Card>
          </div>

          <div className="space-y-6 lg:col-span-3">
            <Card>
              <CardHeader>
                <CardTitle className="text-base">Skills</CardTitle>
                <CardDescription>One skill per line.</CardDescription>
              </CardHeader>
              <CardContent>
                <textarea
                  value={draft.skills}
                  onChange={(e) => update("skills", e.target.value)}
                  rows={6}
                  className="border-input bg-card focus-visible:border-ring focus-visible:ring-ring/40 w-full rounded-md border px-3 py-2 font-mono text-xs shadow-xs outline-none focus-visible:ring-[3px]"
                />
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2 text-base">
                  <Briefcase className="text-primary size-4" />
                  Experience
                </CardTitle>
                <CardDescription>Roles, dates, and highlights grounded in your work history.</CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                {draft.experience.map((item, index) => (
                  <div key={index} className="space-y-3 rounded-md border p-3">
                    <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                      <Input placeholder="Role" value={item.role} onChange={(e) => updateExperience(index, { role: e.target.value })} />
                      <Input placeholder="Company" value={item.company} onChange={(e) => updateExperience(index, { company: e.target.value })} />
                      <Input placeholder="Start" value={item.start ?? ""} onChange={(e) => updateExperience(index, { start: blankToNull(e.target.value) })} />
                      <Input placeholder="End" value={item.end ?? ""} onChange={(e) => updateExperience(index, { end: blankToNull(e.target.value) })} />
                    </div>
                    <textarea
                      value={item.highlights}
                      onChange={(e) => updateExperience(index, { highlights: e.target.value })}
                      rows={4}
                      placeholder="Highlights, one per line"
                      className="border-input bg-card focus-visible:border-ring focus-visible:ring-ring/40 w-full rounded-md border px-3 py-2 text-sm shadow-xs outline-none focus-visible:ring-[3px]"
                    />
                    <Button
                      type="button"
                      variant="ghost"
                      size="sm"
                      onClick={() => update("experience", draft.experience.filter((_, i) => i !== index))}
                    >
                      <Trash2 className="size-4" />
                      Remove
                    </Button>
                  </div>
                ))}
                <Button type="button" variant="outline" size="sm" onClick={() => update("experience", [...draft.experience, emptyExperience()])}>
                  <Plus className="size-4" />
                  Add experience
                </Button>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2 text-base">
                  <GraduationCap className="text-primary size-4" />
                  Education
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                {draft.education.map((item, index) => (
                  <div key={index} className="grid grid-cols-1 gap-3 rounded-md border p-3 sm:grid-cols-[1fr_1fr_8rem_auto]">
                    <Input placeholder="Credential" value={item.credential} onChange={(e) => updateEducation(index, { credential: e.target.value })} />
                    <Input placeholder="Institution" value={item.institution} onChange={(e) => updateEducation(index, { institution: e.target.value })} />
                    <Input placeholder="Year" value={item.year ?? ""} onChange={(e) => updateEducation(index, { year: blankToNull(e.target.value) })} />
                    <Button type="button" variant="ghost" size="icon" aria-label="Remove education" onClick={() => update("education", draft.education.filter((_, i) => i !== index))}>
                      <Trash2 className="size-4" />
                    </Button>
                  </div>
                ))}
                <Button type="button" variant="outline" size="sm" onClick={() => update("education", [...draft.education, emptyEducation()])}>
                  <Plus className="size-4" />
                  Add education
                </Button>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle className="text-base">Projects and Certifications</CardTitle>
                <CardDescription>One item per line in each field.</CardDescription>
              </CardHeader>
              <CardContent className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                <FieldGroup>
                  <Label htmlFor="projects">Projects</Label>
                  <textarea
                    id="projects"
                    value={draft.projects}
                    onChange={(e) => update("projects", e.target.value)}
                    rows={6}
                    className="border-input bg-card focus-visible:border-ring focus-visible:ring-ring/40 w-full rounded-md border px-3 py-2 text-sm shadow-xs outline-none focus-visible:ring-[3px]"
                  />
                </FieldGroup>
                <FieldGroup>
                  <Label htmlFor="certifications">Certifications</Label>
                  <textarea
                    id="certifications"
                    value={draft.certifications}
                    onChange={(e) => update("certifications", e.target.value)}
                    rows={6}
                    className="border-input bg-card focus-visible:border-ring focus-visible:ring-ring/40 w-full rounded-md border px-3 py-2 text-sm shadow-xs outline-none focus-visible:ring-[3px]"
                  />
                </FieldGroup>
              </CardContent>
            </Card>
          </div>
        </div>
      )}
    </form>
  );
}