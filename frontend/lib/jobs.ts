/**
 * Job API helpers. Thin wrappers over the `/api/jobs` CRUD contract.
 */

import { api } from "@/lib/api";
import type {
  Job,
  JobCreatePayload,
  JobImportPayload,
  JobUpdatePayload,
} from "@/lib/types";

/** GET /api/jobs - list the current user's saved jobs. */
export function listJobs(): Promise<Job[]> {
  return api.get<Job[]>("/jobs");
}

/** GET /api/jobs/{id} - fetch one saved job. */
export function getJob(id: string): Promise<Job> {
  return api.get<Job>(`/jobs/${id}`);
}

/** POST /api/jobs - create a saved job from pasted role details. */
export function createJob(payload: JobCreatePayload): Promise<Job> {
  return api.post<Job>("/jobs", payload);
}

/** POST /api/jobs/import - parse pasted job text or a job URL into editable fields. */
export function importJob(payload: JobImportPayload): Promise<JobCreatePayload> {
  return api.post<JobCreatePayload>("/jobs/import", payload);
}

/** PATCH /api/jobs/{id} - update editable job fields. */
export function updateJob(id: string, payload: JobUpdatePayload): Promise<Job> {
  return api.patch<Job>(`/jobs/${id}`, payload);
}

/** DELETE /api/jobs/{id} - remove a saved job. */
export function deleteJob(id: string): Promise<void> {
  return api.delete<void>(`/jobs/${id}`);
}
