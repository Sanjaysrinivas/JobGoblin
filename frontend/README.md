# JobGoblin Frontend

The Next.js App Router web client for JobGoblin. It uses TypeScript strict mode, Tailwind CSS v4, shadcn/ui primitives, lucide-react icons, and a private-workspace UI built around the app shell in `app/(app)`.

## Stack

- Next.js 16, React 19, App Router, Turbopack in dev.
- Tailwind CSS v4 with CSS-variable tokens in `app/globals.css`.
- shadcn/ui primitives in `components/ui/*`.
- lucide-react icons and next-themes dark mode.
- Fonts loaded through `next/font/google`: Sora, Plus Jakarta Sans, JetBrains Mono.

## Structure

```text
frontend/
|-- app/
|   |-- layout.tsx                 # root layout: fonts + ThemeProvider
|   |-- page.tsx                   # redirects to /dashboard
|   |-- globals.css                # design tokens and base styles
|   |-- login/page.tsx             # login outside the app shell
|   `-- (app)/                     # authenticated shell protected by AuthGate
|       |-- layout.tsx
|       |-- dashboard/
|       |-- resumes/
|       |-- resumes/[id]/
|       |-- jobs/
|       |-- applications/
|       |-- contacts/
|       |-- outreach/
|       |-- profile/
|       `-- settings/
|-- components/
|   |-- ui/                        # shadcn primitives
|   |-- contacts/                  # contact forms and list views
|   |-- dashboard/                 # dashboard summary/activity view
|   |-- jobs/                      # jobs list/detail/edit views
|   |-- outreach/                  # review-only outreach draft UI
|   |-- profile/                   # profile builder view
|   |-- resumes/                   # resume upload/list/detail views
|   |-- auth-gate.tsx
|   |-- app-sidebar.tsx
|   |-- app-topbar.tsx
|   |-- login-form.tsx
|   |-- mfa-form.tsx
|   |-- page-header.tsx
|   `-- empty-state.tsx
|-- lib/
|   |-- api.ts                     # typed fetch wrapper, credentials included
|   |-- auth.ts                    # auth API helpers
|   |-- resumes.ts                 # resume API helpers, including PDF export
|   |-- jobs.ts                    # jobs API helpers
|   |-- contacts.ts                # contacts API helpers
|   |-- applications.ts            # applications and follow-up helper calls
|   |-- cover-letters.ts           # local cover-letter draft helpers
|   |-- dashboard.ts               # dashboard summary/activity helpers
|   |-- analysis.ts                # resume-to-job analysis helpers
|   |-- outreach.ts                # review-only local outreach draft helpers
|   |-- profile.ts                 # private profile builder helpers
|   |-- types.ts                   # shared API-facing types
|   |-- nav.ts                     # sidebar navigation config
|   `-- utils.ts                   # cn() class merge
|-- Dockerfile                     # standalone production build
`-- components.json                # shadcn config
```

## Develop

Install dependencies and run the frontend directly:

```bash
npm install
npm run dev
```

Direct frontend dev runs at http://localhost:3000. In that mode, point browser API calls at the backend:

```dotenv
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
```

The preferred full-stack path is still the root Docker Compose stack through Caddy:

```bash
docker compose up -d --build
# open http://localhost:8080
```

In Docker, browser calls use the same-origin `/api` prefix through Caddy. Server-side calls need an absolute URL, so `lib/api.ts` reads `INTERNAL_API_BASE_URL`; `docker-compose.yml` sets it to `http://backend:8000`.

## Current API Usage

The frontend currently talks to implemented backend endpoints for:

- Auth: login, invite-only signup, logout, current user, MFA challenge/enroll/verify, and Google OAuth redirect entry points.
- Resumes: upload, list, detail, edit, delete, re-parse, version management, and PDF export.
- Jobs: list, create, detail, edit, delete, and saved analysis history.
- Contacts: list, create, detail, edit, and delete.
- Applications: list, create, edit, delete, manual status tracking, follow-up reminder fields, workflow context, next action, and active/due/interview/outcome filters.
- Dashboard: summary counts and recent activity.
- Resume-to-job analysis: run an estimated match and fetch saved results.
- Cover letters: create grounded job/resume drafts from job detail, edit content, and update local review status.
- Tailored resume drafts: create job-specific grounded resume-version drafts, review changes, accept/reject, and export PDF.
- Outreach: local review-only draft list/create/edit/delete/generate/export flows; no email or external send action is performed.
- Discovery: reviewable results only; saving a discovered role creates a normal job and does not apply, contact employers, or send silent outreach.
- Interview prep: generate grounded question sets, STAR/story-bank prompts, notes, copy/export text, and prep status.
- Profile: view, save, delete, and seed a private profile from parsed resume facts.

All API requests use `credentials: "include"` so the HTTP-only session cookie flows with same-origin Docker/Caddy requests and direct dev requests.

## Verify

```bash
npm run lint
npm run build
```

The same commands run in GitHub Actions for pull requests.

## Production / Docker

`next.config.ts` sets `output: "standalone"`, and the Dockerfile produces the frontend image used by the root compose stack. Caddy is the public local entry point on http://localhost:8080 and routes `/api/*` to FastAPI while serving everything else from Next.js. Runtime operator checks, Cloudflare/OAuth setup, Adzuna smoke, and release gates live in `../docs/runtime-operator.md`.
