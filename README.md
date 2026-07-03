# JobGoblin

[![CI](https://github.com/Sanjaysrinivas/JobGoblin/actions/workflows/ci.yml/badge.svg)](https://github.com/Sanjaysrinivas/JobGoblin/actions/workflows/ci.yml)
![Next.js](https://img.shields.io/badge/Next.js-frontend-000000?logo=next.js&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-backend-009688?logo=fastapi&logoColor=white)
![Python](https://img.shields.io/badge/Python-3.12+-3776AB?logo=python&logoColor=white)
![TypeScript](https://img.shields.io/badge/TypeScript-typed-3178C6?logo=typescript&logoColor=white)
![Docker](https://img.shields.io/badge/Docker-compose-2496ED?logo=docker&logoColor=white)
![Status](https://img.shields.io/badge/status-MVP%20in%20progress-f5b945)

JobGoblin is a private, self-hosted job-search workspace for one owner and a few invited users. It stores resumes, jobs, contacts, applications, analyses, cover-letter drafts, and outreach drafts while keeping the workflow local and review-driven.

It is not an auto-apply or spam tool. External actions such as sending email, contacting recruiters, or applying to jobs must remain human-reviewed. AI output must stay grounded in user-provided facts and never invent experience, skills, education, or credentials.

## Current Status

MVP build in progress. Phase 0 local-login fixes and Phase 1 delivery foundation are complete, and the merged `dev` branch now includes the core MVP workflow.

Phase status:

- Phase 2 core resource modules are implemented: jobs, contacts, applications, dashboard, cover-letter drafts, and outreach drafts.
- Phase 3 resume-to-job analysis is implemented and needs integrated post-merge validation.
- Phase 4 runtime tooling and the optional Cloudflare Tunnel profile are implemented; real Ollama, OAuth, and tunnel smoke testing are still required.
- Phase 5 has the profile builder, follow-up reminders, and resume versions merged. Tailored resume drafts, email draft/export integration, and interview prep are still ahead.

Implemented:

- Docker Compose stack with Caddy as the same-origin entry point.
- Optional Cloudflare Tunnel compose profile, disabled by default.
- FastAPI backend, PostgreSQL, Alembic migrations, SQLModel models, and health endpoint.
- Email/password auth, admin-created invite tokens, invite-only signup, Google OAuth plumbing, email allowlist, TOTP MFA, and environment-aware auth cookies.
- Resume upload, text extraction, AI parse, edit/list/detail/delete, version management, and PDF export.
- Jobs CRUD API and jobs list/create/detail/edit/delete UI.
- Contacts, applications, dashboard data, resume-to-job analysis, cover-letter draft, profile builder, follow-up reminder, and review-only outreach APIs.
- Next.js app shell, auth guard, login/MFA/signup flow, resume, jobs, contacts, applications, dashboard, job-detail analysis/cover-letter, outreach, and profile screens.
- Runtime operator checks for Ollama, local smoke testing, and Cloudflare Tunnel setup.
- CI for backend ruff/pytest, frontend lint/build, and the merged E2E harness.

Remaining validation and future work:

- Integrated post-merge smoke pass across the browser workflow.
- Real local AI verification with `AI_PROVIDER=ollama`.
- Google OAuth, allowlist, HTTPS tunnel, and secure-cookie validation with real credentials.
- Tailored resume drafts, email draft/export integration, and interview prep.
- Any external sending remains out of scope unless it is explicit, user-reviewed, and approval-gated.

## Quick Start

Copy the environment template:

```bash
cp .env.example .env
```

For fast local iteration, set mock AI and seed the demo admin in `.env`:

```dotenv
AI_PROVIDER=mock
ADMIN_EMAIL=admin@jobgoblin.local
ADMIN_PASSWORD=goblin-demo-pass-123
```

Start the stack:

```bash
docker compose up -d --build
```

Open:

- App through Caddy: http://localhost:8080
- Backend Swagger UI: http://localhost:8000/docs

Demo login, when the seed admin values above are configured:

- Email: `admin@jobgoblin.local`
- Password: `goblin-demo-pass-123`

The Docker/Caddy path is the intended integration path. Caddy routes `/` to the frontend and `/api/*` to the backend so browser traffic is same-origin and auth can use HTTP-only cookies without CORS workarounds.

## Runtime Notes

Ollama is included in the Compose stack, but model download is a one-time host action. For the intended local AI runtime, pull the default model after the stack is up:

```bash
docker compose exec ollama ollama pull qwen2.5:7b-instruct
```

Use `AI_PROVIDER=mock` in `.env` for fast local iteration without a model. Use `AI_PROVIDER=ollama` plus the default `OLLAMA_BASE_URL=http://ollama:11434` when smoke-testing real local parsing/generation.

Cloudflare Tunnel is optional and disabled by default. Create a tunnel in Cloudflare Zero Trust, point its public hostname at `http://caddy:80`, set `CLOUDFLARED_TUNNEL_TOKEN` in `.env`, then start only the tunnel profile:

```bash
docker compose --profile tunnel up -d cloudflared
```

The normal `docker compose up -d --build` path remains local-only and does not require Cloudflare credentials.

## Repository Layout

```text
jobgoblin/
|-- backend/            # FastAPI service, models, migrations, tests
|-- frontend/           # Next.js app shell and UI
|-- docs/               # architecture, design, roadmap
|-- infra/              # Caddy config
|-- docker-compose.yml  # local/self-hosted stack
`-- .env.example        # committed environment template
```

## Verification

Backend:

```bash
cd backend
TEST_DATABASE_URL=postgresql+psycopg://test:test@localhost:5433/test ./.venv/Scripts/python.exe -m pytest -q
./.venv/Scripts/ruff.exe check .
```

Frontend:

```bash
cd frontend
npm run lint
npm run build
```

GitHub Actions runs the same backend and frontend checks for pull requests.

## Essential Docs

- [Architecture](docs/architecture.md)
- [Detailed design](docs/design.md)
- [Roadmap](docs/roadmap.md)
- [Frontend notes](frontend/README.md)

Branch flow: `main -> dev -> feature/*`. Keep `main` release-ready, integrate through `dev`, and use focused PRs for feature work.
