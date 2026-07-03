# JobGoblin Detailed Design Specification

Status: implementation reference; merged MVP feature set documented; integrated runtime/OAuth/tunnel validation still required. Target: V1 MVP. Last updated: 2026-07-03.

This is the durable design reference for the data model, API contract, auth, AI layer, scoring approach, parsing pipeline, deployment, and testing. See `docs/architecture.md` for the shorter architecture companion and `docs/roadmap.md` for phase sequencing.

## 1. Principles

1. JobGoblin is a private productivity tool, never a spam or auto-apply bot.
2. Every external action, including email, outreach, and applying, requires explicit human approval.
3. AI may rephrase, emphasize, and reorganize truthful user-provided content, but must never invent experience, skills, education, credentials, employers, or dates.
4. ATS-style scores are estimates and must be labelled as estimates.
5. Multi-user data is isolated by `user_id`; user-owned queries must be scoped by the current user.

## 2. System Topology

The app is self-hosted on the owner's laptop in one Docker Compose stack. Caddy is the local public entry point and serves a single browser origin:

```text
Browser
  |
  | http://localhost:8080 now; optional HTTPS tunnel profile
  v
Caddy reverse proxy
  |-- /      -> Next.js frontend
  `-- /api/* -> FastAPI backend
                  |-- PostgreSQL volume
                  |-- uploads volume
                  `-- Ollama container
```

The same-origin design lets auth use HTTP-only SameSite=Lax cookies without CORS or cross-site cookie workarounds. Cookie `Secure` is disabled in local development and enabled outside development.

External access through Cloudflare Tunnel is scaffolded as an optional compose profile, with HTTPS/runtime smoke validation still pending. Availability is laptop-bound; state persists in Docker volumes.

## 3. Current Implementation Status

Implemented now:

- Backend app wiring, settings, liveness and DB readiness endpoints, error envelope, route auto-discovery, migrations, startup admin seed.
- Email/password auth, admin-created invite tokens, invite-only signup, Google OAuth plumbing, email allowlist, TOTP MFA, rate limiting, environment-aware cookies.
- SQLModel tables for the V1 domain model.
- Resume upload, storage, text extraction, AI parse, edit/list/detail/delete, and PDF export.
- Jobs CRUD API and jobs list/create/detail/edit/delete UI.
- Contacts, applications, dashboard, resume-to-job analysis, cover-letter draft, profile builder, follow-up reminder, tailored resume drafts, review-only outreach, email export, discovery, and interview prep APIs.
- Contacts, applications, dashboard, jobs, resumes, discovery, job-detail analysis/cover-letter/tailored-draft/interview-prep panels, outreach, and profile frontend screens.
- Optional Cloudflare Tunnel compose profile, disabled by default.
- Runtime operator tooling for Ollama checks, DB readiness, smoke tests, Adzuna operator smoke, Cloudflare Tunnel/OAuth checks, backup/restore, migration/rollback, secrets, and release promotion.
- CI for backend ruff/pytest, frontend lint/build, and the merged E2E harness.

Remaining validation work:

- Integrated browser workflow validation against the production Compose stack.
- Real local AI verification with `AI_PROVIDER=ollama` and the installed local model.
- Google OAuth, allowlist, HTTPS tunnel, and secure-cookie validation with real credentials.

Review posture:

- External sending is not implemented as a silent side effect. Email, recruiter outreach, and applying must stay explicit and approval-gated.
- AI output must remain grounded in user-provided facts and scoped to the authenticated `user_id`.

## 4. Data Model

PostgreSQL via SQLModel and Alembic. Primary keys are UUIDs. User-owned tables include `user_id` and should cascade on user deletion. Cross-user object access should return 404 or 401 without leaking object existence.

### Core Tables

`users`

- Stores email, password hash, display name, admin flag, Google subject, TOTP state, and timestamps.
- First admin can be seeded from `ADMIN_EMAIL` and `ADMIN_PASSWORD`.

`invite_tokens`

- Supports private/invite-only registration.
- Tracks creator, optional used-by user, expiry, and created timestamp.

`profiles`

- Stores one editable private user profile seeded from parsed resume sections or maintained manually.
- Keeps profile facts scoped to the authenticated `user_id` and available for grounded generation workflows.

`resumes`

- Stores title, original filename, content type, size, opaque file key, extracted text, parsed JSON, default flag, and timestamps.
- Files are stored through the storage interface; raw paths are not exposed to clients.

`resume_versions`

- Stores editable resume versions with title, extracted text, parsed JSON, current-version flag, and timestamps.
- Preserves uploaded source facts on `resumes` while allowing role-specific edits and exports from the current version.

`jobs`

- Stores company, title, location, work mode, source, source URL, job description, salary range, currency, priority, and timestamps.
- Pipeline state does not live here; it lives on `applications`.

`job_analyses`

- Stores resume/job pair, overall score, category scores, matched keywords, missing keyword metadata, recommendations, explanation, provider/model, and timestamp.
- Scores are estimates.

`cover_letters`

- Stores job, resume, content, tone, workflow status, and timestamps.
- No sending happens from this table without an explicit later review-gated workflow.

`applications`

- Stores job, optional resume, optional cover letter, pipeline status, applied date, follow-up date, notes, and timestamps.
- Enforces one application per `(user_id, job_id)`.

`contacts`

- Stores optional job link, contact identity fields, company/role/email/LinkedIn URL, notes, contacted flag, and timestamps.

`outreach_messages`

- Stores optional job/contact links, channel, message type, content, workflow status, and timestamps.
- Draft/review statuses are expected before any external action.

`activity_events`

- Stores entity type/id, event type, description, metadata, and timestamp for timelines and dashboard activity.

### Enums

- `work_mode`: `onsite`, `remote`, `hybrid`, `unknown`
- `job_source`: `linkedin`, `company_site`, `indeed`, `referral`, `recruiter`, `other`
- `priority`: `low`, `medium`, `high`
- `application_status`: `saved`, `interested`, `resume_tailored`, `cover_letter_created`, `applied`, `contacted_recruiter`, `referred`, `phone_screen`, `technical_interview`, `final_interview`, `offer`, `rejected`, `withdrawn`, `archived`
- `cover_letter_tone`: `professional`, `friendly`, `concise`, `enthusiastic`
- `cover_letter_status`: `draft`, `reviewed`, `accepted`, `rejected`, `exported`
- `outreach_channel`: `email`, `linkedin`, `other`
- `outreach_status`: `draft`, `copied`, `sent`, `replied`, `closed`

Tailored resume drafts reuse `resume_versions` with `job_id`, `source_version_id`, and grounded tailoring metadata in `parsed_json`. Email drafts reuse `outreach_messages`; generated content remains local and export-only.

## 5. API Contract

Base path: `/api`. JSON in/out unless noted. Auth uses HTTP-only session cookies. Error responses use `{ "detail": "...", "code": "..." }` where routes provide a machine code.

### Implemented Endpoints

Health:

- `GET /api/health`
- `GET /api/health/ready`

Auth:

- `POST /api/auth/register`
- `POST /api/auth/login`
- `POST /api/auth/logout`
- `GET /api/auth/me`
- `GET /api/auth/google/login`
- `GET /api/auth/google/callback`
- `GET /api/auth/mfa/enroll`
- `POST /api/auth/mfa/verify`
- `POST /api/auth/mfa/challenge`

Resumes:

- `POST /api/resumes/upload` with multipart PDF/DOCX upload.
- `GET /api/resumes`
- `GET /api/resumes/{id}`
- `PATCH /api/resumes/{id}`
- `DELETE /api/resumes/{id}`
- `POST /api/resumes/{id}/parse`
- `GET /api/resumes/{id}/export.pdf`
- `GET /api/resumes/{id}/versions/{version_id}/export.pdf`

Jobs:

- `POST /api/jobs`
- `GET /api/jobs`
- `GET /api/jobs/{id}`
- `PATCH /api/jobs/{id}`
- `DELETE /api/jobs/{id}`
- `GET /api/jobs/{job_id}/analysis`
- `GET /api/jobs/{job_id}/resume-drafts`
- `POST /api/jobs/{job_id}/resume-drafts`

Admin invites:

- `GET /api/invites`
- `POST /api/invites`

Analysis:

- `POST /api/analysis/resume-job`
- `GET /api/analysis/{id}`

Cover letters:

- `GET /api/cover-letters`
- `POST /api/cover-letters`
- `GET /api/cover-letters/{id}`
- `PATCH /api/cover-letters/{id}`

Profile:

- `GET /api/profile`
- `PUT /api/profile`
- `POST /api/profile/seed`
- `DELETE /api/profile`

Applications:

- `GET /api/applications`
- `GET /api/applications/follow-ups`
- `POST /api/applications`
- `GET /api/applications/{id}`
- `PATCH /api/applications/{id}`
- `DELETE /api/applications/{id}`

Contacts:

- `GET /api/contacts`
- `POST /api/contacts`
- `GET /api/contacts/{id}`
- `PATCH /api/contacts/{id}`
- `DELETE /api/contacts/{id}`

Outreach:

- `GET /api/outreach`
- `POST /api/outreach`
- `GET /api/outreach/{id}`
- `PATCH /api/outreach/{id}`
- `DELETE /api/outreach/{id}`
- `POST /api/outreach/{id}/email-export`

Dashboard:

- `GET /api/dashboard/summary`
- `GET /api/dashboard/activity`

Implemented workflow endpoints also include:

- `POST /api/jobs/{job_id}/resume-drafts`
- `GET /api/jobs/{job_id}/resume-drafts`
- `GET /api/resumes/{resume_id}/versions/{version_id}/export.pdf`
- `GET /api/applications/{application_id}/workflow`
- `POST /api/outreach/generate`
- `POST /api/outreach/{outreach_id}/email-export`
- `GET /api/interview-prep`
- `POST /api/interview-prep`
- `GET /api/interview-prep/{prep_id}`
- `PATCH /api/interview-prep/{prep_id}`
- `GET /api/discovery/preferences`
- `PUT /api/discovery/preferences`
- `GET /api/discovery/runs`
- `POST /api/discovery/runs`
- `GET /api/discovery/results`
- `PATCH /api/discovery/results/{result_id}`
- `POST /api/discovery/results/{result_id}/save`

## 6. Authentication And Isolation

- Password hashes use argon2id.
- Session tokens are signed JWTs in `jg_session` HTTP-only cookies.
- MFA challenge state uses a separate pending cookie/token path.
- Google OAuth state uses Starlette SessionMiddleware in a separate short-lived signed cookie.
- Registration requires a valid unused invite token, except startup admin seed.
- Google sign-in is fail-closed unless OAuth credentials and allowlisted emails are configured.
- Every user-owned query must filter by the authenticated `user_id`.
- File access must always be authenticated and ownership checked.
- Logs must not include resume text, secrets, tokens, or sensitive profile data.

## 7. AI Provider Layer

The backend uses a small provider abstraction so AI can be swapped and tests can stay deterministic.

```python
class AIProvider(ABC):
    async def generate_text(self, prompt: str, *, system: str | None = None) -> str: ...
    async def generate_json(self, prompt: str, schema: dict, *, system: str | None = None) -> dict: ...
```

Providers:

- `OllamaProvider`: real local model calls through `OLLAMA_BASE_URL`.
- `MockProvider`: deterministic canned output for tests and fast local iteration.

Important config:

```dotenv
AI_PROVIDER=ollama
OLLAMA_BASE_URL=http://ollama:11434
OLLAMA_MODEL=qwen2.5:7b-instruct
OLLAMA_FAST_MODEL=llama3.2:3b
```

Prompt guardrails should be repeated in AI calls: no fabrication, distinguish missing keywords the user likely already qualifies for from true gaps, explain recommendations, and keep resume output ATS-plain.

## 8. Resume Parsing And Storage

Parsing pipeline:

1. Validate uploaded PDF/DOCX type and size (`MAX_UPLOAD_MB`, default 10).
2. Store the original file with an opaque key.
3. Extract text with pdfplumber for PDF and python-docx for DOCX.
4. Ask the AI provider for structured JSON sections when available.
5. Let the user edit extracted text and re-run parsing.
6. Export structured resume data to PDF when requested.

Storage interface:

```python
class StorageBackend(ABC):
    async def save(self, key: str, data: bytes, content_type: str) -> None: ...
    async def load(self, key: str) -> bytes: ...
    async def delete(self, key: str) -> None: ...
```

The MVP implementation is local filesystem storage mounted at `FILE_STORAGE_PATH`. Future S3/R2/MinIO support should preserve opaque keys and authenticated access.

## 9. Resume-To-Job Scoring Plan

The scoring feature is implemented and pending integrated validation.

Hybrid approach:

1. Extract job-description keywords and categories deterministically.
2. Extract resume terms from `extracted_text` and parsed skills.
3. Match exact terms first, then fuzzy terms with `rapidfuzz`.
4. Score weighted categories: keyword 30, skills 25, experience 20, role 10, education 5, formatting 10.
5. Use AI for explanation, recommendations, and missing-keyword classification.
6. Persist results to `job_analyses` and label UI output as an estimate.

Future upgrade: semantic matching through local embeddings after the deterministic MVP is working.

## 10. Configuration

`.env.example` documents committed config. `.env` is gitignored.

Key variables:

```dotenv
APP_ENV=development
APP_SECRET_KEY=change-me
DATABASE_URL=postgresql+psycopg://jobgoblin:jobgoblin@db:5432/jobgoblin
AI_PROVIDER=ollama
OLLAMA_BASE_URL=http://ollama:11434
FILE_STORAGE_PATH=/data/uploads
MAX_UPLOAD_MB=10
ADMIN_EMAIL=
ADMIN_PASSWORD=
FRONTEND_ORIGIN=http://localhost:3000
GOOGLE_CLIENT_ID=
GOOGLE_CLIENT_SECRET=
OAUTH_REDIRECT_BASE_URL=http://localhost:8080
ALLOWED_EMAILS=
TOTP_ISSUER=JobGoblin
JOB_DISCOVERY_PROVIDER=mock
ADZUNA_APP_ID=
ADZUNA_APP_KEY=
OBSERVABILITY_ENABLED=false
```

For fast local iteration, set `AI_PROVIDER=mock` and seed a local admin:

```dotenv
ADMIN_EMAIL=admin@jobgoblin.local
ADMIN_PASSWORD=goblin-demo-pass-123
```

## 11. Deployment

Current compose services:

| Service | Purpose | Notes |
|---------|---------|-------|
| `caddy` | Local entry point | Routes `/` to frontend and `/api/*` to backend. |
| `frontend` | Next.js app | Built from `frontend/`; uses standalone output. |
| `backend` | FastAPI API | Runs migrations on startup; mounts uploads volume. |
| `db` | PostgreSQL 16 | Uses `pgdata` Docker volume. |
| `ollama` | Local LLM runtime | Uses `ollama` Docker volume; model pull/setup is separate. |
| `cloudflared` | Optional tunnel profile | Disabled by default; requires `CLOUDFLARED_TUNNEL_TOKEN`. |

Pending validation:

- Host model pull and Ollama smoke for real local AI behavior.
- HTTPS tunnel validation for secure-cookie behavior.

## 12. Testing Strategy

Backend:

- `pytest` with a test PostgreSQL database on port 5433.
- `MockProvider` for AI tests.
- Coverage should prioritize auth branches, ownership isolation, migrations/model behavior, resume parsing/storage/export, and each CRUD module as it lands.
- `ruff check .` for linting.

Frontend:

- `npm run lint` and `npm run build` are required now.
- Keep Playwright smoke coverage focused on high-value browser workflows as the merged MVP stabilizes.

CI:

- `.github/workflows/ci.yml` runs backend ruff/pytest with a Postgres service and frontend lint/build on pull requests.

## 13. Repository Structure

```text
jobgoblin/
|-- backend/   # FastAPI app, models, schemas, routes, services, migrations, tests
|-- frontend/  # Next.js app, components, lib helpers, Dockerfile
|-- infra/     # Caddy and local access configuration
|-- docs/      # architecture, design, roadmap
|-- docker-compose.yml
|-- .env.example
|-- README.md
```

## 14. Decisions Log

Decided:

- Self-host on the owner's laptop for $0 hosting and local Ollama.
- Caddy same-origin routing for browser auth simplicity.
- Invite-only registration and fail-closed Google OAuth allowlist.
- TOTP MFA instead of SMS or email OTP.
- SQLModel and Alembic for the backend model/migration layer.
- Local storage abstraction for uploads.
- Deterministic plus AI scoring for explainable estimated match results.
- Pipeline status lives on `applications`, not `jobs`.

Resolved:

- Phase 0 local-login fixes are complete.
- Phase 1 delivery foundation is complete.
- Phase 2 core resource modules are implemented.
- Phase 3 resume-to-job analysis is implemented, pending integrated validation.
- Phase 4 tooling is in place, pending real runtime/tunnel smoke.
- Phase 5 has started with profile builder and follow-up reminders merged.
