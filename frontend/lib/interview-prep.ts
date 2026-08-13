/**
 * Interview-prep helpers. These endpoints store local prep notes and generated
 * prompts only; they do not schedule interviews or contact anyone.
 */

import { api } from "@/lib/api";
import type { InterviewPrep, InterviewPrepStatus } from "@/lib/types";

export interface InterviewPrepCreatePayload {
  job_id: string;
  application_id?: string | null;
  resume_id?: string | null;
  notes?: string | null;
}

export interface InterviewPrepUpdatePayload {
  notes?: string | null;
  status?: InterviewPrepStatus;
}

/** GET /api/interview-prep - list prep packets, optionally by job/application. */
export function listInterviewPrep(
  jobId?: string,
  applicationId?: string | null
): Promise<InterviewPrep[]> {
  const query = new URLSearchParams();
  if (jobId) query.set("job_id", jobId);
  if (applicationId) query.set("application_id", applicationId);
  const queryString = query.toString();
  const suffix = queryString ? `?${queryString}` : "";
  return api.get<InterviewPrep[]>(`/interview-prep${suffix}`);
}

/** POST /api/interview-prep - create a local prep packet for review. */
export function createInterviewPrep(
  payload: InterviewPrepCreatePayload
): Promise<InterviewPrep> {
  return api.post<InterviewPrep>("/interview-prep", payload);
}

/** PATCH /api/interview-prep/{id} - update local notes/status. */
export function updateInterviewPrep(
  id: string,
  payload: InterviewPrepUpdatePayload
): Promise<InterviewPrep> {
  return api.patch<InterviewPrep>(`/interview-prep/${id}`, payload);
}