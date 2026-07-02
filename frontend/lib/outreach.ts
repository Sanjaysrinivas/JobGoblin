/**
 * Outreach review queue helpers. These endpoints store local drafts only; they
 * do not send email, open mail clients, or post to external services.
 */

import { api } from "@/lib/api";
import type {
  Outreach,
  OutreachCreatePayload,
  OutreachUpdatePayload,
} from "@/lib/types";

export interface OutreachJobSummary {
  id: string;
  company_name: string;
  title: string;
  location: string | null;
}

export interface OutreachContactSummary {
  id: string;
  name: string;
  company: string | null;
  role: string | null;
  email: string | null;
  linkedin_url: string | null;
}

export interface OutreachDraft extends Outreach {
  job: OutreachJobSummary | null;
  contact: OutreachContactSummary | null;
}


/** GET /api/outreach - list the current user's local outreach drafts. */
export function listOutreach(): Promise<OutreachDraft[]> {
  return api.get<OutreachDraft[]>("/outreach");
}

/** POST /api/outreach - create a review-only local draft. */
export function createOutreach(
  payload: OutreachCreatePayload
): Promise<OutreachDraft> {
  return api.post<OutreachDraft>("/outreach", payload);
}

/** PATCH /api/outreach/{id} - update draft text or local review status. */
export function updateOutreach(
  id: string,
  payload: OutreachUpdatePayload
): Promise<OutreachDraft> {
  return api.patch<OutreachDraft>(`/outreach/${id}`, payload);
}

/** DELETE /api/outreach/{id} - remove a local outreach draft. */
export function deleteOutreach(id: string): Promise<void> {
  return api.delete<void>(`/outreach/${id}`);
}