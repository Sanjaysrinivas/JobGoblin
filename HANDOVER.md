# JobGoblin Agent Handover

Snapshot for the next agent/session. Last updated: 2026-07-01.

Read this once, then keep the local runtime, verification, and roadmap sections handy.

## 1. Project Summary

JobGoblin is a self-hosted, AI-powered job-search and application-management app for one owner and a few invited users. It currently supports private auth, resume management, and jobs CRUD, and is building toward resume-to-job analysis, cover letters, outreach drafts, and application pipeline management.

Core principles:

- Private productivity tool, not a spam or auto-apply bot.
- Every external action, including email, recruiter outreach, and applying, requires human review.
- AI must never invent experience, skills, education, credentials, or employment history.
- ATS-style scores are estimates and must be labelled as estimates.
- Multi-user data is isolated by `user_id`.

Canonical docs:

- `README.md` for at-a-glance setup and status.
- `docs/architecture.md` for topology and hosting decisions.
- `docs/design.md` for the V1 design contract.
- `docs/roadmap.md` for phase order and exit criteria.

## 2. Architecture Decisions

| Decision | Current choice | Rationale |
|----------|----------------|-----------|
| Topology | Next.js frontend + FastAPI backend in one monorepo | Clear service boundary without microservice overhead. |
| Hosting | Docker Compose on the owner's laptop | Keeps cost at $0 and supports local Ollama. |
| Browser origin | Caddy routes `/` to frontend and `/api/*` to backend | HTTP-only cookies work without CORS/cross-site workarounds. |
| AI | Ollama provider for real local use, `MockProvider` for tests/dev | Private, no API keys required for normal local operation. |
| Auth | Email/password, invite tokens, Google OAuth plumbing, allowlist, TOTP MFA | Private/invite-only posture with optional OAuth UX. |
| Data | PostgreSQL 16, SQLModel, Alembic | Typed FastAPI-friendly model layer with migrations. |
| Storage | Local uploads volume behind a storage interface | Keeps MVP simple while preserving a future object-storage swap. |

Cloudflare Tunnel is planned but not yet in `docker-compose.yml`.

## 3. Tech Stack

Backend:

- Python 3.12, FastAPI, SQLModel, Alembic, PostgreSQL 16, psycopg.
- Auth: argon2-cffi, python-jose JWT cookies, Authlib Google OAuth, pyotp/segno TOTP, slowapi rate limiting, Starlette SessionMiddleware for OAuth state.
- Resume/document services: pdfplumber, python-docx, fpdf2, Ollama client.

Frontend:

- Next.js 16 App Router, React 19, TypeScript strict, Tailwind CSS v4, shadcn/ui, lucide-react.
- App shell lives under `frontend/app/(app)` and is protected by `AuthGate`.

Infra:

- `docker-compose.yml`: db, ollama, backend, frontend, caddy.
- `infra/Caddyfile`: same-origin routing.
- `.github/workflows/ci.yml`: backend ruff/pytest and frontend lint/build.

## 4. Current Status

Merged work includes:

- Architecture docs and detailed V1 design spec.
- Backend foundation: health endpoint, config, error envelope, CI, migrations.
- Data model: users, invite tokens, resumes, jobs, analyses, cover letters, applications, contacts, outreach messages, activity events.
- Auth: email/password, admin-created invite tokens, invite-only signup, Google OAuth plumbing, allowlist, TOTP MFA, environment-aware cookies.
- Frontend foundation: app shell, auth guard, login/MFA/signup flow, jobs screens, and placeholder pages for later resources.
- Resume module: upload, extract, parse, edit, list/detail, delete, and PDF export.
- Delivery foundation: route auto-discovery and frontend CI.
- Phase 2 first slice: jobs CRUD API/UI and invite signup flow.

Live API surface today:

- `/api/health`
- `/api/auth/register`, `/api/auth/login`, `/api/auth/logout`, `/api/auth/me`
- `/api/invites` admin list/create
- `/api/auth/google/login`, `/api/auth/google/callback`
- `/api/auth/mfa/enroll`, `/api/auth/mfa/verify`, `/api/auth/mfa/challenge`
- `/api/resumes/upload`, `/api/resumes`, `/api/resumes/{id}`
- `PATCH /api/resumes/{id}`, `DELETE /api/resumes/{id}`
- `/api/resumes/{id}/parse`, `/api/resumes/{id}/export.pdf`
- `/api/jobs`, `/api/jobs/{id}`

Not built yet:

- Contacts, applications, dashboard-data endpoints.
- Cover-letter generation and workflow.
- Resume-to-job analysis UI/API.
- Cloudflare Tunnel service.
- Email sending or any approval-gated external action implementation.

## 5. Local Runtime

Full stack:

```bash
cp .env.example .env
# Set AI_PROVIDER=mock for fast local iteration if Ollama is not ready.
docker compose up -d --build
```

Useful URLs:

- App through Caddy: http://localhost:8080
- Backend Swagger UI: http://localhost:8000/docs

Demo seed values commonly used in local `.env`:

```dotenv
AI_PROVIDER=mock
ADMIN_EMAIL=admin@jobgoblin.local
ADMIN_PASSWORD=goblin-demo-pass-123
```

Current browser check:

1. Start the Docker/Caddy stack.
2. Log in at http://localhost:8080 with the demo admin credentials.
3. Confirm the browser has a `jg_session` cookie.
4. Confirm `/api/auth/me` returns 200.

Fast rebuilds after changes:

```bash
docker compose up -d --build --no-deps backend
docker compose up -d --build --no-deps frontend
```

The backend direct port remains published for docs and local API inspection. Database and Ollama are intended to be reached inside the compose network.

## 6. Verification

Backend tests expect a throwaway Postgres on host port 5433:

```bash
docker run -d --name jg-test-db -e POSTGRES_USER=test -e POSTGRES_PASSWORD=test -e POSTGRES_DB=test -p 5433:5432 postgres:16-alpine
cd backend
python -m venv .venv
./.venv/Scripts/python.exe -m pip install -e ".[dev]"
TEST_DATABASE_URL=postgresql+psycopg://test:test@localhost:5433/test ./.venv/Scripts/python.exe -m pytest -q
./.venv/Scripts/ruff.exe check .
```

Frontend:

```bash
cd frontend
npm run lint
npm run build
```

CI runs backend ruff/pytest with a Postgres service and frontend lint/build on pull requests.

## 7. Workflow Notes

Branch flow: `main -> dev -> feature/*`.

- Keep `main` release-ready.
- Open feature PRs into `dev`.
- Do not commit `.env`; it is gitignored and may contain local demo credentials.
- Do not bypass invite-only/private posture while implementing auth or OAuth.
- New backend route modules should export `router`; `backend/app/api/routes/__init__.py` auto-discovers them.
- User-owned queries must filter by `user_id`; cross-user object access should not leak object existence.
- Migrations run automatically on backend container start with `alembic upgrade head`.

Google OAuth owner setup is still external: create a Google OAuth app, add owner/friends as test users, configure `http://localhost:8080/api/auth/google/callback`, then set `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, and `ALLOWED_EMAILS` in `.env`. Until then Google endpoints fail closed with 503, while email/password login still works.

## 8. Roadmap Summary

Detailed phase criteria live in `docs/roadmap.md`.

1. Phase 0 - usable local app: complete.
2. Phase 1 - delivery foundation: complete.
3. Phase 2 - core resource modules: jobs are in this branch; next are contacts, applications, dashboard, and cover letters.
4. Phase 3 - resume-to-job analysis: deterministic scoring plus AI explanation.
5. Phase 4 - real local runtime and external access: Ollama model setup, Google OAuth, Cloudflare Tunnel, HTTPS cookie verification.
6. Phase 5 - workflow expansion: profile builder, resume versions, tailored drafts, outreach drafts, reminders, interview prep.

## 9. Gotchas

- `.env.example` intentionally leaves `ADMIN_EMAIL` and `ADMIN_PASSWORD` blank; set them locally to seed the demo admin.
- `AI_PROVIDER=mock` is best for fast local iteration. Real parsing/generation needs Ollama running and the model pulled.
- The `ollama` service starts, but model download/setup is still a manual runtime step.
- Existing migrations are chained; do not reorder or rewrite them.
- If the test database schema drifts, reset the throwaway schema before rerunning tests:

```bash
docker exec jg-test-db psql -U test -d test -c "DROP SCHEMA public CASCADE; CREATE SCHEMA public;"
```
