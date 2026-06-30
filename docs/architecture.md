# JobGoblin — Architecture

A self-hosted, AI-powered job-search and application-management web app. This is the
text companion to [`architecture.html`](architecture.html) (open that in a browser for
the diagram and full layout).

## 1. Principles

- **Private productivity tool, not a spam bot.** Every external action (email,
  recruiter outreach, applying) requires explicit human review and approval.
- **Truthful AI.** The AI may rephrase, emphasize, and reorganize the user's real
  content — it must never invent experience, skills, education, or credentials.
- **Estimated scores.** ATS-style match scores are labelled estimates, never
  guaranteed ATS results.
- **Multi-user.** You and your friends each get isolated accounts; every row is
  scoped to a `user_id`.

## 2. Services

Two independently-built services communicating over HTTP/JSON, served behind one
reverse proxy so they share a single origin:

- **Frontend** — Next.js · React · TypeScript · Tailwind · shadcn/ui
- **Backend** — FastAPI · Python · Pydantic · SQLModel

State and AI run as local containers alongside them:

- **PostgreSQL** — users, resumes, jobs, analyses, applications, etc. (Docker volume).
- **File storage** — uploaded resume files on a mounted volume (storage behind an
  interface, so S3/R2 is a later swap).
- **Ollama** — local LLM runtime, the primary AI provider. Mock for tests;
  OpenAI/Anthropic remain pluggable but unused.

## 3. Hosting — self-hosted on the owner's laptop, $0

Everything runs in one Docker Compose stack on the owner's laptop (Ryzen 7 ·
31 GB RAM · RTX 4070 8 GB) and is exposed to the internet via a free Cloudflare
Tunnel. This is what lets us use Ollama (which needs real RAM/GPU and can't run on
free cloud tiers) while staying at $0.

| Component | Runs as | Cost |
|-----------|---------|------|
| Frontend / Backend | containers behind Caddy (same origin) | $0 |
| PostgreSQL | container + volume | $0 |
| Ollama (`qwen2.5:7b`) | container, GPU-accelerated | $0 |
| File storage | mounted volume | $0 |
| Public access | Cloudflare Tunnel (HTTPS) | $0 |
| Repo / CI | GitHub Actions | $0 |

**Trade-off:** the app is online only while the laptop is on (non-24/7). All data
persists on Docker volumes across shutdowns. Because Caddy serves both services under
one hostname, sessions use plain secure HTTP-only cookies — no cross-origin hacks.

## 4. Data model

Core tables (all scoped to `user_id`):

`users`, `resumes`, `resume_versions`, `jobs`, `job_analyses`,
`tailored_resume_drafts`, `cover_letters`, `applications`, `contacts`,
`outreach_messages`, `email_drafts`, `activity_events`.

Application pipeline statuses: `saved`, `interested`, `resume_tailored`,
`cover_letter_created`, `applied`, `contacted_recruiter`, `referred`,
`phone_screen`, `technical_interview`, `final_interview`, `offer`, `rejected`,
`withdrawn`, `archived`.

## 5. Core AI flow — resume × job analysis

1. User uploads a resume → backend stores the file (local volume) and extracts plain text.
2. User pastes a job description and selects a resume.
3. **Deterministic pass:** extract & normalize keywords from both; compute weighted
   category scores — keywords 30%, skills 25%, experience 20%, role 10%,
   education 5%, formatting 10%.
4. **AI pass:** explain gaps, distinguish *missing keywords you already qualify for*
   from *qualifications you lack*, and suggest truthful improvements.
5. Persist numeric score + matched/missing keywords + recommendations.
6. User saves the job to the tracker and advances it through the pipeline.

## 6. Branching workflow

`main → dev → feature/*`:

- **main** — always deployable; receives merges from `dev` via PR at release points.
- **dev** — integration branch; feature PRs land here first.
- **feature/\*** — one branch per unit of work, branched off `dev`, merged via PR.
