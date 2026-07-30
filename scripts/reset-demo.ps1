param(
    [switch]$RecreateVolumes,
    [switch]$Force,
    [string]$ComposeProfile = $(if ($env:COMPOSE_PROFILE) { $env:COMPOSE_PROFILE } else { "full-stack" })
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
trap {
    [Console]::Error.WriteLine("ERROR: $($_.Exception.Message)")
    exit 1
}

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot = Resolve-Path (Join-Path $ScriptDir "..")
Set-Location $RepoRoot

function Import-DotEnv {
    param([string]$Path)
    if (-not (Test-Path $Path)) {
        Write-Host "No .env file found. Using current process environment."
        return
    }

    foreach ($line in Get-Content $Path) {
        $trimmed = $line.Trim()
        if (-not $trimmed -or $trimmed.StartsWith("#") -or -not $trimmed.Contains("=")) {
            continue
        }
        $parts = $trimmed.Split("=", 2)
        $key = $parts[0].Trim()
        $value = $parts[1].Trim().Trim('"').Trim("'")
        if ($key -match "^[A-Za-z_][A-Za-z0-9_]*$") {
            [Environment]::SetEnvironmentVariable($key, $value, "Process")
        }
    }
}

function Assert-DockerCompose {
    if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
        throw "Docker CLI is not available on PATH."
    }
    $previousPreference = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try {
        & docker compose version *> $null
        $exitCode = $LASTEXITCODE
    } finally {
        $ErrorActionPreference = $previousPreference
    }
    if ($exitCode -ne 0) { throw "Docker Compose v2 is not available." }
}

function Get-LocalBaseUrl {
    param([string]$PortVariable, [string]$DefaultPort)
    $port = [Environment]::GetEnvironmentVariable($PortVariable)
    if (-not $port) {
        $port = $DefaultPort
    }
    return "http://localhost:$port"
}

function Assert-RunningServices {
    $required = @("postgres", "core-api", "frontend", "crm-service", "incident-service", "workforce-service", "communication-service")
    $running = & docker compose --profile $ComposeProfile ps --services --filter "status=running"
    if ($LASTEXITCODE -ne 0) {
        throw "Could not read Docker Compose service status."
    }
    $runningSet = @{}
    foreach ($service in $running) {
        $runningSet[$service.Trim()] = $true
    }
    $missing = @($required | Where-Object { -not $runningSet.ContainsKey($_) })
    if ($missing.Count -gt 0) {
        throw "Required services are not running: $($missing -join ', '). Start with: docker compose --profile $ComposeProfile up --build -d"
    }
}

function Invoke-JsonPost {
    param(
        [string]$Url,
        [hashtable]$Headers = @{},
        [object]$Body = @{}
    )
    $json = $Body | ConvertTo-Json -Depth 8
    return Invoke-RestMethod -Method Post -Uri $Url -Headers $Headers -ContentType "application/json" -Body $json -TimeoutSec 10
}

function Wait-CoreReady {
    param([string]$CoreUrl)
    $deadline = (Get-Date).AddSeconds(90)
    while ((Get-Date) -lt $deadline) {
        try {
            $response = Invoke-WebRequest -UseBasicParsing -Method Get -Uri "$CoreUrl/health" -TimeoutSec 3
            if ($response.StatusCode -eq 200) {
                return
            }
        } catch {
            Start-Sleep -Seconds 2
        }
    }
    throw "Core API did not become healthy at $CoreUrl/health."
}

function Invoke-AdminResetFallback {
    if (-not $env:ADMIN_API_KEY) {
        throw "Core reset failed and ADMIN_API_KEY is not available for fallback service resets."
    }

    $headers = @{
        "X-Admin-Key"  = $env:ADMIN_API_KEY
        "X-Request-ID" = "reset-demo-$(Get-Date -Format yyyyMMddHHmmss)"
    }
    $services = @(
        @{ Name = "crm"; Url = "$(Get-LocalBaseUrl 'CRM_SERVICE_PORT' '8101')/admin/reset" },
        @{ Name = "incident"; Url = "$(Get-LocalBaseUrl 'INCIDENT_SERVICE_PORT' '8102')/admin/reset" },
        @{ Name = "workforce"; Url = "$(Get-LocalBaseUrl 'WORKFORCE_SERVICE_PORT' '8103')/admin/reset" },
        @{ Name = "communication"; Url = "$(Get-LocalBaseUrl 'COMMUNICATION_SERVICE_PORT' '8104')/admin/reset" }
    )

    foreach ($service in $services) {
        Write-Host "Resetting $($service.Name) through admin API..."
        Invoke-JsonPost -Url $service.Url -Headers $headers -Body @{} | Out-Null
    }
}

Import-DotEnv (Join-Path $RepoRoot ".env")
Assert-DockerCompose

if ($env:APP_ENV -eq "production" -and -not $Force) {
    throw "APP_ENV=production. Refusing to reset without -Force."
}

$coreUrl = if ($env:VITE_CORE_API_URL) { $env:VITE_CORE_API_URL.TrimEnd("/") } else { Get-LocalBaseUrl "CORE_API_PORT" "8000" }

Write-Host "OptiFlow demo reset starting."
Write-Host "Compose profile: $ComposeProfile"
Write-Host "Core API: $coreUrl"

if ($RecreateVolumes) {
    Write-Warning "This will stop the full stack and delete Docker Compose volumes for this project."
    if (-not $Force) {
        $confirmation = Read-Host "Type RECREATE to continue"
        if ($confirmation -ne "RECREATE") {
            throw "Destructive reset cancelled."
        }
    }
    & docker compose --profile $ComposeProfile down -v
    if ($LASTEXITCODE -ne 0) { throw "docker compose down -v failed." }
    & docker compose --profile $ComposeProfile up --build -d
    if ($LASTEXITCODE -ne 0) { throw "docker compose --profile $ComposeProfile up --build -d failed." }
    Wait-CoreReady -CoreUrl $coreUrl
}

Assert-RunningServices

# Normal path: ask Core to reset demo state. Core keeps admin credentials server-side.
try {
    Write-Host "Calling Core demo reset endpoint..."
    $result = Invoke-JsonPost -Url "$coreUrl/api/v1/demo/simulation/reset" -Body @{}
    if ($result.success -ne $true) {
        throw "Core reset did not return success."
    }
    if ($result.data.degraded -eq $true) {
        throw "Core reset completed in degraded mode."
    }
} catch {
    Write-Warning "Core reset failed: $($_.Exception.Message)"
    Write-Host "Trying direct service admin reset fallback..."
    Invoke-AdminResetFallback
}

try {
    $state = Invoke-RestMethod -Method Get -Uri "$coreUrl/api/v1/demo/simulation/state" -TimeoutSec 10
    Write-Host "Simulation state checked. Degraded: $($state.data.degraded)"
} catch {
    Write-Warning "Reset completed, but simulation state could not be read: $($_.Exception.Message)"
}

Write-Host "Demo reset completed successfully."
exit 0
