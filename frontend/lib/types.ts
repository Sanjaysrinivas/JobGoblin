/**
 * Shared types for the JobGoblin API contract (docs/design.md sections 3-4).
 * These mirror the backend JSON shapes currently implemented or specified.
 */

// ---------------------------------------------------------------------------
// Enumerations (design.md section 3.1)
// ---------------------------------------------------------------------------

export type WorkMode = "onsite" | "remote" | "hybrid" | "unknown";

export type JobSource =
  | "linkedin"
  | "company_site"
  | "indeed"
  | "referral"
  | "recruiter"
  | "other";

export type Priority = "low" | "medium" | "high";

export type ApplicationStatus =
  | "saved"
  | "interested"
  | "resume_tailored"
  | "cover_letter_created"
  | "applied"
  | "contacted_recruiter"
  | "referred"
  | "phone_screen"
  | "technical_interview"
  | "final_interview"
  | "offer"
  | "rejected"
  | "withdrawn"
  | "archived";

export type CoverLetterTone =
  | "professional"
  | "friendly"
  | "concise"
  | "enthusiastic";

export type CoverLetterStatus =
  | "draft"
  | "reviewed"
  | "accepted"
  | "rejected"
  | "exported";

export type OutreachChannel = "email" | "linkedin" | "other";

export type OutreachStatus = "draft" | "copied" | "sent" | "replied" | "closed";

export type DiscoveryRunStatus = "pending" | "completed" | "failed";

export type DiscoveryResultStatus = "new" | "saved" | "dismissed" | "blocked";

export type InterviewPrepStatus =
  | "draft"
  | "reviewed"
  | "ready"
  | "archived";

// ---------------------------------------------------------------------------
// Auth
// ---------------------------------------------------------------------------

export interface User {
  id: string;
  email: string;
  display_name: string;
  is_admin: boolean;
}

export interface SessionUser extends User {
  mfa_enrollment_required?: boolean;
}

export interface MfaRequiredResponse {
  mfa_required: true;
}

export type PrimaryAuthResponse = SessionUser | MfaRequiredResponse;

// ---------------------------------------------------------------------------
// Core resources
// ---------------------------------------------------------------------------

export interface Resume {
  id: string;
  title: string;
  original_filename: string;
  content_type: string;
  file_size: number;
  is_default: boolean;
  current_version_id?: string | null;
  current_version?: ResumeVersion | null;
  version_count?: number;
  extracted_text: string | null;
  parsed_json: ParsedResume | null;
  created_at: string;
  updated_at: string;
}

export interface ResumeVersion {
  id: string;
  resume_id: string;
  job_id?: string | null;
  title: string;
  original_filename?: string | null;
  content_type?: string | null;
  file_size?: number | null;
  extracted_text: string | null;
  parsed_json: ParsedResume | null;
  is_current: boolean;
  source_version_id: string | null;
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
  company_name: string;
  title: string;
  location: string | null;
  work_mode: WorkMode;
  source: JobSource;
  source_url: string | null;
  description: string;
  salary_min: number | null;
  salary_max: number | null;
  currency: string | null;
  priority: Priority;
  created_at: string;
  updated_at: string;
}

export interface JobCreatePayload {
  company_name: string;
  title: string;
  location?: string | null;
  work_mode?: WorkMode;
  source?: JobSource;
  source_url?: string | null;
  description: string;
  salary_min?: number | null;
  salary_max?: number | null;
  currency?: string | null;
  priority?: Priority;
}

export type JobUpdatePayload = Partial<JobCreatePayload>;

export interface JobSearchPreferences {
  id?: string;
  target_countries: string[];
  target_locations: string[];
  desired_titles: string[];
  seniority?: string | null;
  industries: string[];
  required_keywords: string[];
  optional_keywords: string[];
  excluded_keywords: string[];
  visa_sponsorship_required: boolean;
  blocked_companies: string[];
  work_mode: WorkMode;
  created_at?: string;
  updated_at?: string;
}

export type JobSearchPreferencesPayload = Omit<
  JobSearchPreferences,
  "id" | "created_at" | "updated_at"
>;

export interface JobSearchRunCreate {
  country?: string | null;
  location?: string | null;
  query?: string | null;
  provider?: string | null;
  results_per_page?: number;
}

export interface JobSearchRun {
  id: string;
  provider: string;
  status: DiscoveryRunStatus;
  country: string;
  location: string | null;
  query: string;
  preferences_snapshot: Record<string, unknown>;
  result_count: number;
  error: string | null;
  created_at: string;
  updated_at: string;
}

export interface JobSearchResult {
  id: string;
  run_id: string;
  provider: string;
  source: JobSource;
  source_url: string | null;
  title: string;
  company_name: string;
  location: string | null;
  work_mode: WorkMode;
  description: string;
  posted_at: string | null;
  fit_score: number;
  fit_reason: string | null;
  status: DiscoveryResultStatus;
  saved_job_id: string | null;
  created_at: string;
  updated_at: string;
}

export interface JobAnalysis {
  id: string;
  job_id: string;
  resume_id: string;
  overall_score: number;
  keyword_score: number;
  skills_score: number;
  experience_score: number;
  role_score: number;
  education_score: number;
  formatting_score: number;
  matched_keywords: string[] | null;
  missing_keywords: string[] | null;
  explanation: string | null;
  recommendations: string[] | null;
  provider: string;
  model_used: string;
  created_at: string;
}

export interface CoverLetter {
  id: string;
  job_id: string;
  resume_id: string;
  tone: CoverLetterTone;
  content: string;
  status: CoverLetterStatus;
  created_at: string;
  updated_at: string;
}

export interface Application {
  id: string;
  job_id: string;
  resume_id: string | null;
  cover_letter_id: string | null;
  status: ApplicationStatus;
  applied_at: string | null;
  follow_up_at: string | null;
  notes: string | null;
  created_at: string;
  updated_at: string;
}

export interface ApplicationWorkflowResume {
  id: string;
  title: string;
  current_version_id: string | null;
}

export interface ApplicationWorkflowActivity {
  entity_type: string;
  entity_id: string;
  event_type: string;
  description: string | null;
  created_at: string;
}

export interface ApplicationWorkflow {
  application: Application;
  job: Job;
  linked_resume: ApplicationWorkflowResume | null;
  linked_cover_letter: CoverLetter | null;
  cover_letters: CoverLetter[];
  contacts: Contact[];
  outreach_drafts: Outreach[];
  recent_activity: ApplicationWorkflowActivity[];
}

export interface Contact {
  id: string;
  job_id: string | null;
  name: string;
  email: string | null;
  company: string | null;
  role: string | null;
  linkedin_url: string | null;
  notes: string | null;
  contacted: boolean;
  created_at: string;
  updated_at: string;
}

export interface ContactCreatePayload {
  job_id?: string | null;
  name: string;
  email?: string | null;
  company?: string | null;
  role?: string | null;
  linkedin_url?: string | null;
  notes?: string | null;
  contacted?: boolean;
}

export type ContactUpdatePayload = Partial<ContactCreatePayload>;

export interface Outreach {
  id: string;
  contact_id: string | null;
  job_id: string | null;
  channel: OutreachChannel;
  message_type: string;
  content: string;
  status: OutreachStatus;
  created_at: string;
  updated_at: string;
}

export interface OutreachEmailExport {
  to: string | null;
  subject: string;
  body: string;
  text: string;
  filename: string;
  mailto_url: string;
}

export interface OutreachCreatePayload {
  job_id?: string | null;
  contact_id?: string | null;
  channel?: OutreachChannel;
  message_type: string;
  content: string;
  status?: OutreachStatus;
}

export type OutreachUpdatePayload = Partial<OutreachCreatePayload>;

export interface UserProfile {
  id: string;
  source_resume_id: string | null;
  full_name: string | null;
  headline: string | null;
  location: string | null;
  website_url: string | null;
  linkedin_url: string | null;
  summary: string | null;
  skills: string[];
  experience: ParsedExperience[];
  education: ParsedEducation[];
  projects: string[];
  certifications: string[];
  created_at: string;
  updated_at: string;
}

export interface UserProfilePayload {
  full_name?: string | null;
  headline?: string | null;
  location?: string | null;
  website_url?: string | null;
  linkedin_url?: string | null;
  summary?: string | null;
  skills?: string[];
  experience?: ParsedExperience[];
  education?: ParsedEducation[];
  projects?: string[];
  certifications?: string[];
}


export interface InterviewPrepQuestion {
  question: string;
  category: string;
  why: string;
  answer_outline: string;
  evidence: string[];
}

export interface InterviewPrep {
  id: string;
  job_id: string;
  application_id: string | null;
  resume_id: string | null;
  resume_version_id: string | null;
  status: InterviewPrepStatus;
  notes: string | null;
  questions: InterviewPrepQuestion[];
  provider: string;
  model_used: string;
  created_at: string;
  updated_at: string;
}
// ---------------------------------------------------------------------------
// Dashboard (design.md section 4.4)
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
  entity_type: string;
  entity_id: string;
  event_type: string;
  description: string | null;
  metadata: Record<string, unknown> | null;
  created_at: string;
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
// Error envelope (design.md section 4)
// ---------------------------------------------------------------------------

export interface ApiErrorBody {
  detail: string;
  code?: string;
}

