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

Two independently-deployed services communicating over HTTP/JSON:

- **Frontend** — Next.js · React · TypeScript · Tailwind · shadcn/ui → Vercel
- **Backend** — FastAPI · Python · Pydantic · SQLModel → Render

State lives outside the containers:

- **PostgreSQL** (Neon) — users, resumes, jobs, analyses, applications, etc.
- **Object storage** (Cloudflare R2) — uploaded resume files.
- **AI provider layer** — a pluggable interface with OpenAI / Anthropic / Ollama /
  Mock implementations, switchable by config.

## 3. The $0 hosting stack

| Layer | Host | Cost | Trade-off |
|-------|------|------|-----------|
| Frontend | Vercel (Hobby) | $0 | Free forever; non-commercial only |
| Backend | Render web service | $0 | Sleeps after ~15 min idle → ~30–50s cold start |
| Database | Neon (Postgres) | $0 | ~0.5 GB; auto-suspends, resumes in ~1s |
| File storage | Cloudflare R2 | $0 | 10 GB, no egress fees |
| Repo / CI | GitHub | $0 | Actions included |

Built **Docker-first** with storage + DB behind interfaces, so moving to an always-on
~$5/mo VPS later is a config change, not a rewrite.

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

1. User uploads a resume → backend stores the file (R2) and extracts plain text.
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
