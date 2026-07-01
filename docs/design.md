# JobGoblin — Detailed Design Specification

> The "measure twice" document. This locks the data model, API contract, auth,
> AI layer, scoring algorithm, parsing approach, deployment, and testing *before*
> application code is written. Companion to [`architecture.md`](architecture.md).

**Status:** implementation reference · **Target:** V1 MVP · **Last updated:** 2026-07-01

---

## 1. Principles (recap)

1. Private productivity tool — **never** a spam/auto-apply bot.
2. Every external action (email, outreach, applying) requires explicit human approval.
3. The AI **never invents** experience, skills, education, or credentials — it only
   rephrases, emphasizes, or reorganizes truthful, user-provided content.
4. ATS-style scores are **estimates**, clearly labelled as such.
5. **Multi-user** with hard data isolation — every row is scoped to a `user_id`.

---

## 2. System topology

Self-hosted on the owner's laptop (Ryzen 7 8845HS · 31 GB RAM · RTX 4070 8 GB),
all containers in one Docker Compose, with external access planned through a free Cloudflare Tunnel.

```
                        Internet (you + friends)
                               │  HTTPS
                               ▼
                    ┌──────────────────────┐
                    │  Cloudflare Tunnel    │  (cloudflared, free)
                    └──────────┬───────────┘
                               ▼
                    ┌──────────────────────┐
                    │  Caddy reverse proxy  │  one hostname → same-origin
                    │   /      → frontend   │
                    │   /api/* → backend    │
                    └─────┬───────────┬─────┘
                          ▼           ▼
                  ┌────────────┐ ┌────────────────────────┐
                  │ Next.js FE │ │ FastAPI BE              │
                  └────────────┘ │  ├─ Postgres (volume)   │
                                 │  ├─ uploads (volume)    │
                                 │  └─ Ollama (volume)     │
                                 └────────────────────────┘
```

**Key consequence:** because Caddy serves FE and BE under **one origin**, there is
**no cross-site cookie problem**. Session cookies are HTTP-only and SameSite=Lax; the Secure flag is used outside local development.
Availability is non-24/7 (laptop-bound); all state persists on Docker volumes.

---

## 3. Data model

PostgreSQL via **SQLModel** (SQLAlchemy core + Pydantic). Migrations via **Alembic**.
Primary keys are UUIDs. Every user-owned table has `user_id` with
`ON DELETE CASCADE` (satisfies the "delete all my data" requirement).

### 3.1 Enumerations

| Enum | Values |
|------|--------|
| `work_mode` | `onsite`, `remote`, `hybrid`, `unknown` |
| `job_source` | `linkedin`, `company_site`, `indeed`, `referral`, `recruiter`, `other` |
| `priority` | `low`, `medium`, `high` |
| `application_status` | `saved`, `interested`, `resume_tailored`, `cover_letter_created`, `applied`, `contacted_recruiter`, `referred`, `phone_screen`, `technical_interview`, `final_interview`, `offer`, `rejected`, `withdrawn`, `archived` |
| `cover_letter_tone` | `professional`, `friendly`, `concise`, `enthusiastic` |
| `cover_letter_status` | `draft`, `reviewed`, `accepted`, `rejected`, `exported` |
| `outreach_channel` | `email`, `linkedin`, `other` |
| `outreach_status` | `draft`, `copied`, `sent`, `replied`, `closed` |

### 3.2 Tables (V1 MVP)

**users**

| Column | Type | Notes |
|--------|------|-------|
| id | uuid | PK |
| email | citext | unique, lowercased |
| password_hash | text | argon2id |
| display_name | text | |
| is_admin | bool | default false; first user from env seed = admin |
| created_at / updated_at | timestamptz | |

**invite_tokens** (invite-only registration)

| Column | Type | Notes |
|--------|------|-------|
| id | uuid | PK |
| token | text | unique, random |
| created_by | uuid | FK users.id |
| used_by | uuid? | FK users.id, null until redeemed |
| expires_at | timestamptz | |
| created_at | timestamptz | |

**resumes**

| Column | Type | Notes |
|--------|------|-------|
| id | uuid | PK |
| user_id | uuid | FK users.id, CASCADE, **indexed** |
| title | text | |
| original_filename | text | |
| file_key | text | storage key (not a path the client sees) |
| content_type | text | `application/pdf` \| docx mime |
| file_size | int | bytes |
| extracted_text | text | plain text from the file |
| parsed_json | jsonb | structured sections (summary/skills/experience/…) |
| is_default | bool | one default per user (partial unique index) |
| created_at / updated_at | timestamptz | |

**jobs**

| Column | Type | Notes |
|--------|------|-------|
| id | uuid | PK |
| user_id | uuid | FK, CASCADE, indexed |
| company_name | text | |
| title | text | |
| location | text? | |
| work_mode | work_mode | default `unknown` |
| source | job_source | default `other` |
| source_url | text? | |
| description | text | pasted JD |
| salary_min / salary_max | int? | |
| currency | text? | ISO 4217 |
| priority | priority | default `medium` |
| created_at / updated_at | timestamptz | |

> Pipeline **status lives on `applications`**, not `jobs`, to avoid duplicate
> sources of truth (a job becomes an application when the user starts pursuing it).

**job_analyses**

| Column | Type | Notes |
|--------|------|-------|
| id | uuid | PK |
| user_id | uuid | FK, CASCADE, indexed |
| resume_id | uuid | FK resumes.id |
| job_id | uuid | FK jobs.id |
| overall_score | int | 0–100 |
| keyword_score / skills_score / experience_score / role_score / education_score / formatting_score | int | per-category 0–100 |
| matched_keywords | jsonb | string[] |
| missing_keywords | jsonb | `[{keyword, likely_qualified: bool}]` |
| recommendations | jsonb | string[] |
| explanation | text | AI narrative |
| provider / model_used | text | e.g. `ollama` / `qwen2.5:7b` |
| created_at | timestamptz | |

**cover_letters**

| Column | Type | Notes |
|--------|------|-------|
| id | uuid | PK |
| user_id | uuid | FK, CASCADE, indexed |
| job_id | uuid | FK jobs.id |
| resume_id | uuid | FK resumes.id |
| content | text | |
| tone | cover_letter_tone | |
| status | cover_letter_status | default `draft` |
| created_at / updated_at | timestamptz | |

**applications**

| Column | Type | Notes |
|--------|------|-------|
| id | uuid | PK |
| user_id | uuid | FK, CASCADE, indexed |
| job_id | uuid | FK jobs.id; unique per (user_id, job_id) |
| resume_id | uuid? | FK resumes.id |
| cover_letter_id | uuid? | FK cover_letters.id |
| status | application_status | default `saved`, indexed with user_id |
| applied_at | timestamptz? | |
| follow_up_at | timestamptz? | |
| notes | text? | |
| created_at / updated_at | timestamptz | |

**contacts**

| Column | Type | Notes |
|--------|------|-------|
| id | uuid | PK |
| user_id | uuid | FK, CASCADE, indexed |
| job_id | uuid? | FK jobs.id (optional link) |
| name | text | |
| company / role / email / linkedin_url | text? | |
| notes | text? | |
| contacted | bool | default false |
| created_at / updated_at | timestamptz | |

**outreach_messages**

| Column | Type | Notes |
|--------|------|-------|
| id | uuid | PK |
| user_id | uuid | FK, CASCADE, indexed |
| job_id | uuid? | FK jobs.id |
| contact_id | uuid? | FK contacts.id |
| channel | outreach_channel | |
| message_type | text | connection_note / follow_up / recruiter_email / referral / cold |
| content | text | |
| status | outreach_status | default `draft` |
| created_at / updated_at | timestamptz | |

**activity_events** (powers the timeline)

| Column | Type | Notes |
|--------|------|-------|
| id | uuid | PK |
| user_id | uuid | FK, CASCADE, indexed |
| entity_type | text | resume / job / application / … |
| entity_id | uuid | |
| event_type | text | resume_uploaded, analysis_completed, status_changed, … |
| description | text | |
| metadata | jsonb | |
| created_at | timestamptz | indexed |

### 3.3 Deferred to V2 (designed-for, not built yet)

`resume_versions`, `tailored_resume_drafts`, `email_drafts`. Schemas live in the
roadmap; tables are not created in V1 migrations.

---

## 4. API contract

Base path `/api`. JSON in/out. Auth via session cookie. Errors use a consistent
envelope: `{ "detail": "<message>", "code": "<machine_code>" }`. Standard codes:
`401` unauthenticated, `403` not owner, `404` not found, `409` conflict,
`422` validation, `429` rate-limited.

### 4.1 Auth

| Method | Path | Body | Returns |
|--------|------|------|---------|
| POST | `/api/auth/register` | `{email, password, invite_token}` | sets cookie; flat user object |
| POST | `/api/auth/login` | `{email, password}` | sets session and returns flat user with `mfa_enrollment_required`, or returns `{mfa_required: true}` with an MFA-pending cookie |
| POST | `/api/auth/logout` | — | clears cookie |
| GET | `/api/auth/me` | — | flat user object |

### 4.2 Resumes

| Method | Path | Notes |
|--------|------|-------|
| POST | `/api/resumes/upload` | multipart file (PDF/DOCX); extracts text, stores file, runs best-effort inline parse |
| GET | `/api/resumes` | list (current user only) |
| GET | `/api/resumes/{id}` | detail incl. parsed sections |
| PATCH | `/api/resumes/{id}` | edit title, extracted_text, is_default |
| DELETE | `/api/resumes/{id}` | removes row + stored file |
| POST | `/api/resumes/{id}/parse` | re-run AI section parse |

### 4.3 Jobs / Analysis / Cover letters

| Method | Path | Notes |
|--------|------|-------|
| POST / GET / GET{id} / PATCH{id} / DELETE{id} | `/api/jobs` | CRUD |
| POST | `/api/analysis/resume-job` | `{resume_id, job_id}` → runs scoring pipeline → `JobAnalysis` |
| GET | `/api/analysis/{id}` | fetch one |
| GET | `/api/jobs/{job_id}/analysis` | latest analysis for a job |
| POST | `/api/cover-letters` | `{job_id, resume_id, tone}` → generate |
| GET / PATCH | `/api/cover-letters/{id}` | fetch / edit content+status |

### 4.4 Applications / Contacts / Outreach / Dashboard

| Method | Path | Notes |
|--------|------|-------|
| POST / GET / GET{id} / PATCH{id} / DELETE{id} | `/api/applications` | CRUD; PATCH on status writes an `activity_event` |
| POST / GET / GET{id} / PATCH{id} / DELETE{id} | `/api/contacts` | CRUD |
| POST | `/api/outreach/generate` | `{job_id?, contact_id?, message_type, channel}` → draft |
| GET / PATCH | `/api/outreach/{id}` | fetch / edit |
| GET | `/api/dashboard/summary` | counts (saved/applied/interviews/offers/follow-ups due, avg score) |
| GET | `/api/dashboard/activity` | recent timeline events |

---

## 5. Authentication & multi-user security

- **Hashing:** argon2id (`argon2-cffi`).
- **Session:** signed JWT (`python-jose`) in an **HTTP-only, SameSite=Lax** cookie. The cookie is `Secure` outside local development. Same-origin (via Caddy) so no CORS/cross-site cookie issues.
- **Registration:** invite-only — `register` requires a valid, unused `invite_token`.
  First admin seeded from env (`ADMIN_EMAIL` / `ADMIN_PASSWORD`) on startup.
- **Isolation:** a FastAPI dependency `get_current_user()` resolves the user from the
  cookie; **every** repository query filters by `user_id`. Owner checks return `404`
  (not `403`) to avoid leaking existence.
- **File access:** files are served only through authenticated, ownership-checked
  endpoints — never by public path. Validate MIME + magic bytes; cap size at
  **10 MB** (`MAX_UPLOAD_MB`, configurable).
- **Rate limiting:** `slowapi` on AI endpoints (analysis, generation) to protect the
  single Ollama instance from pile-ups.
- **Logging:** never log resume text, emails, or secrets. Redact in production.

---

## 6. AI provider layer

A thin abstraction so the engine is swappable. Verified against the Ollama Python
client (`format` accepts a JSON schema; `temperature: 0` for determinism; async API).

```python
class AIProvider(ABC):
    async def generate_text(self, prompt: str, *, system: str | None = None) -> str: ...
    async def generate_json(self, prompt: str, schema: dict, *, system: str | None = None) -> dict: ...

class OllamaProvider(AIProvider):
    # uses ollama.AsyncClient(host=OLLAMA_BASE_URL)
    # generate_json -> chat(model, messages, format=schema, options={"temperature": 0})

class MockProvider(AIProvider):
    # deterministic canned responses for tests — zero external calls
```

- **Config:** `AI_PROVIDER=ollama`, `OLLAMA_BASE_URL=http://ollama:11434`,
  `OLLAMA_MODEL=qwen2.5:7b-instruct`, `OLLAMA_FAST_MODEL=llama3.2:3b`.
- **Models:** `qwen2.5:7b-instruct` for analysis/structured JSON; `llama3.2:3b` for
  light/fast generation. Pulled on first boot via an init step.
- **Prompt guardrails** (system prompt, every call): no fabrication; distinguish
  *missing keyword you already qualify for* vs *qualification you lack*; explain
  recommendations; keep resume output ATS-plain.

---

## 7. ATS-style scoring algorithm

Hybrid: **deterministic numeric score** + **AI reasoning**. Deterministic part keeps
the number explainable and reproducible; AI part adds judgement and language.

**Pipeline:**

1. **Extract JD keywords** — normalize text (lowercase, strip), pull candidate terms
   via n-gram + a curated skills/tech lexicon, plus capitalized/technical tokens.
2. **Extract resume terms** from `extracted_text` + `parsed_json.skills`.
3. **Match** — exact match first; then fuzzy via **`rapidfuzz`** (`token_set_ratio`
   ≥ threshold) to catch variants (e.g. "CI/CD" ≈ "continuous integration").
4. **Score by category** with the spec weights:
   keyword 30 · skills 25 · experience 20 · role 10 · education 5 · formatting 10.
5. **AI pass** (`generate_json`, schema-enforced) — produce `explanation`,
   `recommendations`, and classify each missing keyword `likely_qualified: bool`.
6. **Persist** numeric scores + AI output as a `JobAnalysis`; label as *estimate*.

**Dependencies:** `rapidfuzz` (fast fuzzy matching, no heavy NLP). A curated skills
lexicon ships as a data file. **V2 upgrade:** semantic matching via Ollama embeddings
(`nomic-embed-text`, ~270 MB — runs easily on the RTX 4070) for synonym-aware scoring.

---

## 8. Resume parsing

1. **Extract text** by type:
   - PDF → **`pdfplumber`** (good layout-aware extraction; `pypdf` fallback).
   - DOCX → **`python-docx`**.
2. Store original file (storage layer) + `extracted_text`.
3. **Section parse** — `generate_json` with a `ParsedResume` schema
   (summary, skills[], experience[], education[], projects[], certifications[]).
4. User can **edit** `extracted_text` and re-run parse (`POST /resumes/{id}/parse`)
   since extraction is never perfect.

---

## 9. File storage abstraction

```python
class StorageBackend(ABC):
    async def save(self, key: str, data: bytes, content_type: str) -> None: ...
    async def load(self, key: str) -> bytes: ...
    async def delete(self, key: str) -> None: ...

class LocalStorage(StorageBackend):   # MVP — mounted Docker volume at FILE_STORAGE_PATH
class S3Storage(StorageBackend):      # future — boto3, works with Cloudflare R2 / MinIO
```

Keys are opaque (`{user_id}/{uuid}{ext}`); files never served by raw path.

---

## 10. Configuration

`pydantic-settings`, all via env (`.env.example` documents every var):

```
APP_ENV=development
APP_SECRET_KEY=
DATABASE_URL=postgresql+psycopg://jobgoblin:***@db:5432/jobgoblin
AI_PROVIDER=ollama
OLLAMA_BASE_URL=http://ollama:11434
OLLAMA_MODEL=qwen2.5:7b-instruct
OLLAMA_FAST_MODEL=llama3.2:3b
FILE_STORAGE_PATH=/data/uploads
MAX_UPLOAD_MB=10
ADMIN_EMAIL=
ADMIN_PASSWORD=
FRONTEND_ORIGIN=http://localhost:3000   # dev only; prod is same-origin
```

---

## 11. Deployment (Docker Compose)

Services (all `restart: unless-stopped`, auto-start on boot):

| Service | Image / build | Volume |
|---------|---------------|--------|
| `caddy` | caddy:2 | caddy config; routes `/`→frontend, `/api`→backend |
| `frontend` | build `frontend/` | — |
| `backend` | build `backend/` | `uploads:/data/uploads` |
| `db` | postgres:16 | `pgdata:/var/lib/postgresql/data` |
| `ollama` | ollama/ollama | `ollama:/root/.ollama` (model cache) |
| `cloudflared` | cloudflare/cloudflared | tunnel token via env; planned, not yet in compose |

- **GPU:** `ollama` container gets the NVIDIA GPU via the container toolkit (CUDA).
- **Model setup:** pull `qwen2.5:7b-instruct` into the Ollama volume before using the real provider; tests and fast dev use `AI_PROVIDER=mock`.
- **Migrations:** `alembic upgrade head` on backend start.
- **CI:** `.github/workflows/ci.yml` currently runs backend ruff + pytest. Frontend lint/build is planned for the delivery-foundation phase.

---

## 12. Testing strategy

- **Backend:** `pytest` + `httpx.AsyncClient`; ephemeral Postgres (Docker/testcontainers);
  **`MockProvider`** for all AI so tests are deterministic and offline. Cover auth +
  ownership isolation, scoring math (deterministic part), parsing, CRUD.
- **Frontend:** component tests (Vitest) + a Playwright smoke of the core loop later.

---

## 13. Repository structure

```
jobgoblin/
├── backend/   app/{core,models,schemas,api/routes,services,workers,tests}/ · Dockerfile · pyproject.toml · alembic/
├── frontend/  app/{login,dashboard,resumes,jobs,applications,contacts,settings}/ · components/ · lib/ · Dockerfile
├── infra/     Caddyfile · cloudflared config planned
├── docs/      architecture.{html,md} · design.md
├── docker-compose.yml · .env.example · README.md
```

---

## 14. Decisions log & open questions

**Decided:** Ollama (`qwen2.5:7b`) · self-host on laptop + Cloudflare Tunnel (non-24/7)
· same-origin via Caddy (no CORS) · invite-only registration · SQLModel + Alembic ·
deterministic+AI scoring (embeddings deferred to V2) · pipeline status on `applications`.

**Resolved:** registration uses the **invite-token** model · upload cap **10 MB**
(`MAX_UPLOAD_MB`, configurable). Building `feature/backend-foundation` next.
