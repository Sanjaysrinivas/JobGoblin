import type { Metadata } from "next";

import { ResumeDetailView } from "@/components/resumes/resume-detail-view";

export const metadata: Metadata = { title: "Resume" };

export default async function ResumeDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  return <ResumeDetailView resumeId={id} />;
}
