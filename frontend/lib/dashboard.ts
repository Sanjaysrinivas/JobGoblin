/**
 * Dashboard API helpers. These call the authenticated dashboard endpoints and
 * keep placeholder/demo data out of the UI layer.
 */

import { api } from "@/lib/api";
import type { ActivityEvent, DashboardSummary } from "@/lib/types";

/** GET /api/dashboard/summary - aggregate counts and average analysis score. */
export function getDashboardSummary(): Promise<DashboardSummary> {
  return api.get<DashboardSummary>("/dashboard/summary");
}

/** GET /api/dashboard/activity - recent user activity for the dashboard feed. */
export function listDashboardActivity(): Promise<ActivityEvent[]> {
  return api.get<ActivityEvent[]>("/dashboard/activity");
}
