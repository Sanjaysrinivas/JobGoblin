/**
 * Job discovery API helpers. Thin wrappers over `/api/discovery`.
 */

import { api } from "@/lib/api";
import type {
  DiscoveryResultStatus,
  Job,
  JobSearchPreferences,
  JobSearchPreferencesPayload,
  JobSearchResult,
  JobSearchRun,
  JobSearchRunCreate,
} from "@/lib/types";

export function getDiscoveryPreferences(): Promise<JobSearchPreferences | null> {
  return api.get<JobSearchPreferences | null>("/discovery/preferences");
}

export function saveDiscoveryPreferences(
  payload: JobSearchPreferencesPayload
): Promise<JobSearchPreferences> {
  return api.put<JobSearchPreferences>("/discovery/preferences", payload);
}

export function createDiscoveryRun(
  payload: JobSearchRunCreate
): Promise<JobSearchRun> {
  return api.post<JobSearchRun>("/discovery/runs", payload);
}

export function listDiscoveryResults(
  status: DiscoveryResultStatus = "new"
): Promise<JobSearchResult[]> {
  return api.get<JobSearchResult[]>(`/discovery/results?status=${status}`);
}

export function updateDiscoveryResult(
  id: string,
  status: DiscoveryResultStatus
): Promise<JobSearchResult> {
  return api.patch<JobSearchResult>(`/discovery/results/${id}`, { status });
}

export function saveDiscoveryResult(id: string): Promise<Job> {
  return api.post<Job>(`/discovery/results/${id}/save`);
}
