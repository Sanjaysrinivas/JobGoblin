"use client";

import * as React from "react";
import Link from "next/link";
import {
  ArrowUpRight,
  Bell,
  Briefcase,
  FileText,
  Loader2,
  Plus,
  Send,
  Target,
} from "lucide-react";

import { ApiError } from "@/lib/api";
import { getDashboardSummary, listDashboardActivity } from "@/lib/dashboard";
import type { ActivityEvent, DashboardSummary } from "@/lib/types";
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

function formatStatus(value: string): string {
  return value
    .split("_")
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

function formatRelative(value: string): string {
  const then = new Date(value).getTime();
  if (Number.isNaN(then)) return "Unknown time";

  const diffSeconds = Math.round((then - Date.now()) / 1000);
  const units: Array<[Intl.RelativeTimeFormatUnit, number]> = [
    ["year", 60 * 60 * 24 * 365],
    ["month", 60 * 60 * 24 * 30],
    ["day", 60 * 60 * 24],
    ["hour", 60 * 60],
    ["minute", 60],
  ];
  const rtf = new Intl.RelativeTimeFormat(undefined, { numeric: "auto" });

  for (const [unit, seconds] of units) {
    if (Math.abs(diffSeconds) >= seconds) {
      return rtf.format(Math.round(diffSeconds / seconds), unit);
    }
  }
  return "just now";
}

function activityMessage(event: ActivityEvent): string {
  return event.description || formatStatus(event.event_type);
}

function activityMeta(event: ActivityEvent): string {
  return `${formatStatus(event.entity_type)} - ${formatStatus(event.event_type)}`;
}

export function DashboardView() {
  const [summary, setSummary] = React.useState<DashboardSummary | null>(null);
  const [activity, setActivity] = React.useState<ActivityEvent[] | null>(null);
  const [error, setError] = React.useState<string | null>(null);

  React.useEffect(() => {
    let active = true;
    (async () => {
      try {
        const [summaryData, activityData] = await Promise.all([
          getDashboardSummary(),
          listDashboardActivity(),
        ]);
        if (!active) return;
        setSummary(summaryData);
        setActivity(activityData);
      } catch (err) {
        if (!active) return;
        setError(
          err instanceof ApiError && err.isUnauthorized
            ? "Please sign in to view your dashboard."
            : "Could not load dashboard data."
        );
        setSummary(null);
        setActivity([]);
      }
    })();
    return () => {
      active = false;
    };
  }, []);

  const stats = summary
    ? [
        {
          label: "Saved jobs",
          value: summary.saved.toLocaleString(),
          icon: Briefcase,
          hint: "roles in your shortlist",
          tone: "text-info",
        },
        {
          label: "Applied",
          value: summary.applied.toLocaleString(),
          icon: Send,
          hint: "applications submitted",
          tone: "text-primary",
        },
        {
          label: "Follow-ups",
          value: summary.follow_ups_due.toLocaleString(),
          icon: Bell,
          hint: "due now or overdue",
          tone: "text-warning-foreground",
        },
        {
          label: "Avg. score",
          value: summary.avg_score == null ? "-" : `${Math.round(summary.avg_score)}%`,
          icon: Target,
          hint: "resume-to-job estimate",
          tone: "text-success",
        },
      ]
    : [];

  const pipeline = summary
    ? [
        { stage: "Saved", count: summary.saved, variant: "info" as const },
        { stage: "Applied", count: summary.applied, variant: "default" as const },
        { stage: "Interviewing", count: summary.interviewing, variant: "warning" as const },
        { stage: "Offers", count: summary.offers, variant: "success" as const },
      ]
    : [];
  const pipelineMax = Math.max(1, ...pipeline.map((p) => p.count));

  return (
    <div className="space-y-8">
      <PageHeader
        title="Dashboard"
        description="Your job hunt at a glance: pipeline, momentum, and what to do next."
        actions={
          <Button asChild>
            <Link href="/jobs">
              <Plus className="size-4" />
              Add a job
            </Link>
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

      {summary === null && !error ? (
        <div className="text-muted-foreground flex items-center gap-2 text-sm">
          <Loader2 className="size-4 animate-spin" />
          Loading dashboard...
        </div>
      ) : summary ? (
        <>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
            {stats.map((stat, i) => {
              const Icon = stat.icon;
              return (
                <Card
                  key={stat.label}
                  className="animate-rise gap-0 py-5"
                  style={{ animationDelay: `${i * 60}ms` }}
                >
                  <CardContent className="space-y-3">
                    <div className="flex items-center justify-between">
                      <span className="text-muted-foreground text-sm font-medium">
                        {stat.label}
                      </span>
                      <Icon className={`size-4 ${stat.tone}`} />
                    </div>
                    <div className="font-display text-3xl font-semibold tracking-tight tabular-nums">
                      {stat.value}
                    </div>
                    <p className="text-muted-foreground text-xs">{stat.hint}</p>
                  </CardContent>
                </Card>
              );
            })}
          </div>

          <div className="grid grid-cols-1 gap-6 lg:grid-cols-5">
            <Card className="animate-rise lg:col-span-3" style={{ animationDelay: "240ms" }}>
              <CardHeader>
                <CardTitle>Pipeline</CardTitle>
                <CardDescription>
                  Application status counts from your tracked jobs.
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                {pipeline.map((row) => (
                  <div key={row.stage} className="space-y-1.5">
                    <div className="flex items-center justify-between text-sm">
                      <span className="font-medium">{row.stage}</span>
                      <Badge variant={row.variant}>{row.count}</Badge>
                    </div>
                    <div className="bg-secondary h-2.5 w-full overflow-hidden rounded-full">
                      <div
                        className="bg-primary h-full rounded-full transition-all"
                        style={{
                          width:
                            row.count === 0
                              ? "0%"
                              : `${Math.max((row.count / pipelineMax) * 100, 6)}%`,
                        }}
                      />
                    </div>
                  </div>
                ))}
              </CardContent>
            </Card>

            <Card className="animate-rise lg:col-span-2" style={{ animationDelay: "300ms" }}>
              <CardHeader>
                <CardTitle>Recent activity</CardTitle>
                <CardDescription>Your latest moves.</CardDescription>
              </CardHeader>
              <CardContent>
                {activity === null ? (
                  <div className="text-muted-foreground flex items-center gap-2 text-sm">
                    <Loader2 className="size-4 animate-spin" />
                    Loading activity...
                  </div>
                ) : activity.length === 0 ? (
                  <p className="text-muted-foreground text-sm">No activity recorded yet.</p>
                ) : (
                  <ol className="relative space-y-5 border-l pl-5">
                    {activity.map((event) => (
                      <li key={event.id} className="relative">
                        <span className="bg-primary ring-card absolute top-1 -left-[1.4rem] size-2.5 rounded-full ring-4" />
                        <p className="text-sm leading-snug font-medium">
                          {activityMessage(event)}
                        </p>
                        <div className="text-muted-foreground mt-1 flex flex-wrap items-center gap-2 text-xs">
                          <span>{activityMeta(event)}</span>
                          <span aria-hidden>-</span>
                          <span>{formatRelative(event.created_at)}</span>
                        </div>
                      </li>
                    ))}
                  </ol>
                )}
              </CardContent>
            </Card>
          </div>

          <Card className="animate-rise" style={{ animationDelay: "360ms" }}>
            <CardHeader>
              <CardTitle>Quick start</CardTitle>
              <CardDescription>The core loop: upload, analyze, apply, track.</CardDescription>
            </CardHeader>
            <CardContent className="grid grid-cols-1 gap-3 sm:grid-cols-3">
              {[
                {
                  href: "/resumes",
                  icon: FileText,
                  title: "Upload a resume",
                  body: "Extract text and parse sections with AI.",
                },
                {
                  href: "/jobs",
                  icon: Briefcase,
                  title: "Add a job",
                  body: "Paste a description and score the fit.",
                },
                {
                  href: "/applications",
                  icon: Send,
                  title: "Track an application",
                  body: "Log it and follow up on time.",
                },
              ].map((q) => {
                const Icon = q.icon;
                return (
                  <Link
                    key={q.title}
                    href={q.href}
                    className="group hover:border-primary/40 hover:bg-secondary/50 flex flex-col items-start gap-2 rounded-lg border p-4 text-left transition-colors"
                  >
                    <span className="flex w-full items-center justify-between">
                      <Icon className="text-primary size-5" />
                      <ArrowUpRight className="text-muted-foreground size-4 transition-transform group-hover:translate-x-0.5 group-hover:-translate-y-0.5" />
                    </span>
                    <span className="text-sm font-medium">{q.title}</span>
                    <span className="text-muted-foreground text-xs">{q.body}</span>
                  </Link>
                );
              })}
            </CardContent>
          </Card>

          <p className="text-muted-foreground flex items-center gap-2 text-xs">
            <Badge variant="outline">Live data</Badge>
            Counts and activity are loaded from the authenticated dashboard API.
          </p>
        </>
      ) : null}
    </div>
  );
}
