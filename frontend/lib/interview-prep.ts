/**
 * Interview-prep helpers. These endpoints store local prep notes and generated
 * prompts only; they do not schedule interviews or contact anyone.
 */

import { api } from "@/lib/api";
import type { InterviewPrep, InterviewPrepStatus } from "@/lib/types";

export interface InterviewPrepCreatePayload {
  job_id: string;
  resume_id?: string | null;
}

export interface InterviewPrepUpdatePayload {
  notes?: string | null;
  status?: InterviewPrepStatus;
}

/** GET /api/interview-prep - list prep packets, optionally by job. */
export function listInterviewPrep(jobId?: string): Promise<InterviewPrep[]> {
  const query = jobId ? `?${new URLSearchParams({ job_id: jobId })}` : "";
  return api.get<InterviewPrep[]>(`/interview-prep${query}`);
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