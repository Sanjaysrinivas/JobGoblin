import {
  Award,
  Briefcase,
  FolderGit2,
  GraduationCap,
  Sparkles,
  Wrench,
} from "lucide-react";

import type { ParsedResume } from "@/lib/types";
import { Badge } from "@/components/ui/badge";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";

function SectionCard({
  icon: Icon,
  title,
  children,
}: {
  icon: typeof Sparkles;
  title: string;
  children: React.ReactNode;
}) {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-base">
          <Icon className="text-primary size-4" />
          {title}
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-3 text-sm">{children}</CardContent>
    </Card>
  );
}

/**
 * Read-only render of a parsed resume profile: summary, skills, experience,
 * education, projects, certifications. Sections with no data are omitted.
 */
export function ParsedSections({ parsed }: { parsed: ParsedResume | null }) {
  if (!parsed) {
    return (
      <p className="text-muted-foreground text-sm">
        This resume has not been parsed yet. Run a parse to extract sections.
      </p>
    );
  }

  const hasExperience = parsed.experience?.length > 0;
  const hasEducation = parsed.education?.length > 0;
  const hasSkills = parsed.skills?.length > 0;
  const hasProjects = parsed.projects?.length > 0;
  const hasCerts = parsed.certifications?.length > 0;

  const empty =
    !parsed.summary &&
    !hasSkills &&
    !hasExperience &&
    !hasEducation &&
    !hasProjects &&
    !hasCerts;

  if (empty) {
    return (
      <p className="text-muted-foreground text-sm">
        The parser did not find any sections. Try editing the extracted text and
        re-parsing.
      </p>
    );
  }

  return (
    <div className="space-y-4">
      {parsed.summary && (
        <SectionCard icon={Sparkles} title="Summary">
          <p className="leading-relaxed">{parsed.summary}</p>
        </SectionCard>
      )}

      {hasSkills && (
        <SectionCard icon={Wrench} title="Skills">
          <div className="flex flex-wrap gap-1.5">
            {parsed.skills.map((skill, i) => (
              <Badge key={`${skill}-${i}`} variant="secondary">
                {skill}
              </Badge>
            ))}
          </div>
        </SectionCard>
      )}

      {hasExperience && (
        <SectionCard icon={Briefcase} title="Experience">
          <ul className="space-y-4">
            {parsed.experience.map((exp, i) => {
              const dates = [exp.start, exp.end].filter(Boolean).join(" – ");
              return (
                <li key={i} className="space-y-1">
                  <div className="flex flex-wrap items-baseline justify-between gap-x-2">
                    <span className="font-medium">
                      {[exp.role, exp.company].filter(Boolean).join(" · ")}
                    </span>
                    {dates && (
                      <span className="text-muted-foreground text-xs tabular-nums">
                        {dates}
                      </span>
                    )}
                  </div>
                  {exp.highlights?.length > 0 && (
                    <ul className="text-muted-foreground list-disc space-y-0.5 pl-5">
                      {exp.highlights.map((h, j) => (
                        <li key={j}>{h}</li>
                      ))}
                    </ul>
                  )}
                </li>
              );
            })}
          </ul>
        </SectionCard>
      )}

      {hasEducation && (
        <SectionCard icon={GraduationCap} title="Education">
          <ul className="space-y-2">
            {parsed.education.map((ed, i) => (
              <li key={i} className="flex flex-wrap items-baseline justify-between gap-x-2">
                <span>
                  {[ed.credential, ed.institution].filter(Boolean).join(", ")}
                </span>
                {ed.year && (
                  <span className="text-muted-foreground text-xs tabular-nums">
                    {ed.year}
                  </span>
                )}
              </li>
            ))}
          </ul>
        </SectionCard>
      )}

      {hasProjects && (
        <SectionCard icon={FolderGit2} title="Projects">
          <ul className="list-disc space-y-0.5 pl-5">
            {parsed.projects.map((p, i) => (
              <li key={i}>{p}</li>
            ))}
          </ul>
        </SectionCard>
      )}

      {hasCerts && (
        <SectionCard icon={Award} title="Certifications">
          <ul className="list-disc space-y-0.5 pl-5">
            {parsed.certifications.map((c, i) => (
              <li key={i}>{c}</li>
            ))}
          </ul>
        </SectionCard>
      )}
    </div>
  );
}
