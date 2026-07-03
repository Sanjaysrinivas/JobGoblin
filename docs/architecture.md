# JobGoblin Architecture

A self-hosted, AI-powered job-search and application-management web app. This is
the text companion to [architecture.html](architecture.html), which contains the
same high-level system diagram in browser-friendly form.

## 1. Principles

- Private productivity tool, not a spam bot. Every external action such as email,
  recruiter outreach, or applying requires explicit human review and approval.
- Truthful AI. The AI may rephrase, emphasize, and reorganize the user's real
  content, but it must never invent experience, skills, education, or credentials.
- Estimated scores. ATS-style match scores are labelled estimates, never
  guaranteed ATS results.
- Multi-user isolation. User-owned rows are scoped to `user_id`.

## 2. Services

Two independently-built services communicate over HTTP/JSON and are served behind
one reverse proxy so the browser sees a single origin:

- Frontend: Next.js, React, TypeScript, Tailwind, shadcn/ui.
- Backend: FastAPI, Python, SQLModel, Alembic.

State and AI run as local containers alongside them:

- PostgreSQL: users, profiles, resumes, jobs, analyses, cover letters, applications, contacts, outreach messages, and activity data.
- File storage: uploaded resume files on a mounted local volume behind a storage
  interface, so object storage remains a later swap.
- Ollama: local LLM runtime. `MockProvider` is used for tests and fast dev.

## 3. Hosting

Everything runs in one Docker Compose stack on the owner's laptop (Ryzen 7,
31 GB RAM, RTX 4070 8 GB). External access is scaffolded through an optional Cloudflare
Tunnel compose profile, with HTTPS/runtime validation still pending. This keeps hosting at zero monthly cost while
letting the app use local Ollama.

| Component | Runs as | Cost |
|-----------|---------|------|
| Frontend / Backend | Containers behind Caddy, same origin | $0 |
| PostgreSQL | Container and Docker volume | $0 |
| Ollama | Container, GPU-capable when host tooling is enabled | $0 |
| File storage | Mounted Docker volume | $0 |
| Public access | Optional Cloudflare Tunnel profile; HTTPS validation still required | $0 |
| Repo / CI | GitHub Actions | $0 |

Trade-off: the app is online only while the laptop is on. All state persists on
Docker volumes across shutdowns. Because Caddy serves both services under one
hostname, session cookies can stay HTTP-only and SameSite=Lax without CORS hacks;
the Secure flag is used outside local development.

## 4. Data Model

Current tables include `users`, `invite_tokens`, and these user-owned tables
scoped to `user_id`:

`profiles`, `resumes`, `resume_versions`, `jobs`, `job_analyses`, `cover_letters`,
`applications`, `contacts`, `outreach_messages`, `activity_events`.

Deferred V2 tables: `tailored_resume_drafts`, `email_drafts`.

Operational probes:

- `GET /api/health`: liveness only; does not touch PostgreSQL.
- `GET /api/health/ready`: readiness; returns `503` when PostgreSQL cannot answer `SELECT 1`.

Application pipeline statuses: `saved`, `interested`, `resume_tailored`,
`cover_letter_created`, `applied`, `contacted_recruiter`, `referred`,
`phone_screen`, `technical_interview`, `final_interview`, `offer`, `rejected`,
`withdrawn`, `archived`.

## 5. Core AI Flow: Resume To Job Analysis

This is implemented and pending integrated validation. The resume upload, storage, extraction, parsing, PDF export, and job-description comparison flow are in place, with final integrated smoke still pending.

1. User uploads a resume; backend stores the file and extracts plain text.
2. User pastes a job description and selects a resume.
3. Deterministic pass extracts and normalizes keywords from both texts, then
   computes weighted category scores.
4. AI pass explains gaps, distinguishes keywords the user likely already
   qualifies for from qualifications they lack, and suggests truthful changes.
5. Persist numeric score, matched/missing keywords, explanation, and
   recommendations.
6. User saves the job to the tracker, creates local review-only drafts as needed, and advances the application through the pipeline with optional follow-up reminders.

## 6. Branching Workflow

`main -> dev -> feature/*`

- `main`: release-ready branch.
- `dev`: integration branch, promoted to `main` only after the runbook release checks pass or are explicitly marked pending when they require real external credentials.
- `feature/*`: one branch per unit of work, branched off `dev`, merged via PR.
