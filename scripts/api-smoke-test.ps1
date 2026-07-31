Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot = Resolve-Path (Join-Path $ScriptDir "..")
Set-Location $RepoRoot

function Import-DotEnv {
    param([string]$Path)
    if (-not (Test-Path $Path)) { return }
    foreach ($line in Get-Content $Path) {
        $trimmed = $line.Trim()
        if (-not $trimmed -or $trimmed.StartsWith("#") -or -not $trimmed.Contains("=")) { continue }
        $key, $value = $trimmed.Split("=", 2)
        $key = $key.Trim()
        $value = $value.Trim().Trim('"').Trim("'")
        if ($key -match "^[A-Za-z_][A-Za-z0-9_]*$") {
            [Environment]::SetEnvironmentVariable($key, $value, "Process")
        }
    }
}

function Env-OrDefault {
    param([string]$Name, [string]$Default)
    $value = [Environment]::GetEnvironmentVariable($Name, "Process")
    if ([string]::IsNullOrWhiteSpace($value)) { return $Default }
    return $value
}

function Invoke-Check {
    param(
        [string]$Name,
        [string]$Method,
        [string]$Url,
        [hashtable]$Headers = @{},
        [object]$Body = $null,
        [int[]]$ExpectedStatus = @(200)
    )

    $status = 0
    $ok = $false
    $failureMessage = ""
    try {
        $params = @{
            Method = $Method
            Uri = $Url
            Headers = $Headers
            TimeoutSec = 15
            UseBasicParsing = $true
        }
        if ($null -ne $Body) {
            $params["ContentType"] = "application/json"
            $params["Body"] = ($Body | ConvertTo-Json -Depth 20)
        }
        $response = Invoke-WebRequest @params
        $status = [int]$response.StatusCode
        $ok = $ExpectedStatus -contains $status
    } catch {
        $failureMessage = $_.Exception.Message
        $responseProperty = $_.Exception.PSObject.Properties["Response"]
        if ($null -ne $responseProperty -and $null -ne $responseProperty.Value) {
            $statusCodeProperty = $responseProperty.Value.PSObject.Properties["StatusCode"]
            if ($null -ne $statusCodeProperty) {
                $status = [int]$statusCodeProperty.Value
            }
        }
        $ok = $false
    }

    if ($ok) {
        Write-Host ("PASS {0,-42} HTTP {1}" -f $Name, $status)
        return $true
    }
    Write-Host ("FAIL {0,-42} HTTP {1} {2}" -f $Name, $status, $failureMessage)
    return $false
}

Import-DotEnv (Join-Path $RepoRoot ".env")

$Core = "http://localhost:$(Env-OrDefault "CORE_API_PORT" "8000")"
$Crm = "http://localhost:$(Env-OrDefault "CRM_SERVICE_PORT" "8101")"
$Incident = "http://localhost:$(Env-OrDefault "INCIDENT_SERVICE_PORT" "8102")"
$Workforce = "http://localhost:$(Env-OrDefault "WORKFORCE_SERVICE_PORT" "8103")"
$Communication = "http://localhost:$(Env-OrDefault "COMMUNICATION_SERVICE_PORT" "8104")"
$ToolToken = Env-OrDefault "TOOL_SHARED_TOKEN" "change-me"
$AdminKey = Env-OrDefault "ADMIN_API_KEY" "change-me-admin"
$ScenarioId = Env-OrDefault "SIMULATION_DEFAULT_SCENARIO" "product_release_day"
$RequestId = "SMOKE-$([guid]::NewGuid().ToString("N").Substring(0, 12).ToUpper())"

$ToolHeaders = @{
    "X-Tool-Token" = $ToolToken
    "X-Request-ID" = $RequestId
}
$AdminHeaders = @{
    "X-Admin-Key" = $AdminKey
    "X-Request-ID" = $RequestId
}

$results = @()
$results += Invoke-Check "Core API health" "GET" "$Core/health"
$results += Invoke-Check "CRM health" "GET" "$Crm/health"
$results += Invoke-Check "Incident health" "GET" "$Incident/health"
$results += Invoke-Check "Workforce health" "GET" "$Workforce/health"
$results += Invoke-Check "Communication health" "GET" "$Communication/health"
$results += Invoke-Check "List simulation scenarios" "GET" "$Core/api/v1/simulation/scenarios" @{"X-Request-ID" = $RequestId}
$results += Invoke-Check "Start simulation" "POST" "$Core/api/v1/simulation/start" $AdminHeaders @{
    scenario_id = $ScenarioId
    mode = "TIMELINE"
    reset_existing = $true
    auto_advance = $false
}
$results += Invoke-Check "Get simulation status" "GET" "$Core/api/v1/simulation/status" @{"X-Request-ID" = $RequestId}
$results += Invoke-Check "Pause simulation" "POST" "$Core/api/v1/simulation/pause" $AdminHeaders
$results += Invoke-Check "Resume simulation" "POST" "$Core/api/v1/simulation/resume" $AdminHeaders
$results += Invoke-Check "Inject judge event" "POST" "$Core/api/v1/simulation/event" $AdminHeaders @{
    event_id = "SMOKE-EVT-$([guid]::NewGuid().ToString("N").Substring(0, 8).ToUpper())"
    event_type = "ENGINEER_ON_LEAVE"
    scenario_id = $ScenarioId
    payload = @{
        specialist_id = "SPEC-PRIYA"
        reason = "Smoke test leave event"
    }
    idempotency_key = "SMOKE-IDEM-$([guid]::NewGuid().ToString("N").Substring(0, 8).ToUpper())"
}
$results += Invoke-Check "Advance timeline" "POST" "$Core/api/v1/simulation/advance" $AdminHeaders
$results += Invoke-Check "Reset simulation" "POST" "$Core/api/v1/simulation/reset" $AdminHeaders @{
    scenario_id = $ScenarioId
}

$passed = @($results | Where-Object { $_ -eq $true }).Count
$failed = @($results | Where-Object { $_ -ne $true }).Count
Write-Host ""
Write-Host "Smoke summary: PASS=$passed FAIL=$failed"

if ($failed -gt 0) { exit 1 }
exit 0
