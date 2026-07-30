param(
    [switch]$SkipBuild,
    [switch]$Fresh,
    [switch]$SkipSeed,
    [switch]$Force,
    [ValidateSet("", "BALANCED", "SLA_FIRST", "REVENUE_FIRST", "FAIRNESS_FIRST")]
    [string]$PreferenceProfile = "SLA_FIRST"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$scriptDirectory = Split-Path -Parent $MyInvocation.MyCommand.Path
$repositoryRoot = Resolve-Path (Join-Path $scriptDirectory "..")
$environmentPath = Join-Path $repositoryRoot ".env"
$environmentExamplePath = Join-Path $repositoryRoot ".env.example"

Set-Location $repositoryRoot

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    throw "Docker CLI is not available. Start Docker Desktop and try again."
}

if (-not (Test-Path -LiteralPath $environmentPath)) {
    Copy-Item -LiteralPath $environmentExamplePath -Destination $environmentPath
    Write-Host "Created .env from .env.example."
}

if ($Fresh) {
    Write-Warning "Fresh mode removes only this project's Docker volumes and recreates all demo databases."
    if (-not $Force) {
        $confirmation = Read-Host "Type FRESH to continue"
        if ($confirmation -ne "FRESH") {
            throw "Fresh container setup cancelled."
        }
    }
    & docker compose --profile full-stack down --volumes --remove-orphans
    if ($LASTEXITCODE -ne 0) {
        throw "Docker Compose could not remove the previous OptiFlow stack."
    }
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

Write-Host "Starting the complete OptiFlow stack in containers..."
& docker @composeArguments
if ($LASTEXITCODE -ne 0) {
    throw "Docker Compose could not start the full stack."
}

if (-not $SkipSeed) {
    Write-Host "Restoring deterministic enterprise demo data..."
    & (Join-Path $scriptDirectory "reset-demo.ps1")
    if ($LASTEXITCODE -ne 0) {
        throw "Demo reset failed."
    }
}

if (-not $SkipSeed -and $PreferenceProfile) {
    Write-Host "Preparing mature $PreferenceProfile preference memory..."
    & docker compose --profile full-stack exec -T core-api python -m scripts.seed_preference_demo `
        --profile $PreferenceProfile `
        --apply
    if ($LASTEXITCODE -ne 0) {
        throw "Preference-memory seed failed."
    }
}

Write-Host ""
Write-Host "OptiFlow is ready. Every service is running in Docker."
Write-Host "Application: http://localhost:3000"
Write-Host "Core health: http://localhost:8000/health"
Write-Host "Stop: docker compose --profile full-stack down"
Write-Host "Start again: docker compose --profile full-stack up -d --wait"
Write-Host ""
exit 0
