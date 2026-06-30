/**
 * Shared types for the JobGoblin API contract (docs/design.md §3–4).
 *
 * These mirror the backend's JSON shapes. The backend is built in parallel on
 * another branch; treat this file as the agreed contract until both merge.
 */

// ---------------------------------------------------------------------------
// Enumerations (design.md §3.1)
// ---------------------------------------------------------------------------

export type ApplicationStatus =
  | "saved"
  | "applied"
  | "interviewing"
  | "offer"
  | "rejected"
  | "withdrawn";

export type CoverLetterStatus = "draft" | "final";

export type OutreachChannel = "email" | "linkedin" | "other";

export type OutreachMessageType =
  | "intro"
  | "follow_up"
  | "thank_you"
  | "referral_request";

// ---------------------------------------------------------------------------
// Core resources
// ---------------------------------------------------------------------------

export interface User {
  id: string;
  email: string;
  created_at: string;
}

export interface Resume {
  id: string;
  title: string;
  is_default: boolean;
  extracted_text: string;
  parsed_json: ParsedResume | null;
  created_at: string;
  updated_at: string;
}

export interface ParsedResume {
  summary: string | null;
  skills: string[];
  experience: ParsedExperience[];
  education: ParsedEducation[];
  projects: string[];
  certifications: string[];
}

export interface ParsedExperience {
  company: string;
  role: string;
  start: string | null;
  end: string | null;
  highlights: string[];
}

export interface ParsedEducation {
  institution: string;
  credential: string;
  year: string | null;
}

export interface Job {
  id: string;
  title: string;
  company: string;
  location: string | null;
  url: string | null;
  description: string;
  created_at: string;
}

export interface JobAnalysis {
  id: string;
  job_id: string;
  resume_id: string;
  overall_score: number;
  category_scores: {
    keyword: number;
    skills: number;
    experience: number;
    role: number;
    education: number;
    formatting: number;
  };
  matched_keywords: string[];
  missing_keywords: MissingKeyword[];
  explanation: string;
  recommendations: string[];
  created_at: string;
}

export interface MissingKeyword {
  term: string;
  likely_qualified: boolean;
}

export interface CoverLetter {
  id: string;
  job_id: string;
  resume_id: string;
  tone: string;
  content: string;
  status: CoverLetterStatus;
  created_at: string;
}

export interface Application {
  id: string;
  job_id: string;
  status: ApplicationStatus;
  applied_at: string | null;
  follow_up_at: string | null;
  notes: string | null;
  created_at: string;
  updated_at: string;
}

export interface Contact {
  id: string;
  name: string;
  email: string | null;
  company: string | null;
  role: string | null;
  linkedin_url: string | null;
  notes: string | null;
  created_at: string;
}

export interface Outreach {
  id: string;
  contact_id: string | null;
  job_id: string | null;
  channel: OutreachChannel;
  message_type: OutreachMessageType;
  content: string;
  created_at: string;
}

// ---------------------------------------------------------------------------
// Dashboard (design.md §4.4)
// ---------------------------------------------------------------------------

export interface DashboardSummary {
  saved: number;
  applied: number;
  interviewing: number;
  offers: number;
  follow_ups_due: number;
  avg_score: number | null;
}

export interface ActivityEvent {
  id: string;
  kind: string;
  message: string;
  occurred_at: string;
}

// ---------------------------------------------------------------------------
// Request payloads
// ---------------------------------------------------------------------------

export interface LoginPayload {
  email: string;
  password: string;
}

export interface RegisterPayload extends LoginPayload {
  invite_token: string;
}

// ---------------------------------------------------------------------------
// Error envelope (design.md §4)
// ---------------------------------------------------------------------------

export interface ApiErrorBody {
  detail: string;
  code?: string;
}
