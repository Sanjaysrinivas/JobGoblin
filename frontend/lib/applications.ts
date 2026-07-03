/**
 * Application tracking helpers. These endpoints record local workflow state
 * only; they do not send email or submit applications.
 */

import { api } from "@/lib/api";
import type { Application, ApplicationStatus, ApplicationWorkflow } from "@/lib/types";

export interface ApplicationJobSummary {
  id: string;
  company_name: string;
  title: string;
  location: string | null;
}

export interface TrackedApplication extends Application {
  job: ApplicationJobSummary;
}

export interface ApplicationFollowUpActivity {
  event_type: string;
  description: string | null;
  created_at: string;
}

export interface ApplicationFollowUp extends Omit<Application, "follow_up_at"> {
  follow_up_at: string;
  due: boolean;
  job: ApplicationJobSummary;
  latest_activity: ApplicationFollowUpActivity | null;
}

export interface ApplicationCreatePayload {
  job_id: string;
  resume_id?: string | null;
  cover_letter_id?: string | null;
  status?: ApplicationStatus;
  applied_at?: string | null;
  follow_up_at?: string | null;
  notes?: string | null;
}

export type ApplicationUpdatePayload = Partial<
  Omit<ApplicationCreatePayload, "job_id">
>;

/** GET /api/applications - list the current user's tracked applications. */
export function listApplications(): Promise<TrackedApplication[]> {
  return api.get<TrackedApplication[]>("/applications");
}

/** GET /api/applications/follow-ups - list due and upcoming reminders. */
export function listApplicationFollowUps(
  days = 14
): Promise<ApplicationFollowUp[]> {
  const params = new URLSearchParams({ days: String(days) });
  return api.get<ApplicationFollowUp[]>(`/applications/follow-ups?${params}`);
}

/** GET /api/applications/{id}/workflow - fetch linked workflow context. */
export function getApplicationWorkflow(id: string): Promise<ApplicationWorkflow> {
  return api.get<ApplicationWorkflow>(`/applications/${id}/workflow`);
}
/** POST /api/applications - start tracking one saved job. */
export function createApplication(
  payload: ApplicationCreatePayload
): Promise<TrackedApplication> {
  return api.post<TrackedApplication>("/applications", payload);
}

/** PATCH /api/applications/{id} - update manual status/reminder fields. */
export function updateApplication(
  id: string,
  payload: ApplicationUpdatePayload
): Promise<TrackedApplication> {
  return api.patch<TrackedApplication>(`/applications/${id}`, payload);
}

/** DELETE /api/applications/{id} - stop tracking an application locally. */
export function deleteApplication(id: string): Promise<void> {
  return api.delete<void>(`/applications/${id}`);
}
