/**
 * Resume-to-job analysis API helpers.
 */

import { api } from "@/lib/api";
import type { JobAnalysis } from "@/lib/types";

export interface ResumeJobAnalysisPayload {
  resume_id: string;
  job_id: string;
}

/** POST /api/analysis/resume-job - score one resume against one job. */
export function createResumeJobAnalysis(
  payload: ResumeJobAnalysisPayload
): Promise<JobAnalysis> {
  return api.post<JobAnalysis>("/analysis/resume-job", payload);
}

/** GET /api/jobs/{job_id}/analysis - list saved analyses for a job. */
export function listJobAnalyses(jobId: string): Promise<JobAnalysis[]> {
  return api.get<JobAnalysis[]>(`/jobs/${jobId}/analysis`);
}

/** GET /api/analysis/{id} - fetch one saved analysis. */
export function getJobAnalysis(id: string): Promise<JobAnalysis> {
  return api.get<JobAnalysis>(`/analysis/${id}`);
}
