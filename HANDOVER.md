# JobGoblin — Agent Handover

> Snapshot for the next agent/session picking up this project. Last updated **2026-07-01**.
> Read this top-to-bottom once, then keep section 7 (local runtime verification), section 9 (phase roadmap), and `docs/roadmap.md` open.

---

## 1. What this is

**JobGoblin** ðŸ‘º â€” a self-hosted, AI-powered job-search & application-management web app for
one owner + a few invited friends. Upload a rÃ©sumÃ© â†’ score it against a job description
(estimated ATS-style match) â†’ surface missing keywords â†’ generate tailored bullets, cover
letters, outreach â†’ track applications through a pipeline.

**Core principles (never violate):**
- Private productivity tool â€” **not** a spam/auto-apply bot.
- Every external action (email/outreach/apply) requires **human review**.
- The AI **never invents** experience/skills/credentials â€” only rephrases truthful input.
- ATS scores are **estimates**, always labelled as such.
- **Multi-user** with hard isolation â€” every owned row scoped to `user_id`.

Full spec: `docs/design.md`. High-level + diagram: `docs/architecture.md` / `docs/architecture.html`.

---

## 2. Architecture & key decisions (with rationale)

| Decision | Choice | Why |
|----------|--------|-----|
| Topology | 2 services (Next.js FE + FastAPI BE), one monorepo | "Not a monolith" but no microservice tax at this scale |
| Hosting | **Self-host all containers on the owner's laptop** (Ryzen 7 Â· 31 GB Â· RTX 4070 8 GB) + **Cloudflare Tunnel** | $0, and the only way to run **Ollama** (needs GPU/RAM; can't run on free cloud tiers). Non-24/7 is accepted (laptop off at night). |
| Same-origin | **Caddy** reverse proxy: `/`â†’frontend, `/api/*`â†’backend, one hostname | Lets us use secure HTTP-only cookies with **no CORS/cross-site** issues |
| AI | **Ollama** (`qwen2.5:7b-instruct`), `MockProvider` for tests, OpenAI/Anthropic pluggable | $0, private, no API keys. Structured output via `chat(format=<json schema>, temperature=0)` |
| Auth | Email/password **+ Google OAuth** + **TOTP MFA** + email allowlist | Google for UX; allowlist keeps it private (OAuth alone lets anyone in); TOTP because SMS costs $ and email OTP needs deferred email infra |
| ORM/migrations | SQLModel + Alembic | typed, FastAPI-native |
| Profile data | Comes from **rÃ©sumÃ© upload â†’ AI parse**, *not* LinkedIn | LinkedIn API won't give profile data to a personal app; scraping violates ToS + our non-goals. LinkedIn PDF export can be uploaded like any rÃ©sumÃ©. |

Decisions are also saved to agent memory: `jobgoblin-architecture.md`, `jobgoblin-git-workflow.md`.

---

## 3. Tech stack

- **Backend:** Python 3.12, FastAPI, SQLModel, Alembic, PostgreSQL 16, psycopg. Auth: argon2-cffi, python-jose (JWT), Authlib (Google OAuth), pyotp + segno (TOTP+QR), slowapi (rate limiting), itsdangerous/Starlette SessionMiddleware (OAuth state). Docs/parse: pdfplumber, python-docx, fpdf2 (PDF export), ollama client.
- **Frontend:** Next.js 16 (App Router), TypeScript (strict), Tailwind v4, shadcn/ui. Design system "**Goblin Workshop**" (warm stone + goblin-green accent, dark mode; fonts Sora / Plus Jakarta Sans / JetBrains Mono, self-hosted via `next/font`).
- **Infra:** Docker Compose (db, ollama, backend, frontend, caddy), Cloudflare Tunnel (planned, not yet added).

---

## 4. Repo layout & key files

```
backend/
  app/
    main.py                     # app wiring: routers, SessionMiddleware, limiter, CORS(dev), lifespan(seed_admin), error envelope
    core/
      config.py                 # pydantic-settings; prod-secret guard; get_settings() cached
      database.py               # engine + get_session() dependency
      security.py               # argon2 + JWT; MFA token-type isolation (session vs mfa_pending)
      startup.py                # idempotent admin seed from ADMIN_EMAIL/PASSWORD
      storage.py                # StorageBackend ABC + LocalStorage (path-traversal-safe)
      ratelimit.py              # slowapi limiter + 429 handler
      allowlist.py, google_oauth.py, totp.py   # auth pieces
    api/
      deps.py                   # get_current_user (cookie -> JWT -> user, 401)
      routes/health.py, auth.py, resumes.py
    services/
      ai_provider.py            # AIProvider ABC, OllamaProvider, MockProvider, get_ai_provider()
      document_extractor.py     # PDF/DOCX -> text
      resume_parser.py          # text -> structured JSON via AI
      pdf_export.py             # structured resume -> PDF (fpdf2)
    schemas/                    # auth.py, resume.py
    models/                     # core.py (10 tables + enums.py); user has google_sub/totp_secret/totp_enabled/last_totp_timestep
  alembic/versions/             # 7ca6416ad0c0 (initial), 6216e35ab071 (google+totp)
  tests/                        # conftest.py (session-scoped schema + TRUNCATE; autouse settings/limiter reset)
  Dockerfile, pyproject.toml
frontend/
  app/(app)/{dashboard,resumes,jobs,applications,contacts,settings}/  # (app)/layout.tsx = shell, NO auth guard
  app/login/, components/login-form.tsx, components/mfa-form.tsx
  lib/api.ts (typed fetch, server vs browser base URL), lib/auth.ts, lib/types.ts, lib/resumes.ts
  Dockerfile, public/.gitkeep
infra/Caddyfile
docker-compose.yml, .env.example, README.md, docs/{design,architecture}.md, docs/architecture.html
```

---

## 5. Current status

**Merged to `dev` (PRs #1â€“#8):** architecture docs Â· design spec Â· backend foundation (health, config, CI) Â·
data model (10 tables + migration) Â· email/password auth Â· frontend foundation Â· **Google OAuth + TOTP MFA + allowlist** Â· **resume module** (uploadâ†’extractâ†’parseâ†’editâ†’**export-PDF**).

- Backend tests and `ruff` pass on `dev`. CI (GitHub Actions) now runs backend ruff/pytest with a Postgres service and frontend lint/build.
- **15 API endpoints** live: `/api/health`, `/api/auth/{register,login,logout,me,google/login,google/callback,mfa/enroll,mfa/verify,mfa/challenge}`, `/api/resumes/{upload,GET,GET id,PATCH,DELETE,parse,export.pdf}`.
- Branch trail: `main â†’ dev â†’ feature/*` (all feature branches merged & deleted).

**Not built yet:** jobs, contacts, cover-letters, applications, dashboard-data endpoints; profile-builder; Cloudflare Tunnel; email sending.

---

## 6. How to run (dev environment)

**Stack:** `docker compose up -d --build` brings up db + ollama + backend + frontend + caddy.
To skip the large Ollama pull while iterating: `docker compose up -d --build --no-deps db backend frontend caddy` (start `db` first, wait healthy).

- **App (via Caddy):** http://localhost:8080  (`/`â†’frontend, `/api/*`â†’backend)
- **Backend direct / Swagger:** http://localhost:8000/docs
- **db** and **ollama** are internal (not published).
- **Local `.env`** (gitignored) currently has demo values: `AI_PROVIDER=mock`, `ADMIN_EMAIL=admin@jobgoblin.local`, `ADMIN_PASSWORD=goblin-demo-pass-123`. All env vars documented in `.env.example`.

**Backend tests:** a throwaway Postgres runs in container **`jg-test-db`** on host **:5433**.
```
docker run -d --name jg-test-db -e POSTGRES_USER=test -e POSTGRES_PASSWORD=test -e POSTGRES_DB=test -p 5433:5432 postgres:16-alpine
cd backend && python -m venv .venv && ./.venv/Scripts/python.exe -m pip install -e ".[dev]"
TEST_DATABASE_URL=postgresql+psycopg://test:test@localhost:5433/test ./.venv/Scripts/python.exe -m pytest -q
./.venv/Scripts/ruff.exe check .
```
If the test schema is stale: `docker exec jg-test-db psql -U test -d test -c "DROP SCHEMA public CASCADE; CREATE SCHEMA public;"`.

**Migrations** run automatically on backend container start (`alembic upgrade head`). Autogenerate:
`DATABASE_URL=...:5433/test ./.venv/Scripts/alembic.exe revision --autogenerate -m "..."` then verify `upgrade head` + `alembic check` (no drift) + `downgrade base`.

**Note:** Docker Desktop reset once mid-session and wiped containers â€” if `docker ps` is empty, relaunch Docker Desktop and `docker compose up` again (volumes persist; `jg-test-db` must be recreated).

---

## 7. Local runtime verification

Phase 0 landed in PR #10. Local browser login now uses environment-aware auth cookies, MFA enrollment can be skipped during login, and the frontend auth helpers match the backend response shape.

**Current check:** run the Docker/Caddy stack and log in at http://localhost:8080 with the demo admin credentials. Confirm the browser stores `jg_session` and `/api/auth/me` returns 200 after login.

**Refresh after backend/frontend edits:** `docker compose up -d --build` for the full stack, or rebuild a single service with `docker compose up -d --build --no-deps backend` / `frontend` when dependencies are already running.

---

## 8. Conventions & workflow (follow these)

- **Branching:** `main â†’ dev â†’ feature/*`. Never commit features to `main`/`dev` directly. Branch off `dev`, open a PR **into `dev`** (`gh pr create --base dev`). Commit trailer: `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`. Remote: `github.com/Sanjaysrinivas/JobGoblin`.
- **TDD (rigid):** write the failing test, watch it fail, then minimal code to pass. Greenfield conventions: pytest, tests in `backend/tests/`, `test_*.py`, `TestClient` + `dependency_overrides`, the `session` fixture.
- **Every PR gets a `gemini-code-assist` review.** The established loop: fetch comments (`gh api repos/Sanjaysrinivas/JobGoblin/pulls/<n>/comments`), **triage them (verify, don't blindly apply)**, then fix. So far every batch has been valid; document any you reject and why.
- **Verify before "done":** run pytest + ruff (backend) / `npm run build` + lint (frontend) + confirm CI green before recommending a merge. Spot-check security-sensitive code even when an agent reports green.
- **Parallel agents:** big independent features were built via the **Agent tool with `isolation: "worktree"`** and thorough self-contained prompts (agents don't inherit context). Resume a completed agent with **SendMessage** (by its `agentId`) to apply review fixes in its existing worktree. Only dispatch agents for genuinely independent work (no shared files / sequential deps).
- **RTK:** user's global instruction is to prefix shell commands with `rtk` (token-saving passthrough); non-critical.

---

## 9. Phase roadmap (recommended order)

The durable phase plan now lives in `docs/roadmap.md`. In short:

1. **Phase 0 - Restore a usable local app:** completed in PR #10 with env-conditional auth cookies, skippable MFA enrollment, aligned auth helpers, and app auth guarding.
2. **Phase 1 - Delivery foundation:** in progress in PR #11 with auto-router discovery, frontend CI (lint + build), and refreshed README/design/roadmap handoff docs.
3. **Phase 2 - Core resource modules:** build jobs, contacts, applications, dashboard, and cover-letter CRUD/generation against the existing models, with strict `user_id` isolation and tests.
4. **Phase 3 - Resume-to-job analysis:** implement deterministic keyword/fuzzy scoring using existing `rapidfuzz`, add AI explanation through `AIProvider`, persist `JobAnalysis`, and surface estimated scores in the UI.
5. **Phase 4 - Real local runtime and external access:** pull/configure Ollama models, set `AI_PROVIDER=ollama`, configure Google OAuth, then add Cloudflare Tunnel and verify HTTPS cookie behavior.
6. **Phase 5 - V2 workflow expansion:** profile builder, resume versions, tailored drafts, outreach drafts, reminders, email drafts, and interview prep, always review-gated.

## 10. Known gotchas

- **`.env` is gitignored** and holds demo creds + `AI_PROVIDER=mock`; don't commit it. `.env.example` is the committed template.
- **Migrations run on container start** â€” if you change models, regenerate the migration (against :5433) and verify `alembic check`; otherwise the container's `alembic upgrade head` can drift from models. Enums are stored as `VARCHAR + CHECK` (native_enum=False) on purpose.
- **Two migrations chain:** `7ca6416ad0c0` â†’ `6216e35ab071`. Don't reorder.
- **Ollama** isn't started in the `--no-deps` dev shortcut; real parsing needs it up + the model pulled (multi-GB). Tests always use `MockProvider`.

---

## 11. Human-only external dependency

**Google OAuth app** (owner must create): Google Cloud Console â†’ OAuth consent screen (**Testing** mode; add owner+friends as test users = built-in allowlist) â†’ Credentials â†’ OAuth client (Web) â†’ Authorized redirect URI `http://localhost:8080/api/auth/google/callback` (+ the tunnel URL later) â†’ copy Client ID/Secret into `.env` (`GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`). Until then, `/api/auth/google/*` return 503 and the "Sign in with Google" button won't complete; everything else works.

---

## 12. Command cheat-sheet

```bash
# Full stack (with Ollama pull)         docker compose up -d --build
# Fast stack (skip Ollama)              docker compose up -d db && docker compose up -d --build --no-deps backend frontend caddy
# Rebuild just backend after a change   docker compose up -d --build --no-deps backend
# Logs                                  docker compose logs backend | tail
# Backend tests + lint                  cd backend; TEST_DATABASE_URL=postgresql+psycopg://test:test@localhost:5433/test ./.venv/Scripts/python.exe -m pytest -q; ./.venv/Scripts/ruff.exe check .
# Frontend build                        cd frontend; npm run build
# PR review comments                    gh api repos/Sanjaysrinivas/JobGoblin/pulls/<n>/comments --jq '.[] | "\(.path):\(.line)\n\(.body)"'
# Demo login                            http://localhost:8080  â†’  admin@jobgoblin.local / goblin-demo-pass-123
```
