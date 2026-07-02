param(
    [string]$Python = "python",
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$PytestArgs
)

$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = Resolve-Path (Join-Path $scriptDir "..\..")
$composeFile = Join-Path $repoRoot "test\e2e\docker-compose.backend-tests.yml"
$pythonCommand = $Python
if ($Python -match "[\\/]") {
    $pythonCommand = (Resolve-Path $Python).Path
}

Push-Location $repoRoot
try {
    docker compose -f $composeFile -p jobgoblin-backend-tests up -d test-db

    $ready = $false
    for ($attempt = 1; $attempt -le 30; $attempt++) {
        docker compose -f $composeFile -p jobgoblin-backend-tests exec -T test-db pg_isready -U test -d test | Out-Null
        if ($LASTEXITCODE -eq 0) {
            $ready = $true
            break
        }
        Start-Sleep -Seconds 2
    }

    if (-not $ready) {
        docker compose -f $composeFile -p jobgoblin-backend-tests logs --no-color test-db
        throw "Timed out waiting for the backend test database."
    }

    if (-not $PytestArgs) {
        $PytestArgs = @("-q")
    }

    Push-Location (Join-Path $repoRoot "backend")
    try {
        $env:TEST_DATABASE_URL = "postgresql+psycopg://test:test@localhost:5433/test"
        & $pythonCommand -m pytest @PytestArgs
        exit $LASTEXITCODE
    }
    finally {
        Pop-Location
    }
}
finally {
    Pop-Location
}

