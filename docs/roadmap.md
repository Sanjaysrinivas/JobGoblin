# JobGoblin Roadmap And Phases

Last updated: 2026-07-01.

This roadmap tracks the practical build order from the current `dev` branch. It
is intentionally phase-based rather than date-based because the project is a
private self-hosted tool and depends on local verification, OAuth setup, and the
owner's laptop runtime.

## Phase 0: Restore A Usable Local App

Goal: make the browser app usable through `http://localhost:8080` so every later
feature can be tested end to end.

Scope:

- Make `jg_session` and `jg_mfa` cookie `Secure` flags environment-aware.
- Decide and implement the MFA enrollment UX: mandatory gate or skippable nudge.
- Align frontend auth helpers with the backend's flat auth response shape.
- Add an app-shell auth guard or a consistent unauthenticated redirect pattern.
- Keep Google OAuth disabled gracefully until credentials are configured.

Exit criteria:

- Demo admin can log in through Caddy on `http://localhost:8080`.
- `/api/auth/me` returns the current user after browser login.
- Backend auth tests cover development cookie behavior and MFA branching.
- Backend ruff/pytest and frontend lint/build are run locally.

## Phase 1: Delivery Foundation

Goal: reduce merge conflicts and catch frontend breakage before broader feature
fan-out.

Scope:

- Add backend route auto-discovery for `app/api/routes/*.py` modules that export
  `router`.
- Add GitHub Actions frontend CI: `npm ci`, `npm run lint`, `npm run build`. Completed in `.github/workflows/ci.yml`.
- Refresh project docs when behavior changes, especially README, design, and this
  roadmap.
- Confirm `HANDOVER.md` is intentionally tracked or intentionally local-only.

Exit criteria:

- New route modules no longer require editing `backend/app/main.py`.
- CI includes backend ruff/pytest and frontend lint/build.
- The docs describe the actual local Docker/Caddy/Ollama architecture.

## Phase 2: Core Resource Modules

Goal: expose the existing database model through focused, isolated API and UI
modules.

Recommended order:

1. Jobs: CRUD API, ownership tests, list/create/detail/edit UI.
2. Contacts: CRUD API, optional job link validation, contact management UI.
3. Applications: CRUD API, unique `(user_id, job_id)` behavior, status changes,
   `activity_events`, pipeline UI.
4. Dashboard: summary counts, follow-up due count, average analysis score, recent
   activity timeline.
5. Cover letters: AI-generated drafts, edit/status workflow, no external sending.

Exit criteria:

- Each user-owned query is scoped by `user_id`.
- Cross-user access returns 404 or 401 without leaking object existence.
- Frontend pages stop using placeholder figures for implemented resources.
- Activity events are written for meaningful user actions.

## Phase 3: Resume-To-Job Analysis

Goal: deliver the signature ATS-style estimated match feature.

Scope:

- Deterministic keyword extraction from job descriptions and resumes.
- Exact and fuzzy matching using `rapidfuzz` (already in backend dependencies).
- Weighted category scoring: keyword, skills, experience, role, education,
  formatting.
- AI explanation and recommendations through the existing `AIProvider`.
- Persist results to `JobAnalysis` and label scores as estimates in the UI.

Exit criteria:

- Analysis can be run for an owned resume and owned job.
- Analysis cannot cross user boundaries.
- Tests cover deterministic scoring and provider-mocked AI output.
- UI shows matched keywords, missing keywords, recommendations, and the estimate
  disclaimer.

## Phase 4: Real Local Runtime And External Access

Goal: move from mock/dev behavior to the intended private self-hosted runtime.

Scope:

- Pull and verify `qwen2.5:7b-instruct` in Ollama.
- Set `AI_PROVIDER=ollama` and smoke-test resume parsing and generation.
- Configure Google OAuth credentials and allowlisted users.
- Add Cloudflare Tunnel service/config after local auth is stable.
- Verify secure-cookie behavior under HTTPS tunnel access.

Exit criteria:

- Owner and allowlisted friends can sign in through the tunnel URL.
- AI features work through Ollama without external API keys.
- The app remains non-public: allowlist and human-review gates remain intact.

## Phase 5: V2 Workflow Expansion

Goal: deepen the job-search workflow after the MVP loop is usable.

Scope:

- Profile builder from parsed resumes and user edits.
- Resume versions and tailored resume drafts.
- Outreach draft generation with review-only status transitions.
- Follow-up reminders.
- Email draft/export integration; no auto-send without explicit review.
- Interview prep assistant.

Exit criteria:

- External actions remain approval-gated.
- AI-generated content remains grounded in user-provided facts.
- New tables and migrations are introduced only when the workflow needs them.
