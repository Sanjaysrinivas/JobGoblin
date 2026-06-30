# 👺 JobGoblin

A self-hosted, AI-powered job-search and application-management web app. Upload a
resume, score it against any job description, surface missing keywords, generate
tailored bullets / cover letters / outreach, and track every application from
*saved* to *offer*.

> **A private productivity tool — not a spam or auto-apply bot.** Every external
> action (email, recruiter outreach, applying) requires explicit human review and
> approval. The AI never invents experience, skills, or credentials.

## Architecture at a glance

Two independently-deployed services talking over HTTP/JSON:

| Layer | Tech | Free host |
|-------|------|-----------|
| Frontend | Next.js · React · TypeScript · Tailwind · shadcn/ui | Vercel |
| Backend | FastAPI · Python · Pydantic · SQLModel | Render |
| Database | PostgreSQL | Neon |
| File storage | Object storage (resume files) | Cloudflare R2 |
| AI | Pluggable provider (OpenAI / Anthropic / Ollama / Mock) | — |

**Full interactive architecture doc:** open [`docs/architecture.html`](docs/architecture.html)
in a browser.

## Repository layout

```
jobgoblin/
├── backend/            # FastAPI service
├── frontend/           # Next.js service
├── docs/               # architecture.html, architecture.md
├── docker-compose.yml  # local dev: frontend + backend + postgres
├── .env.example
└── README.md
```

*(backend/ and frontend/ are scaffolded in subsequent feature branches.)*

## Local development

The whole stack is **Docker-first** — runs locally for free with one command:

```bash
cp .env.example .env      # fill in your AI provider key
docker compose up --build
```

Frontend → http://localhost:3000 · Backend → http://localhost:8000 (docs at `/docs`).

## Branching workflow

`main → dev → feature/*`. `main` stays release-ready, `dev` is integration, and
every change rides a `feature/*` branch merged into `dev` via pull request.

## Roadmap

- **V1 (MVP, current):** auth · resume upload + extraction · job CRUD · resume↔job
  analysis · ATS-style score · cover letters · application tracker · dashboard.
- **V2:** resume versions · tailored drafts · contacts · outreach · reminders.
- **V3:** Gmail drafts · calendar · browser extension · local LLM (Ollama).
- **V4:** assisted (approval-gated) automation · interview prep assistant.
