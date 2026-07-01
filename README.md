# JobGoblin

[![CI](https://github.com/Sanjaysrinivas/JobGoblin/actions/workflows/ci.yml/badge.svg)](https://github.com/Sanjaysrinivas/JobGoblin/actions/workflows/ci.yml)
![Next.js](https://img.shields.io/badge/Next.js-frontend-000000?logo=next.js&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-backend-009688?logo=fastapi&logoColor=white)
![Python](https://img.shields.io/badge/Python-3.12+-3776AB?logo=python&logoColor=white)
![TypeScript](https://img.shields.io/badge/TypeScript-typed-3178C6?logo=typescript&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-database-4169E1?logo=postgresql&logoColor=white)
![Docker](https://img.shields.io/badge/Docker-compose-2496ED?logo=docker&logoColor=white)
![Hosting](https://img.shields.io/badge/hosting-%240%2Fmo-2ea44f)
![Status](https://img.shields.io/badge/status-MVP%20in%20progress-f5b945)

A self-hosted, AI-powered job-search and application-management web app for one
owner and a few invited friends. Upload a resume, score it against a job
description, surface missing keywords, generate truthful drafts, and track every
application from saved to offer.

> Private productivity tool, not a spam or auto-apply bot. Every external action
> such as email, recruiter outreach, or applying requires explicit human review.
> The AI must never invent experience, skills, education, or credentials.

## Architecture At A Glance

The current deployment target is one local Docker Compose stack on the owner's
laptop, served through Caddy under one browser origin.

| Layer | Tech | Runtime |
|-------|------|---------|
| Frontend | Next.js, React, TypeScript, Tailwind, shadcn/ui | Docker container |
| Backend | FastAPI, Python 3.12, SQLModel, Alembic | Docker container |
| Database | PostgreSQL 16 | Docker volume |
| File storage | Local mounted uploads volume behind a storage interface | Docker volume |
| AI | Ollama primary provider, MockProvider for tests | Docker container |
| Edge | Caddy now; Cloudflare Tunnel planned | Local container stack |

Caddy routes `/` to the frontend and `/api/*` to the backend, so browser traffic
is same-origin and auth can use HTTP-only cookies without CORS workarounds.

Full docs:

- [Architecture](docs/architecture.md)
- [Detailed design](docs/design.md)
- [Roadmap and phases](docs/roadmap.md)

## Repository Layout

```text
jobgoblin/
├── backend/            # FastAPI service, SQLModel models, Alembic migrations, tests
├── frontend/           # Next.js app shell and UI
├── docs/               # architecture, design, roadmap
├── infra/              # Caddy config
├── docker-compose.yml  # local/self-hosted stack
├── .env.example
└── README.md
```

## Current Status

Implemented:

- Backend foundation, health endpoint, settings, migrations, CI backend and frontend jobs.
- Email/password auth, Google OAuth plumbing, allowlist, TOTP MFA.
- Resume upload, extraction, AI parse, edit, list/detail, delete, and PDF export.
- Frontend app shell, login/MFA screens, and resume screens.

Not built yet:

- Jobs, contacts, cover letters, applications, dashboard data endpoints.
- Resume-to-job analysis UI/API.
- Cloudflare Tunnel service.
- Email sending and approval-gated external actions.

Known active blocker: local browser login needs environment-aware cookie
security and a clearer MFA-enrollment path. See [HANDOVER.md](HANDOVER.md) if
present in your checkout.

## Local Development

Copy the environment template and use mock AI for fast local iteration:

```bash
cp .env.example .env
docker compose up -d --build
```

Useful URLs:

- App through Caddy: http://localhost:8080
- Backend Swagger UI: http://localhost:8000/docs

The frontend and backend are also runnable directly during development, but the
Docker/Caddy path is the intended same-origin integration path.

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

Frontend lint/build are not in GitHub Actions yet; that is part of the next
foundation phase.

## Branching Workflow

`main -> dev -> feature/*`

`main` stays release-ready, `dev` is the integration branch, and each change
should land through a focused feature branch and PR into `dev`.
