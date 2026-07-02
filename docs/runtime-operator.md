# Runtime Operator Runbook

This runbook covers the Phase 4 operator path for running JobGoblin with the
real local Ollama provider, optional Google OAuth, and optional Cloudflare
Tunnel access. It contains no secrets; keep real values in `.env` only.

## 1. Local Stack Baseline

Copy the template and set the local admin before the first backend boot:

```bash
cp .env.example .env
```

Required local values:

```dotenv
APP_ENV=development
APP_SECRET_KEY=<long random local secret>
AI_PROVIDER=ollama
OLLAMA_BASE_URL=http://ollama:11434
OLLAMA_MODEL=qwen2.5:7b-instruct
OLLAMA_FAST_MODEL=llama3.2:3b
ADMIN_EMAIL=<local owner email>
ADMIN_PASSWORD=<local owner password>
```

Start the local stack:

```bash
docker compose up -d --build
```

Check the Caddy entrypoint:

```bash
curl http://localhost:8080/api/health
```

## 2. Ollama Model Pull And Verification

The Compose stack includes the `ollama` service, but model downloads are stored
in the `ollama` Docker volume and must be pulled at least once.

Verify configuration and model presence:

```bash
python scripts/ollama_runtime_check.py
```

Start Ollama and pull missing default models:

```bash
python scripts/ollama_runtime_check.py --start --pull
```

Run a tiny generation probe after the models are present:

```bash
python scripts/ollama_runtime_check.py --generate
```

Equivalent manual commands:

```bash
docker compose up -d ollama
docker compose exec ollama ollama pull qwen2.5:7b-instruct
docker compose exec ollama ollama pull llama3.2:3b
docker compose exec ollama ollama list
docker compose exec ollama ollama show qwen2.5:7b-instruct
```

## 3. Switch To Real AI Provider

Set the provider values in `.env`:

```dotenv
AI_PROVIDER=ollama
OLLAMA_BASE_URL=http://ollama:11434
OLLAMA_MODEL=qwen2.5:7b-instruct
OLLAMA_FAST_MODEL=llama3.2:3b
```

Restart the backend after changing provider values:

```bash
docker compose up -d --build backend
```

For fast local iteration without a model, set `AI_PROVIDER=mock`, restart the
backend, and skip the Ollama model check.

## 4. Runtime Smoke Test

The runtime smoke script logs in, uploads a generated DOCX resume, verifies
resume parsing, creates a job, runs resume-to-job analysis, and generates a
cover-letter draft. It creates smoke-test records in the local database and
does not delete existing data.

Use a non-MFA local smoke admin. MFA-enabled accounts are intentionally rejected
because automated second-factor entry should not be part of this check.

```bash
python scripts/runtime_smoke.py --email owner@example.com --password "<password>"
```

Or set local-only smoke variables in `.env`:

```dotenv
RUNTIME_SMOKE_EMAIL=owner@example.com
RUNTIME_SMOKE_PASSWORD=<local password>
RUNTIME_SMOKE_BASE_URL=http://localhost:8080/api
```

Then run:

```bash
python scripts/runtime_smoke.py
```

Expected result:

- `/api/health` returns JSON.
- `/api/auth/login` returns the smoke user.
- Resume upload returns `parsed_json`.
- `POST /api/analysis/resume-job` returns an `overall_score` and explanation.
- `POST /api/cover-letters` returns non-empty draft content.

## 5. Google OAuth Checklist

Leave Google values empty until the Cloudflare hostname is known. With empty
values, Google endpoints fail closed with `google_not_configured`.

Google Cloud Console checklist:

- Create an OAuth client for a web application.
- Add the tunnel callback as an authorized redirect URI:
  `<OAUTH_REDIRECT_BASE_URL>/api/auth/google/callback`
- Use the same public origin for `OAUTH_REDIRECT_BASE_URL`, for example
  `https://jobs.example.com`.
- Put only invited owner/friend emails in `ALLOWED_EMAILS`.
- Keep `GOOGLE_CLIENT_SECRET` only in local `.env`; never commit it.

Required `.env` shape:

```dotenv
GOOGLE_CLIENT_ID=<client id>
GOOGLE_CLIENT_SECRET=<client secret>
OAUTH_REDIRECT_BASE_URL=https://jobs.example.com
ALLOWED_EMAILS=owner@example.com,friend@example.com
```

Validation:

```bash
curl -I https://jobs.example.com/api/auth/google/login
```

Expected behavior is a redirect to Google when configured. An unallowlisted
Google account must fail with `not_allowlisted` after callback.

## 6. Cloudflare Tunnel Bring-Up

Create the tunnel in Cloudflare Zero Trust and configure its public hostname to
serve the local Compose origin:

```text
Public hostname service: http://caddy:80
```

Token-based Compose mode:

```dotenv
CLOUDFLARED_TUNNEL_TOKEN=<token from Cloudflare>
```

Start and verify:

```bash
python scripts/cloudflare_tunnel_check.py --start --public-url https://jobs.example.com
```

Manual equivalent:

```bash
docker compose --profile tunnel up -d cloudflared
docker compose --profile tunnel ps cloudflared
docker compose --profile tunnel logs --tail=80 cloudflared
curl https://jobs.example.com/api/health
```

Named-tunnel config-file mode is documented in
`infra/cloudflared-config.example.yml`. Keep the real config and credentials
ignored or outside git-tracked paths.

## 7. HTTPS Cookie Verification

For tunnel use, set production-like values and restart the stack:

```dotenv
APP_ENV=production
OAUTH_REDIRECT_BASE_URL=https://jobs.example.com
```

Production mode requires a non-default `APP_SECRET_KEY` and non-default database
credentials. Verify in the browser developer tools that `jg_session` and
`jg_oauth_state` are `Secure`, `HttpOnly`, and `SameSite=Lax` when accessed via
the HTTPS tunnel URL.
