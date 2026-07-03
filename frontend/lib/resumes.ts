/**
 * Resume API helpers — thin wrappers over the `/api/resumes/*` contract
 * (design.md §4.2). Mirrors the style of `lib/auth.ts`: drive the endpoints and
 * return the typed shapes the backend reports.
 *
 * The session rides along in an HTTP-only cookie (see `lib/api.ts`), so these
 * helpers never touch tokens.
 */

import { api, ApiError } from "@/lib/api";
import type { ParsedResume, ResumeVersion } from "@/lib/types";

// Base URL resolution mirrors lib/api.ts: same-origin in the browser (behind
// Caddy), configurable for dev. The PDF export returns a binary body, which the
// JSON-oriented apiFetch cannot surface, so this one call goes direct — while
// still riding the same session cookie via credentials: "include".
const API_BASE_URL =
  typeof window === "undefined"
    ? process.env.INTERNAL_API_BASE_URL ?? "http://backend:8000"
    : process.env.NEXT_PUBLIC_API_BASE_URL ?? "";

/**
 * A resume as returned by the backend (`ResumeOut`). Richer than the shared
 * `Resume` in `lib/types.ts` — it carries upload metadata too. Defined here so
 * the resume feature stays self-contained.
 */
export interface ResumeDetail {
  id: string;
  title: string;
  original_filename: string;
  content_type: string;
  file_size: number;
  extracted_text: string | null;
  parsed_json: ParsedResume | null;
  is_default: boolean;
  current_version_id?: string | null;
  current_version?: ResumeVersion | null;
  version_count?: number;
  created_at: string;
  updated_at: string;
}


export interface ResumeUpdatePayload {
  title?: string;
  extracted_text?: string;
  is_default?: boolean;
}

export interface ResumeVersionUpdatePayload {
  title?: string;
  extracted_text?: string;
}

export interface ResumeVersionDuplicatePayload {
  title?: string;
  source_version_id?: string;
}

/** GET /api/resumes — list the current user's resumes (newest first). */
export function listResumes(): Promise<ResumeDetail[]> {
  return api.get<ResumeDetail[]>("/resumes");
}

/** GET /api/resumes/{id} — fetch one resume incl. parsed sections. */
export function getResume(id: string): Promise<ResumeDetail> {
  return api.get<ResumeDetail>(`/resumes/${id}`);
}

/** POST /api/resumes/upload — multipart upload; extracts + parses server-side. */
export function uploadResume(file: File): Promise<ResumeDetail> {
  const form = new FormData();
  form.append("file", file);
  return api.upload<ResumeDetail>("/resumes/upload", form);
}

/** PATCH /api/resumes/{id} — edit title / extracted_text / default flag. */
export function updateResume(
  id: string,
  payload: ResumeUpdatePayload
): Promise<ResumeDetail> {
  return api.patch<ResumeDetail>(`/resumes/${id}`, payload);
}

/** DELETE /api/resumes/{id} — removes the row and the stored file. */
export function deleteResume(id: string): Promise<void> {
  return api.delete<void>(`/resumes/${id}`);
}

/** POST /api/resumes/{id}/parse - re-run the AI section parse. */
export function reparseResume(id: string): Promise<ResumeDetail> {
  return api.post<ResumeDetail>(`/resumes/${id}/parse`);
}

/** GET /api/resumes/{id}/versions - list versions in one resume family. */
export function listResumeVersions(resumeId: string): Promise<ResumeVersion[]> {
  return api.get<ResumeVersion[]>(`/resumes/${resumeId}/versions`);
}

/** POST /api/resumes/{id}/versions - duplicate a resume version. */
export function duplicateResumeVersion(
  resumeId: string,
  payload: ResumeVersionDuplicatePayload = {}
): Promise<ResumeVersion> {
  return api.post<ResumeVersion>(`/resumes/${resumeId}/versions`, payload);
}

/** PATCH /api/resumes/{id}/versions/{versionId} - edit version source text. */
export function updateResumeVersion(
  resumeId: string,
  versionId: string,
  payload: ResumeVersionUpdatePayload
): Promise<ResumeVersion> {
  return api.patch<ResumeVersion>(
    `/resumes/${resumeId}/versions/${versionId}`,
    payload
  );
}

/** POST /api/resumes/{id}/versions/{versionId}/current - make a version current. */
export function makeResumeVersionCurrent(
  resumeId: string,
  versionId: string
): Promise<ResumeDetail> {
  return api.post<ResumeDetail>(
    `/resumes/${resumeId}/versions/${versionId}/current`
  );
}

/** DELETE /api/resumes/{id}/versions/{versionId} - remove a non-current version. */
export function deleteResumeVersion(
  resumeId: string,
  versionId: string
): Promise<void> {
  return api.delete<void>(`/resumes/${resumeId}/versions/${versionId}`);
}

/** POST /api/resumes/{id}/versions/{versionId}/parse - re-parse one version. */
export function reparseResumeVersion(
  resumeId: string,
  versionId: string
): Promise<ResumeVersion> {
  return api.post<ResumeVersion>(
    `/resumes/${resumeId}/versions/${versionId}/parse`
  );
}

/**
 * GET /api/resumes/{id}/export.pdf — fetch the rendered PDF as a Blob so the
 * browser can trigger a download. Goes direct (not through apiFetch) because the
 * body is binary, but sends the session cookie just the same.
 */
export async function fetchResumePdf(id: string): Promise<Blob> {
  const res = await fetch(`${API_BASE_URL}/api/resumes/${id}/export.pdf`, {
    method: "GET",
    credentials: "include",
  });
  if (!res.ok) {
    throw new ApiError(res.status, res.statusText || "Export failed");
  }
  return res.blob();
}

/** GET /api/resumes/{id}/versions/{versionId}/export.pdf - export one version. */
export async function fetchResumeVersionPdf(
  resumeId: string,
  versionId: string
): Promise<Blob> {
  const res = await fetch(
    `${API_BASE_URL}/api/resumes/${resumeId}/versions/${versionId}/export.pdf`,
    { method: "GET", credentials: "include" }
  );
  if (!res.ok) {
    throw new ApiError(res.status, res.statusText || "Export failed");
  }
  return res.blob();
}
