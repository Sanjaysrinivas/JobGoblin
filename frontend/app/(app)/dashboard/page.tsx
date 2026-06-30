import type { Metadata } from "next";
import {
  Bookmark,
  Send,
  CalendarCheck,
  Trophy,
  Target,
  ArrowUpRight,
  Plus,
  FileText,
  Briefcase,
} from "lucide-react";

import { PageHeader } from "@/components/page-header";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";

export const metadata: Metadata = { title: "Dashboard" };

// Placeholder figures — wired to GET /api/dashboard/summary once auth lands.
const stats = [
  {
    label: "Saved",
    value: 12,
    icon: Bookmark,
    hint: "roles in your shortlist",
    tone: "text-info",
  },
  {
    label: "Applied",
    value: 8,
    icon: Send,
    hint: "applications sent",
    tone: "text-primary",
  },
  {
    label: "Interviews",
    value: 3,
    icon: CalendarCheck,
    hint: "in progress",
    tone: "text-warning-foreground",
  },
  {
    label: "Offers",
    value: 1,
    icon: Trophy,
    hint: "on the table",
    tone: "text-success",
  },
];

const pipeline = [
  { stage: "Saved", count: 12, variant: "info" as const },
  { stage: "Applied", count: 8, variant: "default" as const },
  { stage: "Interviewing", count: 3, variant: "warning" as const },
  { stage: "Offer", count: 1, variant: "success" as const },
];
const pipelineMax = Math.max(...pipeline.map((p) => p.count));

const activity = [
  {
    message: "Scored resume against Senior Frontend Engineer @ Vercel",
    meta: "Match 82% · 4 missing keywords",
    when: "2h ago",
  },
  {
    message: "Moved Staff Engineer @ Linear to Interviewing",
    meta: "Status change",
    when: "Yesterday",
  },
  {
    message: "Generated cover letter for Product Engineer @ Stripe",
    meta: "Draft · confident tone",
    when: "2d ago",
  },
  {
    message: "Uploaded resume “2026-baseline.pdf”",
    meta: "Parsed 6 sections",
    when: "3d ago",
  },
];

export default function DashboardPage() {
  return (
    <div className="space-y-8">
      <PageHeader
        title="Dashboard"
        description="Your job hunt at a glance — pipeline, momentum, and what to do next."
        actions={
          <Button>
            <Plus className="size-4" />
            Add a job
          </Button>
        }
      />

      {/* Stat cards */}
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
        {/* Pipeline */}
        <Card
          className="animate-rise lg:col-span-3"
          style={{ animationDelay: "240ms" }}
        >
          <CardHeader>
            <CardTitle>Pipeline</CardTitle>
            <CardDescription>
              Where your opportunities sit right now.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            {pipeline.map((row) => (
              <div key={row.stage} className="space-y-1.5">
                <div className="flex items-center justify-between text-sm">
                  <span className="font-medium">{row.stage}</span>
                  <span className="text-muted-foreground tabular-nums">
                    {row.count}
                  </span>
                </div>
                <div className="bg-secondary h-2.5 w-full overflow-hidden rounded-full">
                  <div
                    className="bg-primary h-full rounded-full transition-all"
                    style={{
                      width: `${Math.max(
                        (row.count / pipelineMax) * 100,
                        6
                      )}%`,
                    }}
                  />
                </div>
              </div>
            ))}
            <div className="text-muted-foreground flex items-center gap-2 pt-2 text-sm">
              <Target className="text-primary size-4" />
              Average match score
              <span className="text-foreground ml-auto font-mono text-sm font-medium">
                74%
              </span>
            </div>
          </CardContent>
        </Card>

        {/* Activity */}
        <Card
          className="animate-rise lg:col-span-2"
          style={{ animationDelay: "300ms" }}
        >
          <CardHeader>
            <CardTitle>Recent activity</CardTitle>
            <CardDescription>Your latest moves.</CardDescription>
          </CardHeader>
          <CardContent>
            <ol className="relative space-y-5 border-l pl-5">
              {activity.map((event, i) => (
                <li key={i} className="relative">
                  <span className="bg-primary ring-card absolute top-1 -left-[1.4rem] size-2.5 rounded-full ring-4" />
                  <p className="text-sm leading-snug font-medium">
                    {event.message}
                  </p>
                  <div className="text-muted-foreground mt-1 flex items-center gap-2 text-xs">
                    <span>{event.meta}</span>
                    <span aria-hidden>·</span>
                    <span>{event.when}</span>
                  </div>
                </li>
              ))}
            </ol>
          </CardContent>
        </Card>
      </div>

      {/* Quick actions */}
      <Card className="animate-rise" style={{ animationDelay: "360ms" }}>
        <CardHeader>
          <CardTitle>Quick start</CardTitle>
          <CardDescription>
            The core loop: upload, analyze, apply, track.
          </CardDescription>
        </CardHeader>
        <CardContent className="grid grid-cols-1 gap-3 sm:grid-cols-3">
          {[
            {
              icon: FileText,
              title: "Upload a resume",
              body: "Extract text and parse sections with AI.",
            },
            {
              icon: Briefcase,
              title: "Add a job",
              body: "Paste a description and score the fit.",
            },
            {
              icon: Send,
              title: "Track an application",
              body: "Log it and follow up on time.",
            },
          ].map((q) => {
            const Icon = q.icon;
            return (
              <button
                key={q.title}
                type="button"
                className="group hover:border-primary/40 hover:bg-secondary/50 flex flex-col items-start gap-2 rounded-lg border p-4 text-left transition-colors"
              >
                <span className="flex w-full items-center justify-between">
                  <Icon className="text-primary size-5" />
                  <ArrowUpRight className="text-muted-foreground size-4 transition-transform group-hover:translate-x-0.5 group-hover:-translate-y-0.5" />
                </span>
                <span className="text-sm font-medium">{q.title}</span>
                <span className="text-muted-foreground text-xs">{q.body}</span>
              </button>
            );
          })}
        </CardContent>
      </Card>

      <p className="text-muted-foreground flex items-center gap-2 text-xs">
        <Badge variant="outline">Preview</Badge>
        Figures are placeholders until the backend auth + dashboard endpoints
        merge.
      </p>
    </div>
  );
}
