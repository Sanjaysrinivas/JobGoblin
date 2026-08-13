import type { Metadata } from "next";

import { ResumeListView } from "@/components/resumes/resume-list-view";

export const metadata: Metadata = { title: "Resumes" };

export default function ResumesPage() {
  return <ResumeListView />;
}
