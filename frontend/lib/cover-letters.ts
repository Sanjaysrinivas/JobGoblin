/**
 * Cover-letter draft helpers. These endpoints store editable drafts only; they
 * do not send email, submit applications, or contact employers.
 */

import { api } from "@/lib/api";
import type {
  CoverLetter,
  CoverLetterStatus,
  CoverLetterTone,
} from "@/lib/types";

export interface CoverLetterCreatePayload {
  job_id: string;
  resume_id: string;
  tone?: CoverLetterTone;
}

export interface CoverLetterUpdatePayload {
  content?: string;
  tone?: CoverLetterTone;
  status?: CoverLetterStatus;
}

/** GET /api/cover-letters - list the current user's local cover-letter drafts. */
export function listCoverLetters(jobId?: string): Promise<CoverLetter[]> {
  const query = jobId ? `?${new URLSearchParams({ job_id: jobId })}` : "";
  return api.get<CoverLetter[]>(`/cover-letters${query}`);
}

/** GET /api/cover-letters/{id} - fetch one editable draft. */
export function getCoverLetter(id: string): Promise<CoverLetter> {
  return api.get<CoverLetter>(`/cover-letters/${id}`);
}

/** POST /api/cover-letters - generate and save a local draft for review. */
export function createCoverLetter(
  payload: CoverLetterCreatePayload
): Promise<CoverLetter> {
  return api.post<CoverLetter>("/cover-letters", payload);
}

/** PATCH /api/cover-letters/{id} - update draft text or local review status. */
export function updateCoverLetter(
  id: string,
  payload: CoverLetterUpdatePayload
): Promise<CoverLetter> {
  return api.patch<CoverLetter>(`/cover-letters/${id}`, payload);
}