# JobGoblin — Frontend

The Next.js (App Router) web client for JobGoblin. TypeScript (strict),
Tailwind CSS v4, and shadcn/ui, in the **"Goblin Workshop"** design system:
warm-neutral stone surfaces, a single goblin-green accent, lantern-amber as
the secondary signal, and a first-class dark mode.

## Stack

- **Next.js 16** (App Router, React 19, Turbopack)
- **Tailwind CSS v4** (CSS-variable tokens in `app/globals.css`)
- **shadcn/ui** (new-york style) — `components/ui/*`
- **lucide-react** icons, **next-themes** for dark mode
- Fonts (self-hosted via `next/font/google`): Sora (display),
  Plus Jakarta Sans (body), JetBrains Mono (data)

## Structure

```
frontend/
├── app/
│   ├── layout.tsx           # root layout: fonts + ThemeProvider
│   ├── page.tsx             # redirects → /dashboard
│   ├── globals.css          # design tokens (light + dark) + base styles
│   ├── login/page.tsx       # full-bleed login (outside the app shell)
│   └── (app)/               # authenticated shell (sidebar + topbar)
│       ├── layout.tsx
│       ├── dashboard/       # pipeline, activity, quick actions
│       ├── resumes/  jobs/  applications/  contacts/  settings/
├── components/
│   ├── ui/                  # shadcn primitives: button, input, card, label, badge
│   ├── app-sidebar.tsx  app-topbar.tsx
│   ├── login-form.tsx       # POSTs /api/auth/login (credentials: include)
│   ├── theme-provider.tsx  theme-toggle.tsx
│   ├── page-header.tsx  empty-state.tsx  goblin-mark.tsx
├── lib/
│   ├── api.ts               # typed fetch wrapper (always credentials: include)
│   ├── auth.ts              # login / register / logout / getCurrentUser
│   ├── types.ts             # shared API types (mirrors docs/design.md §3–4)
│   ├── nav.ts               # sidebar navigation config
│   └── utils.ts             # cn() class merge
├── Dockerfile               # multi-stage standalone production build
└── components.json          # shadcn config
```

## Develop

```bash
npm install
npm run dev      # http://localhost:3000
```

**Browser** calls go to the same origin under `/api` (production, behind
Caddy). When running `next dev` outside Docker, point the browser at the
backend directly:

```bash
# .env.local
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
```

**Server-side** calls (Server Components / Actions) need an absolute URL and
skip the Caddy hop, so `lib/api.ts` reads `INTERNAL_API_BASE_URL` (default
`http://backend:8000`). docker-compose sets this for the `frontend` service.

## Verify

```bash
npm run lint
npm run build
```

## Production / Docker

`next.config.ts` sets `output: "standalone"`, and the `Dockerfile` produces a
minimal Node 22 image. In the stack the frontend sits behind Caddy (see the
root `docker-compose.yml` + `infra/Caddyfile`):

```bash
docker compose up --build
# open http://localhost:8080  (Caddy → / = frontend, /api/* = backend)
```

## API contract

The backend auth endpoints are built in parallel on another branch. This app
codes against the agreed contract (`docs/design.md` §4):

- `POST /api/auth/login` `{email, password}` → sets session cookie, `{user}`
- `POST /api/auth/logout`, `GET /api/auth/me`, `POST /api/auth/register`

All requests use `credentials: "include"` so the HTTP-only session cookie
flows on every call.
