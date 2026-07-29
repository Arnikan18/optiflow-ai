param(
    [ValidateSet("unit", "integration", "all")]
    [string]$Mode = "all"
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

function Resolve-Python {
    param([string]$Directory)
    $candidates = @()
    if ($env:PYTHON) { $candidates += $env:PYTHON }
    $candidates += Join-Path $Directory ".venv\Scripts\python.exe"
    $candidates += Join-Path $Directory ".venv\bin\python"
    $candidates += Join-Path $RepoRoot ".venv\Scripts\python.exe"
    $candidates += Join-Path $RepoRoot ".venv\bin\python"
    $candidates += Join-Path $RepoRoot "tools\crm-service\.venv\Scripts\python.exe"
    $candidates += Join-Path $RepoRoot "tools\crm-service\.venv\bin\python"
    $candidates += Join-Path $RepoRoot "tools\incident-service\.venv\Scripts\python.exe"
    $candidates += Join-Path $RepoRoot "tools\incident-service\.venv\bin\python"
    $candidates += Join-Path $RepoRoot "tools\workforce-service\.venv\Scripts\python.exe"
    $candidates += Join-Path $RepoRoot "tools\workforce-service\.venv\bin\python"
    $candidates += Join-Path $RepoRoot "tools\communication-service\.venv\Scripts\python.exe"
    $candidates += Join-Path $RepoRoot "tools\communication-service\.venv\bin\python"
    foreach ($candidate in $candidates) {
        if ($candidate -and (Test-Path $candidate)) {
            return (Resolve-Path $candidate).Path
        }
    }
    $pythonCommand = Get-Command python -ErrorAction SilentlyContinue
    if ($pythonCommand) { return $pythonCommand.Source }
    throw "Python is not available for $Directory."
}

function Invoke-TestSuite {
    param(
        [string]$Name,
        [string]$Directory,
        [string]$TestPath
    )

    $suitePath = Join-Path $Directory $TestPath
    if (-not (Test-Path $suitePath)) {
        return [pscustomobject]@{ Name = $Name; Status = "FAILED"; Duration = 0.0; Message = "Missing required test path: $suitePath" }
    }

    $python = Resolve-Python $Directory
    $safeName = $Name -replace '[^A-Za-z0-9_-]', '-'
    $tempName = ".test-tmp-$safeName-$PID-$(Get-Date -Format yyyyMMddHHmmssfff)"
    $oldPythonPath = $env:PYTHONPATH
    $oldDatabaseUrl = $env:DATABASE_URL
    $sharedPath = Join-Path $RepoRoot "shared\python"
    $env:PYTHONPATH = if ($oldPythonPath) { "$sharedPath;$oldPythonPath" } else { $sharedPath }
    if ($Name -like "*-service") {
        $tempDbPath = Join-Path ([System.IO.Path]::GetTempPath()) "optiflow-$safeName-$PID.db"
        $env:DATABASE_URL = "sqlite:///$($tempDbPath.Replace('\', '/'))"
    }

    $watch = [System.Diagnostics.Stopwatch]::StartNew()
    Push-Location $Directory
    try {
        & $python -m pytest $TestPath -q -p no:cacheprovider --basetemp=$tempName 2>&1 | ForEach-Object { Write-Host $_ }
        $exitCode = $LASTEXITCODE
    } finally {
        Pop-Location
        $env:PYTHONPATH = $oldPythonPath
        $env:DATABASE_URL = $oldDatabaseUrl
    }
    $watch.Stop()

    if ($exitCode -eq 0) {
        return [pscustomobject]@{ Name = $Name; Status = "PASSED"; Duration = $watch.Elapsed.TotalSeconds; Message = "" }
    }
    return [pscustomobject]@{ Name = $Name; Status = "FAILED"; Duration = $watch.Elapsed.TotalSeconds; Message = "pytest exited with $exitCode" }
}

$suites = @()
if ($Mode -in @("unit", "all")) {
    $suites += @{ Name = "crm-service"; Directory = Join-Path $RepoRoot "tools\crm-service"; TestPath = "tests" }
    $suites += @{ Name = "incident-service"; Directory = Join-Path $RepoRoot "tools\incident-service"; TestPath = "tests" }
    $suites += @{ Name = "workforce-service"; Directory = Join-Path $RepoRoot "tools\workforce-service"; TestPath = "tests" }
    $suites += @{ Name = "communication-service"; Directory = Join-Path $RepoRoot "tools\communication-service"; TestPath = "tests" }
    $suites += @{ Name = "core-api"; Directory = Join-Path $RepoRoot "core-api"; TestPath = "tests\unit" }
}
if ($Mode -in @("integration", "all")) {
    $suites += @{ Name = "integration-tests"; Directory = $RepoRoot; TestPath = "integration-tests" }
}

$started = Get-Date
$results = @()
Write-Host "Running OptiFlow backend tests. Mode: $Mode"
foreach ($suite in $suites) {
    Write-Host ""
    Write-Host "==> $($suite.Name)"
    $results += Invoke-TestSuite -Name $suite.Name -Directory $suite.Directory -TestPath $suite.TestPath
}

$duration = ((Get-Date) - $started).TotalSeconds
$passed = @($results | Where-Object { $_.Status -eq "PASSED" })
$failed = @($results | Where-Object { $_.Status -eq "FAILED" })
$skipped = @($results | Where-Object { $_.Status -eq "SKIPPED" })

Write-Host ""
Write-Host "Test summary"
foreach ($result in $results) {
    $line = "{0,-24} {1,-8} {2,8:N2}s" -f $result.Name, $result.Status, $result.Duration
    if ($result.Message) { $line = "$line  $($result.Message)" }
    Write-Host $line
}
Write-Host "Passed: $($passed.Count)  Failed: $($failed.Count)  Skipped: $($skipped.Count)  Duration: $([math]::Round($duration, 2))s"

if ($failed.Count -gt 0) { exit 1 }
exit 0
