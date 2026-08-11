"use client";

import * as React from "react";
import {
  AlertTriangle,
  BarChart3,
  CheckCircle2,
  ClipboardCheck,
  ListChecks,
  Loader2,
  Play,
  ShieldCheck,
  Sparkles,
  XCircle,
} from "lucide-react";

import { ApiError } from "@/lib/api";
import {
  createResumeJobAnalysis,
  listJobAnalyses,
} from "@/lib/analysis";
import { listResumes, type ResumeDetail } from "@/lib/resumes";
import type { JobAnalysis } from "@/lib/types";
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

interface JobAnalysisPanelProps {
  jobId: string;
}

const scoreRows: Array<{ key: keyof JobAnalysis; label: string; max: number }> = [
  { key: "keyword_score", label: "Keywords", max: 30 },
  { key: "skills_score", label: "Skills", max: 25 },
  { key: "experience_score", label: "Experience", max: 20 },
  { key: "role_score", label: "Role fit", max: 10 },
  { key: "education_score", label: "Education", max: 5 },
  { key: "formatting_score", label: "Formatting", max: 10 },
];

function formatDate(value: string): string {
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value));
}

function scoreVariant(score: number): "success" | "warning" | "destructive" {
  if (score >= 75) return "success";
  if (score >= 50) return "warning";
  return "destructive";
}

function scoreTone(score: number): string {
  if (score >= 75) return "bg-success";
  if (score >= 50) return "bg-warning";
  return "bg-destructive";
}

function readinessVariant(value: string | null | undefined): "success" | "warning" | "destructive" {
  if (value === "Ready to apply") return "success";
  if (value === "Needs tailoring") return "warning";
  return "destructive";
}

function resumeLabel(resumeId: string, resumes: ResumeDetail[]): string {
  return resumes.find((resume) => resume.id === resumeId)?.title ?? "Resume";
}

function KeywordList({
  icon,
  title,
  values,
  empty,
  variant,
}: {
  icon: React.ReactNode;
  title: string;
  values: string[] | null;
  empty: string;
  variant: "success" | "outline" | "destructive";
}) {
  return (
    <div className="space-y-2">
      <div className="flex items-center gap-2 text-sm font-medium">
        {icon}
        {title}
      </div>
      {values && values.length > 0 ? (
        <div className="flex flex-wrap gap-2">
          {values.map((keyword) => (
            <Badge key={keyword} variant={variant}>
              {keyword}
            </Badge>
          ))}
        </div>
      ) : (
        <p className="text-muted-foreground text-sm">{empty}</p>
      )}
    </div>
  );
}

export function JobAnalysisPanel({ jobId }: JobAnalysisPanelProps) {
  const [resumes, setResumes] = React.useState<ResumeDetail[]>([]);
  const [analyses, setAnalyses] = React.useState<JobAnalysis[]>([]);
  const [selectedResumeId, setSelectedResumeId] = React.useState("");
  const [selectedAnalysisId, setSelectedAnalysisId] = React.useState("");
  const [loading, setLoading] = React.useState(true);
  const [running, setRunning] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);
  const [historyNotice, setHistoryNotice] = React.useState<string | null>(null);

  React.useEffect(() => {
    let active = true;
    (async () => {
      setLoading(true);
      setError(null);
      setHistoryNotice(null);
      try {
        const resumeData = await listResumes();
        let analysisData: JobAnalysis[] = [];
        try {
          analysisData = await listJobAnalyses(jobId);
        } catch (err) {
          if (err instanceof ApiError && err.status === 404) {
            setHistoryNotice(
              "Previous analyses are not available from the backend yet. New analyses will still appear here after you run them."
            );
          } else {
            throw err;
          }
        }
        if (!active) return;
        setResumes(resumeData);
        setAnalyses(analysisData);
        const defaultResume = resumeData.find((resume) => resume.is_default);
        setSelectedResumeId(defaultResume?.id ?? resumeData[0]?.id ?? "");
        setSelectedAnalysisId(analysisData[0]?.id ?? "");
      } catch (err) {
        if (!active) return;
        setError(
          err instanceof ApiError && err.isUnauthorized
            ? "Please sign in to analyze this job."
            : "Could not load resumes or analyses. Is the backend running?"
        );
      } finally {
        if (active) setLoading(false);
      }
    })();
    return () => {
      active = false;
    };
  }, [jobId]);

  async function runAnalysis() {
    if (!selectedResumeId) return;
    setRunning(true);
    setError(null);
    try {
      const created = await createResumeJobAnalysis({
        job_id: jobId,
        resume_id: selectedResumeId,
      });
      setAnalyses((prev) => [created, ...prev.filter((item) => item.id !== created.id)]);
      setSelectedAnalysisId(created.id);
      setHistoryNotice(null);
    } catch (err) {
      setError(
        err instanceof ApiError
          ? err.message || "Could not run analysis."
          : "Could not reach the server. Is the backend running?"
      );
    } finally {
      setRunning(false);
    }
  }

  const selectedAnalysis =
    analyses.find((analysis) => analysis.id === selectedAnalysisId) ?? analyses[0];

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-base">
          <Sparkles className="text-primary size-4" />
          Resume analysis
        </CardTitle>
        <CardDescription>
          Score a saved resume against this job description and review prior runs.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-5">
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-[1fr_1fr_auto] lg:items-end">
          <div className="space-y-2">
            <Label htmlFor="analysis-resume">Resume</Label>
            <select
              id="analysis-resume"
              value={selectedResumeId}
              onChange={(event) => setSelectedResumeId(event.target.value)}
              disabled={loading || running || resumes.length === 0}
              className="border-input bg-card focus-visible:border-ring focus-visible:ring-ring/40 flex h-9 w-full rounded-md border px-3 py-1 text-sm shadow-xs outline-none transition-[color,box-shadow] focus-visible:ring-[3px] disabled:cursor-not-allowed disabled:opacity-50"
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
            <Label htmlFor="analysis-history">Previous analyses</Label>
            <select
              id="analysis-history"
              value={selectedAnalysis?.id ?? ""}
              onChange={(event) => setSelectedAnalysisId(event.target.value)}
              disabled={loading || analyses.length === 0}
              className="border-input bg-card focus-visible:border-ring focus-visible:ring-ring/40 flex h-9 w-full rounded-md border px-3 py-1 text-sm shadow-xs outline-none transition-[color,box-shadow] focus-visible:ring-[3px] disabled:cursor-not-allowed disabled:opacity-50"
            >
              {analyses.length === 0 ? (
                <option value="">No analyses yet</option>
              ) : (
                analyses.map((analysis) => (
                  <option key={analysis.id} value={analysis.id}>
                    {Math.round(analysis.overall_score)}% - {resumeLabel(analysis.resume_id, resumes)} - {formatDate(analysis.created_at)}
                  </option>
                ))
              )}
            </select>
          </div>

          <Button
            type="button"
            onClick={runAnalysis}
            disabled={loading || running || !selectedResumeId}
            className="lg:mb-0"
          >
            {running ? (
              <Loader2 className="size-4 animate-spin" />
            ) : (
              <Play className="size-4" />
            )}
            {running ? "Analyzing..." : "Run analysis"}
          </Button>
        </div>

        {loading && (
          <div className="text-muted-foreground flex items-center gap-2 text-sm">
            <Loader2 className="size-4 animate-spin" />
            Loading analysis tools...
          </div>
        )}

        {error && (
          <p
            role="alert"
            className="bg-destructive/10 text-destructive rounded-md px-3 py-2 text-sm"
          >
            {error}
          </p>
        )}

        {historyNotice && (
          <p className="bg-warning/15 text-warning-foreground rounded-md px-3 py-2 text-sm">
            {historyNotice}
          </p>
        )}

        {resumes.length === 0 && !loading && (
          <p className="text-muted-foreground rounded-md border border-dashed px-3 py-4 text-sm">
            Upload a resume before running job analysis.
          </p>
        )}

        <div className="grid grid-cols-1 gap-3 text-sm lg:grid-cols-2">
          <div className="border-border/70 bg-secondary/30 flex gap-3 rounded-lg border p-3">
            <ShieldCheck className="text-primary mt-0.5 size-4 shrink-0" />
            <p className="text-muted-foreground">
              Scores are estimates based on the saved job description and resume text. Use them for prioritization, not as a hiring prediction.
            </p>
          </div>
          <div className="border-border/70 bg-secondary/30 flex gap-3 rounded-lg border p-3">
            <AlertTriangle className="text-warning-foreground mt-0.5 size-4 shrink-0" />
            <p className="text-muted-foreground">
              No-fabrication rule: only add missing keywords or skills when they truthfully reflect your experience.
            </p>
          </div>
        </div>

        {selectedAnalysis ? (
          <div className="grid grid-cols-1 gap-6 lg:grid-cols-5">
            <div className="space-y-4 lg:col-span-2">
              <div className="rounded-lg border p-4">
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <p className="text-muted-foreground text-xs font-medium uppercase tracking-wide">
                      Overall match
                    </p>
                    <p className="font-display mt-1 text-4xl font-semibold tabular-nums">
                      {Math.round(selectedAnalysis.overall_score)}%
                    </p>
                  </div>
                  <Badge variant={scoreVariant(selectedAnalysis.overall_score)}>
                    {resumeLabel(selectedAnalysis.resume_id, resumes)}
                  </Badge>
                </div>
                <div className="mt-3 flex flex-wrap gap-2">
                  {selectedAnalysis.fit_label && (
                    <Badge variant={scoreVariant(selectedAnalysis.overall_score)}>
                      {selectedAnalysis.fit_label}
                    </Badge>
                  )}
                  {selectedAnalysis.application_readiness && (
                    <Badge variant={readinessVariant(selectedAnalysis.application_readiness)}>
                      {selectedAnalysis.application_readiness}
                    </Badge>
                  )}
                </div>
                <p className="text-muted-foreground mt-3 text-xs">
                  {selectedAnalysis.provider} / {selectedAnalysis.model_used} - {formatDate(selectedAnalysis.created_at)}
                </p>
              </div>

              {selectedAnalysis.readiness_steps && selectedAnalysis.readiness_steps.length > 0 && (
                <div className="space-y-2 rounded-lg border p-4">
                  <div className="flex items-center gap-2 text-sm font-medium">
                    <ClipboardCheck className="text-primary size-4" />
                    Application readiness
                  </div>
                  <ul className="text-muted-foreground list-disc space-y-1 pl-5 text-sm">
                    {selectedAnalysis.readiness_steps.map((step) => (
                      <li key={step}>{step}</li>
                    ))}
                  </ul>
                </div>
              )}

              <div className="space-y-3 rounded-lg border p-4">
                <div className="flex items-center gap-2 text-sm font-medium">
                  <BarChart3 className="text-primary size-4" />
                  Score breakdown
                </div>
                <div className="space-y-3">
                  {scoreRows.map((row) => {
                    const value = Number(selectedAnalysis[row.key] ?? 0);
                    return (
                      <div key={row.key} className="space-y-1.5">
                        <div className="flex items-center justify-between text-xs">
                          <span className="text-muted-foreground">{row.label}</span>
                          <span className="font-mono font-medium tabular-nums">
                            {Math.round(value)}/{row.max}
                          </span>
                        </div>
                        <div className="bg-secondary h-2 overflow-hidden rounded-full">
                          <div
                            className={`${scoreTone(value)} h-full rounded-full`}
                            style={{ width: `${Math.max(0, Math.min((value / row.max) * 100, 100))}%` }}
                          />
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            </div>

            <div className="space-y-5 lg:col-span-3">
              <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
                <KeywordList
                  icon={<CheckCircle2 className="text-success size-4" />}
                  title="Matched keywords"
                  values={selectedAnalysis.matched_keywords}
                  empty="No matched keywords returned."
                  variant="success"
                />
                <KeywordList
                  icon={<XCircle className="text-destructive size-4" />}
                  title="Missing keywords"
                  values={selectedAnalysis.missing_keywords}
                  empty="No missing keywords returned."
                  variant="destructive"
                />
              </div>

              {selectedAnalysis.keyword_checklist && selectedAnalysis.keyword_checklist.length > 0 && (
                <div className="space-y-3">
                  <div className="flex items-center gap-2 text-sm font-medium">
                    <ListChecks className="text-primary size-4" />
                    ATS checklist
                  </div>
                  <div className="grid grid-cols-1 gap-3">
                    {selectedAnalysis.keyword_checklist.map((group) => (
                      <div key={group.label} className="rounded-lg border p-3">
                        <h3 className="text-sm font-medium">{group.label}</h3>
                        <div className="mt-2 grid grid-cols-1 gap-3 md:grid-cols-2">
                          <KeywordList
                            icon={<CheckCircle2 className="text-success size-4" />}
                            title="Present"
                            values={group.matched}
                            empty="No matching evidence found."
                            variant="success"
                          />
                          <KeywordList
                            icon={<XCircle className="text-destructive size-4" />}
                            title="Verify before adding"
                            values={group.missing}
                            empty="No gaps in this group."
                            variant="outline"
                          />
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {selectedAnalysis.rewrite_suggestions && selectedAnalysis.rewrite_suggestions.length > 0 && (
                <div className="space-y-3">
                  <h3 className="text-sm font-medium">Resume rewrite suggestions</h3>
                  <div className="grid grid-cols-1 gap-3">
                    {selectedAnalysis.rewrite_suggestions.map((suggestion) => (
                      <div key={`${suggestion.section}-${suggestion.action}`} className="rounded-lg border p-3">
                        <div className="flex flex-wrap items-center gap-2">
                          <Badge variant="outline">{suggestion.section}</Badge>
                          <span className="text-sm font-medium">{suggestion.action}</span>
                        </div>
                        <p className="text-muted-foreground mt-2 text-sm">{suggestion.prompt}</p>
                        {suggestion.verify_before_adding.length > 0 && (
                          <div className="mt-3">
                            <p className="text-muted-foreground text-xs font-medium uppercase tracking-wide">
                              Verify before adding
                            </p>
                            <div className="mt-2 flex flex-wrap gap-2">
                              {suggestion.verify_before_adding.map((item) => (
                                <Badge key={item} variant="outline">
                                  {item}
                                </Badge>
                              ))}
                            </div>
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                </div>
              )}

              <div className="space-y-2">
                <h3 className="text-sm font-medium">Recommendations</h3>
                {selectedAnalysis.recommendations && selectedAnalysis.recommendations.length > 0 ? (
                  <ul className="text-muted-foreground list-disc space-y-1 pl-5 text-sm">
                    {selectedAnalysis.recommendations.map((recommendation) => (
                      <li key={recommendation}>{recommendation}</li>
                    ))}
                  </ul>
                ) : (
                  <p className="text-muted-foreground text-sm">
                    No recommendations returned.
                  </p>
                )}
              </div>

              <div className="space-y-2">
                <h3 className="text-sm font-medium">Explanation</h3>
                <p className="bg-secondary/35 whitespace-pre-wrap rounded-md p-4 text-sm leading-relaxed">
                  {selectedAnalysis.explanation || "No explanation returned."}
                </p>
              </div>
            </div>
          </div>
        ) : !loading ? (
          <p className="text-muted-foreground rounded-md border border-dashed px-3 py-4 text-sm">
            Run an analysis to see scores, keywords, recommendations, and explanation here.
          </p>
        ) : null}
      </CardContent>
    </Card>
  );
}


