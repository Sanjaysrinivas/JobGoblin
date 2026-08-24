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

The default `tunnel` profile uses Cloudflare Quick Tunnel. It requires no
Cloudflare account login and creates a fresh shareable `trycloudflare.com` URL
each time the `cloudflared` container starts:

```bash
python scripts/cloudflare_tunnel_check.py --start
```

Manual equivalent:

```bash
docker compose --profile tunnel up -d cloudflared
docker compose --profile tunnel ps cloudflared
docker compose --profile tunnel logs --tail=80 cloudflared
```

Copy the `https://*.trycloudflare.com` URL from the logs and share that while
the local stack is running. To start the quick tunnel with every normal Compose
startup, set `COMPOSE_PROFILES=tunnel` in local `.env`.

Signup remains invite-only unless `PUBLIC_SIGNUP_ENABLED=true` is set. Enable
that only when everyone with the tunnel URL should be able to create an account.

Stable named tunnels are still available through the `named-tunnel` profile.
Create the tunnel in Cloudflare Zero Trust, point its public hostname at
`http://caddy:80`, set `CLOUDFLARED_TUNNEL_TOKEN`, then start
`docker compose --profile named-tunnel up -d cloudflared-named`. Config-file
mode is documented in `infra/cloudflared-config.example.yml`. Keep real config
and credentials ignored or outside git-tracked paths.

## 7. HTTPS Cookie Verification

For a stable named tunnel, set production-like values and restart the stack:

```dotenv
APP_ENV=production
OAUTH_REDIRECT_BASE_URL=https://jobs.example.com
```

Production mode requires a non-default `APP_SECRET_KEY` and non-default database
credentials. Verify in the browser developer tools that `jg_session` and
`jg_oauth_state` are `Secure`, `HttpOnly`, and `SameSite=Lax` when accessed via
the HTTPS tunnel URL.

## 8. Health, Readiness, And Logs

`/api/health` is the liveness probe. It only proves FastAPI can answer a request
and intentionally does not touch PostgreSQL.

`/api/health/ready` is the readiness probe. It runs `SELECT 1` through the
configured SQLAlchemy engine and returns `503` with `database_unavailable` when
PostgreSQL is not reachable.

```bash
curl http://localhost:8080/api/health
curl http://localhost:8080/api/health/ready
docker compose logs --tail=120 backend db
docker compose exec db pg_isready -U jobgoblin -d jobgoblin
```

If liveness passes but readiness fails, check the `db` container, `DATABASE_URL`,
Postgres credentials, and whether migrations/startup are still running.

## 9. Observability And LLM Diagnostics

LLM observability is opt-in. It records provider, model, operation, prompt hash,
prompt length, schema hash, latency, and error type. It must not record raw
resume text, profile facts, prompts, job descriptions, tokens, or secrets.

```dotenv
OBSERVABILITY_ENABLED=false
```

Set it to `true` only when the target observability package/config is available,
then restart the backend:

```bash
docker compose up -d --build backend
docker compose logs --tail=120 backend
```

For Ollama failures, run these operator checks on the machine with the model
volume and GPU/runtime access:

```bash
python scripts/ollama_runtime_check.py
python scripts/ollama_runtime_check.py --start --pull
python scripts/ollama_runtime_check.py --generate
docker compose logs --tail=120 ollama backend
docker compose exec ollama ollama list
```

Common causes: the `ollama` service is stopped, the model was never pulled, the
model name in `.env` does not match `ollama list`, the first load is slow, or the
model returned malformed JSON and the app fell back to deterministic behavior.

## 10. Adzuna Discovery Smoke Path

Adzuna requires real credentials. Do not mark this smoke as passed unless an
operator has run it with live `ADZUNA_APP_ID` and `ADZUNA_APP_KEY`.

```dotenv
JOB_DISCOVERY_PROVIDER=adzuna
ADZUNA_BASE_URL=https://api.adzuna.com/v1/api
ADZUNA_APP_ID=<operator-provided id>
ADZUNA_APP_KEY=<operator-provided key>
```

Restart the backend after changing provider settings:

```bash
docker compose up -d --build backend
curl http://localhost:8080/api/health/ready
```

Operator-run browser smoke:

1. Sign in through `http://localhost:8080`.
2. Open `/discover`.
3. Save preferences with a small country/location/query.
4. Run discovery and verify the run completes with reviewable results.
5. Save one selected result as a normal job.

Operator-run API smoke, using a local non-MFA account:

```bash
curl -c /tmp/jg.cookie -H "Content-Type: application/json" \
  -d '{"email":"owner@example.com","password":"<password>"}' \
  http://localhost:8080/api/auth/login
curl -b /tmp/jg.cookie -H "Content-Type: application/json" \
  -d '{"provider":"adzuna","country":"us","query":"python fastapi","results_per_page":5}' \
  http://localhost:8080/api/discovery/runs
```

Discovery is read-only toward employers and job boards: it finds, stores, ranks,
dismisses, and saves candidate roles. It does not auto-apply, send email, contact
recruiters, submit forms, or perform silent outreach.

## 11. Cloudflare Tunnel And OAuth Failure Modes

Quick Tunnel setup requires local Caddy to be healthy and the `cloudflared`
container to reach Cloudflare. Quick Tunnel URLs are temporary and change when
the `cloudflared` container is recreated. Named-tunnel tokens belong in local
`.env` only. Never commit a token, named-tunnel credential file, Google client
secret, or real operator hostname if it should stay private.

Troubleshooting commands:

```bash
python scripts/cloudflare_tunnel_check.py --start
docker compose --profile tunnel logs --tail=120 cloudflared
curl http://localhost:8080/api/health/ready
```

The script reads the generated `trycloudflare.com` URL from logs. Pass
`--public-url https://jobs.example.com` only when validating a stable named
tunnel. Common quick-tunnel failures: local Caddy not
healthy, Docker not running, Cloudflare edge connectivity blocked, or the
temporary URL not emitted yet. Common named-tunnel failures: empty
`CLOUDFLARED_TUNNEL_TOKEN`, hostname pointed at the wrong service, DNS still
propagating, or cloudflared running with an old token.

Google OAuth must use the same public base URL that users open in the browser:

```dotenv
OAUTH_REDIRECT_BASE_URL=https://jobs.example.com
```

Authorized redirect URI in Google Cloud Console:

```text
https://jobs.example.com/api/auth/google/callback
```

Common OAuth failures: `google_not_configured` means credentials are empty,
`redirect_uri_mismatch` means Google Console and `OAUTH_REDIRECT_BASE_URL` differ,
and `not_allowlisted` means the Google account is not in `ALLOWED_EMAILS`.

## 12. Backup And Restore

Back up both PostgreSQL and uploaded files. The database alone is not enough
because resume originals live in the uploads volume.

Operator-run backup:

```bash
mkdir -p backups
docker compose exec -T db pg_dump -U jobgoblin -d jobgoblin > backups/jobgoblin.sql
docker compose run --rm -v jobgoblin_uploads:/data/uploads -v "${PWD}/backups:/backup" backend \
  tar -czf /backup/uploads.tgz -C /data uploads
```

Operator-run restore into a stopped or disposable environment first:

```bash
docker compose up -d db
docker compose exec -T db psql -U jobgoblin -d jobgoblin < backups/jobgoblin.sql
docker compose run --rm -v jobgoblin_uploads:/data/uploads -v "${PWD}/backups:/backup" backend \
  tar -xzf /backup/uploads.tgz -C /data
curl http://localhost:8080/api/health/ready
```

Before restoring over important data, take a fresh backup and confirm the target
Compose project/volumes are the ones you intend to replace.

## 13. Migrations And Rollback

The backend image runs Alembic migrations on startup. For normal updates:

```bash
git fetch origin
git checkout dev
git pull --ff-only
docker compose up -d --build
curl http://localhost:8080/api/health/ready
```

Before any migration-bearing update, take the backup in section 12. If startup or
readiness fails after an update, inspect logs first:

```bash
docker compose logs --tail=160 backend db
```

Rollback path:

1. Stop write traffic by taking the app down or keeping it local-only.
2. Check out the previous known-good commit or release branch.
3. Rebuild the stack.
4. If the failed migration changed data/schema and downgrade is not explicitly
   proven, restore the pre-update database and uploads backup instead of guessing.
5. Re-run `/api/health/ready` and a login smoke.

## 14. Secrets Handling

`.env` is the only local place for real secrets. Keep `.env.example` populated
with names and safe placeholders only.

Rotate these if they are exposed: `APP_SECRET_KEY`, database credentials,
`GOOGLE_CLIENT_SECRET`, `CLOUDFLARED_TUNNEL_TOKEN`, Adzuna keys, and any named
Cloudflare tunnel credential file. Do not paste secrets into issue comments,
commits, screenshots, smoke logs, or AI prompts.

Production mode must not use the default app secret or default database
credentials; the backend refuses to boot when those defaults are present.

## 15. Release From dev To main

`main` stays release-ready; `dev` is the integration branch. Use this operator
path for a stable local release:

```bash
git checkout dev
git pull --ff-only
cd backend
ruff check .
pytest -q
cd ../frontend
npm run lint
npm run build
cd ..
docker compose up -d --build
curl http://localhost:8080/api/health/ready
python scripts/runtime_smoke.py
```

The real credential checks are separate operator-run gates when relevant:

```bash
python scripts/ollama_runtime_check.py --generate
python scripts/cloudflare_tunnel_check.py --public-url https://jobs.example.com
# Adzuna smoke: run section 10 with live credentials.
```

After checks pass, merge `dev` to `main` through a PR or fast-forward policy used
by the repo. Do not promote `main` based on unrun Cloudflare, OAuth, Ollama, or
Adzuna checks; leave those explicitly marked pending.
