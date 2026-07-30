param(
    [switch]$SkipBuild,
    [switch]$SkipInstall,
    [switch]$ResetData,
    [ValidateSet("", "BALANCED", "SLA_FIRST", "REVENUE_FIRST", "FAIRNESS_FIRST")]
    [string]$PreferenceProfile = ""
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$scriptDirectory = Split-Path -Parent $MyInvocation.MyCommand.Path
$repositoryRoot = Resolve-Path (Join-Path $scriptDirectory "..")
$frontendDirectory = Join-Path $repositoryRoot "frontend"
$environmentPath = Join-Path $repositoryRoot ".env"
$environmentExamplePath = Join-Path $repositoryRoot ".env.example"

Set-Location $repositoryRoot

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    throw "Docker CLI is not available. Start Docker Desktop and try again."
}

if (-not (Get-Command npm.cmd -ErrorAction SilentlyContinue)) {
    throw "npm is not available. Install Node.js 22 LTS and try again."
}

if (-not (Test-Path -LiteralPath $environmentPath)) {
    Copy-Item -LiteralPath $environmentExamplePath -Destination $environmentPath
    Write-Host "Created .env from .env.example."
}

$composeArguments = @(
    "compose",
    "--profile", "full-stack",
    "up",
    "-d",
    "--wait"
)
if (-not $SkipBuild) {
    $composeArguments += "--build"
}

Write-Host "Starting OptiFlow backend services..."
& docker @composeArguments
if ($LASTEXITCODE -ne 0) {
    throw "Docker Compose could not start the backend."
}

if ($ResetData) {
    Write-Host "Restoring deterministic enterprise demo data..."
    & (Join-Path $scriptDirectory "reset-demo.ps1")
    if ($LASTEXITCODE -ne 0) {
        throw "Demo reset failed."
    }
}

if ($PreferenceProfile) {
    Write-Host "Preparing mature $PreferenceProfile preference memory..."
    & docker compose exec -T core-api python -m scripts.seed_preference_demo `
        --profile $PreferenceProfile `
        --decisions 18 `
        --preferred-count 14 `
        --apply
    if ($LASTEXITCODE -ne 0) {
        throw "Preference-memory seed failed."
    }
}

Set-Location $frontendDirectory
if (-not $SkipInstall) {
    Write-Host "Installing frontend dependencies..."
    & npm.cmd install
    if ($LASTEXITCODE -ne 0) {
        throw "Frontend dependency installation failed."
    }
}

Write-Host ""
Write-Host "Backend: http://localhost:8000"
Write-Host "Frontend: http://localhost:3000"
Write-Host "Press Ctrl+C to stop the local frontend. Docker services keep running."
Write-Host ""

& npm.cmd run dev -- --host 0.0.0.0
exit $LASTEXITCODE
