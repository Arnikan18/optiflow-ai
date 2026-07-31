param(
    [int]$TimeoutSeconds = 3,
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
    if (-not (Test-Path $Path)) { return }
    foreach ($line in Get-Content $Path) {
        $trimmed = $line.Trim()
        if (-not $trimmed -or $trimmed.StartsWith("#") -or -not $trimmed.Contains("=")) { continue }
        $parts = $trimmed.Split("=", 2)
        $key = $parts[0].Trim()
        $value = $parts[1].Trim().Trim('"').Trim("'")
        if ($key -match "^[A-Za-z_][A-Za-z0-9_]*$") {
            [Environment]::SetEnvironmentVariable($key, $value, "Process")
        }
    }
}

function Get-LocalBaseUrl {
    param([string]$PortVariable, [string]$DefaultPort)
    $port = [Environment]::GetEnvironmentVariable($PortVariable)
    if (-not $port) { $port = $DefaultPort }
    return "http://localhost:$port"
}

function Test-HttpComponent {
    param([string]$Name, [string]$Url, [bool]$ParseOverall = $false)
    $watch = [System.Diagnostics.Stopwatch]::StartNew()
    try {
        $response = Invoke-WebRequest -UseBasicParsing -Method Get -Uri $Url -TimeoutSec $TimeoutSeconds
        $watch.Stop()
        $status = if ($response.StatusCode -ge 200 -and $response.StatusCode -lt 300) { "HEALTHY" } else { "UNHEALTHY" }
        $message = "HTTP $($response.StatusCode)"
        if ($ParseOverall -and $response.Content) {
            try {
                $json = $response.Content | ConvertFrom-Json
                if ($json.success -eq $true -and $json.data.overall_status) {
                    $status = $json.data.overall_status
                    $message = "aggregate overall_status=$status"
                }
            } catch {
                $status = "DEGRADED"
                $message = "Could not parse aggregate health JSON"
            }
        }
        return [pscustomobject]@{ Component = $Name; Check = $Url; Status = $status; ResponseMs = [math]::Round($watch.Elapsed.TotalMilliseconds, 2); HttpStatus = $response.StatusCode; Message = $message }
    } catch {
        $watch.Stop()
        return [pscustomobject]@{ Component = $Name; Check = $Url; Status = "UNHEALTHY"; ResponseMs = [math]::Round($watch.Elapsed.TotalMilliseconds, 2); HttpStatus = ""; Message = $_.Exception.Message }
    }
}

function Test-Postgres {
    $watch = [System.Diagnostics.Stopwatch]::StartNew()
    try {
        & docker compose --profile $ComposeProfile exec -T postgres pg_isready -U $env:POSTGRES_USER -d $env:POSTGRES_DB *> $null
        $exitCode = $LASTEXITCODE
        $watch.Stop()
        if ($exitCode -eq 0) {
            return [pscustomobject]@{ Component = "postgres"; Check = "docker compose exec pg_isready"; Status = "HEALTHY"; ResponseMs = [math]::Round($watch.Elapsed.TotalMilliseconds, 2); HttpStatus = ""; Message = "pg_isready passed" }
        }
        return [pscustomobject]@{ Component = "postgres"; Check = "docker compose exec pg_isready"; Status = "UNHEALTHY"; ResponseMs = [math]::Round($watch.Elapsed.TotalMilliseconds, 2); HttpStatus = ""; Message = "pg_isready failed" }
    } catch {
        $watch.Stop()
        return [pscustomobject]@{ Component = "postgres"; Check = "docker compose exec pg_isready"; Status = "UNHEALTHY"; ResponseMs = [math]::Round($watch.Elapsed.TotalMilliseconds, 2); HttpStatus = ""; Message = $_.Exception.Message }
    }
}

Import-DotEnv (Join-Path $RepoRoot ".env")

$coreUrl = if ($env:VITE_CORE_API_URL) { $env:VITE_CORE_API_URL.TrimEnd("/") } else { Get-LocalBaseUrl "CORE_API_PORT" "8000" }
$checks = @(
    @{ Name = "frontend"; Url = "$(Get-LocalBaseUrl 'FRONTEND_PORT' '3000')/"; Parse = $false },
    @{ Name = "core-api"; Url = "$coreUrl/health"; Parse = $false },
    @{ Name = "core-demo-health"; Url = "$coreUrl/api/v1/demo/health"; Parse = $true },
    @{ Name = "crm-service"; Url = "$(Get-LocalBaseUrl 'CRM_SERVICE_PORT' '8101')/health"; Parse = $false },
    @{ Name = "incident-service"; Url = "$(Get-LocalBaseUrl 'INCIDENT_SERVICE_PORT' '8102')/health"; Parse = $false },
    @{ Name = "workforce-service"; Url = "$(Get-LocalBaseUrl 'WORKFORCE_SERVICE_PORT' '8103')/health"; Parse = $false },
    @{ Name = "communication-service"; Url = "$(Get-LocalBaseUrl 'COMMUNICATION_SERVICE_PORT' '8104')/health"; Parse = $false }
)

$results = @()
$results += Test-Postgres
foreach ($check in $checks) {
    $results += Test-HttpComponent -Name $check.Name -Url $check.Url -ParseOverall $check.Parse
}

$overall = if ($results | Where-Object { $_.Status -eq "UNHEALTHY" }) {
    "UNHEALTHY"
} elseif ($results | Where-Object { $_.Status -eq "DEGRADED" }) {
    "DEGRADED"
} else {
    "HEALTHY"
}

Write-Host "OptiFlow health check"
$results | Format-Table Component, Check, Status, ResponseMs, HttpStatus, Message -AutoSize
Write-Host "Overall: $overall"

if ($overall -eq "HEALTHY") { exit 0 }
exit 1
