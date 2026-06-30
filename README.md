# 👺 JobGoblin

[![CI](https://github.com/Sanjaysrinivas/JobGoblin/actions/workflows/ci.yml/badge.svg)](https://github.com/Sanjaysrinivas/JobGoblin/actions/workflows/ci.yml)
![Next.js](https://img.shields.io/badge/Next.js-frontend-000000?logo=next.js&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-backend-009688?logo=fastapi&logoColor=white)
![Python](https://img.shields.io/badge/Python-3.12+-3776AB?logo=python&logoColor=white)
![TypeScript](https://img.shields.io/badge/TypeScript-typed-3178C6?logo=typescript&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-database-4169E1?logo=postgresql&logoColor=white)
![Docker](https://img.shields.io/badge/Docker-compose-2496ED?logo=docker&logoColor=white)
![Hosting](https://img.shields.io/badge/hosting-%240%2Fmo-2ea44f)
![Status](https://img.shields.io/badge/status-MVP%20in%20progress-f5b945)

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
