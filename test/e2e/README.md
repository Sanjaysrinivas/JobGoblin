# E2E and Backend Test Harness

## Backend DB Tests

The backend pytest suite expects a PostgreSQL database at:

```text
postgresql+psycopg://test:test@localhost:5433/test
```

Start the test database and run the backend tests from the repository root:

```powershell
.\test\e2e\run-backend-db-tests.ps1
```

Pass a specific Python executable when you want to use an existing virtualenv:

```powershell
.\test\e2e\run-backend-db-tests.ps1 -Python .\backend\.venv\Scripts\python.exe
```

The script uses `test/e2e/docker-compose.backend-tests.yml` and leaves the
database container running for faster repeat runs. Stop it with:

```powershell
docker compose -f .\test\e2e\docker-compose.backend-tests.yml -p jobgoblin-backend-tests down --volumes
```

## Playwright E2E

The CI E2E job starts the root Docker Compose stack through Caddy and runs:

```powershell
cd frontend
$env:PLAYWRIGHT_BASE_URL = "http://127.0.0.1:8080"
npx playwright test
```

For local full-stack E2E, configure `.env` with `AI_PROVIDER=mock`,
`ADMIN_EMAIL=admin@jobgoblin.local`, and
`ADMIN_PASSWORD=goblin-demo-pass-123`, then start:

```powershell
docker compose up -d --build db backend frontend caddy
```
