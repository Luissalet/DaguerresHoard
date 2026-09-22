#requires -Version 5.1
<#
  Starts Daguerre's Hoard in the background and opens it in the browser.

  First run: creates .venv with Python 3.11+ (C:\Python313 preferred),
  installs requirements-lock.txt, and builds the frontend if
  frontend\dist is missing. The lock is reinstalled whenever it changes.
  The app always runs with the repository root as working directory (the
  assistant reads faustus-plugin.json from there) and this script waits
  until /api/health answers before returning.

  Usage: scripts\start.ps1 [-Port 8814] [-Demo] [-NoBrowser]
  ASCII only: Windows PowerShell 5.1 reads BOM-less scripts as ANSI.
#>
param(
    [int]$Port = 8814,
    [switch]$Demo,
    [switch]$NoBrowser
)

$ErrorActionPreference = "Stop"
# Loopback health checks must not go through a system proxy (PowerShell 5.1).
try { [System.Net.WebRequest]::DefaultWebProxy = New-Object System.Net.WebProxy } catch { }

$RepoRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $RepoRoot

$Url = "http://127.0.0.1:$Port"
$VenvPython = Join-Path $RepoRoot ".venv\Scripts\python.exe"
$LockFile = Join-Path $RepoRoot "requirements-lock.txt"
$LockStamp = Join-Path $RepoRoot ".venv\daguerre-lock.sha256"

function Fail([string]$Message) {
    Write-Host ""
    Write-Host "ERROR: $Message" -ForegroundColor Red
    exit 1
}

function Test-DaguerreHealth {
    try {
        $r = Invoke-RestMethod -Uri "$Url/api/health" -TimeoutSec 2 -UseBasicParsing
        return ($r.service -eq "daguerres-hoard")
    } catch {
        return $false
    }
}

function Test-PortBusy {
    try {
        $c = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction Stop
        return [bool]$c
    } catch {
        return [bool](netstat -ano | Select-String -Pattern ":$Port\s+\S+\s+LISTENING")
    }
}

function Find-BasePython {
    # Returns @(exe, extra-args) for a Python >= 3.11.
    $candidates = @()
    if (Test-Path "C:\Python313\python.exe") { $candidates += ,@("C:\Python313\python.exe") }
    if (Get-Command py -ErrorAction SilentlyContinue) {
        $candidates += ,@("py", "-3.13")
        $candidates += ,@("py", "-3")
    }
    if (Get-Command python -ErrorAction SilentlyContinue) { $candidates += ,@("python") }
    foreach ($c in $candidates) {
        $exe = $c[0]
        $extra = @($c | Select-Object -Skip 1)
        try {
            $ver = & $exe @extra -c "import sys; print('%d.%d' % sys.version_info[:2])" 2>$null
            if ($LASTEXITCODE -eq 0 -and $ver -and ([version]$ver -ge [version]"3.11")) {
                return ,$c
            }
        } catch { }
    }
    return $null
}

if (Test-DaguerreHealth) {
    Write-Host "Daguerre's Hoard is already running at $Url"
    if (-not $NoBrowser) { Start-Process $Url }
    exit 0
}
if (Test-PortBusy) {
    Fail "port $Port is already used by another program. Start with -Port <other> or close that program."
}

# 1) virtual environment ------------------------------------------------
if (-not (Test-Path $VenvPython)) {
    $base = Find-BasePython
    if (-not $base) { Fail "Python 3.11 or newer was not found. Install Python 3.13 (C:\Python313) and retry." }
    Write-Host "Creating the virtual environment with $($base -join ' ')..."
    $exe = $base[0]
    $extra = @($base | Select-Object -Skip 1)
    & $exe @extra -m venv (Join-Path $RepoRoot ".venv")
    if ($LASTEXITCODE -ne 0 -or -not (Test-Path $VenvPython)) { Fail "could not create .venv" }
}

# 2) dependencies (re-run whenever the lock file changes) ----------------
$lockHash = (Get-FileHash -LiteralPath $LockFile -Algorithm SHA256).Hash
$installed = if (Test-Path $LockStamp) { (Get-Content -LiteralPath $LockStamp -Raw).Trim() } else { "" }
if ($installed -ne $lockHash) {
    Write-Host "Installing pinned dependencies (first run takes a few minutes)..."
    & $VenvPython -m pip install --disable-pip-version-check --upgrade pip
    & $VenvPython -m pip install --disable-pip-version-check -r $LockFile
    if ($LASTEXITCODE -ne 0) { Fail "pip install -r requirements-lock.txt failed (see the output above)" }
    Set-Content -LiteralPath $LockStamp -Value $lockHash -Encoding ASCII
}

# 3) frontend ------------------------------------------------------------
if (-not (Test-Path (Join-Path $RepoRoot "frontend\dist\index.html"))) {
    if (-not (Get-Command npm -ErrorAction SilentlyContinue)) {
        Fail "the interface is not built and npm was not found. Install Node.js 22 and retry."
    }
    Write-Host "Building the interface..."
    Push-Location (Join-Path $RepoRoot "frontend")
    try {
        # npm.cmd, not npm: the npm.ps1 shim misreads "& npm ci" as "pm ci".
        & npm.cmd ci --no-audit --no-fund
        if ($LASTEXITCODE -ne 0) { Fail "npm ci failed" }
        & npm.cmd run build
        if ($LASTEXITCODE -ne 0) { Fail "npm run build failed" }
    } finally {
        Pop-Location
    }
}

# 4) start in the background and wait for /api/health -------------------
$dataName = if ($Demo) { "data-demo" } else { "data" }
$logDir = Join-Path $RepoRoot "$dataName\logs"
New-Item -ItemType Directory -Force -Path $logDir | Out-Null
$appArgs = @("-m", "daguerre_hoard", "--no-browser", "--port", "$Port")
if ($Demo) { $appArgs += "--demo" }

Write-Host "Starting Daguerre's Hoard on $Url ..."
$proc = Start-Process -FilePath $VenvPython -ArgumentList $appArgs -WorkingDirectory $RepoRoot `
    -WindowStyle Hidden -PassThru `
    -RedirectStandardOutput (Join-Path $logDir "stdout.log") `
    -RedirectStandardError (Join-Path $logDir "stderr.log")

$deadline = (Get-Date).AddSeconds(90)
while ((Get-Date) -lt $deadline) {
    if (Test-DaguerreHealth) {
        Write-Host "Daguerre's Hoard is running at $Url (stop it with scripts\stop.ps1)."
        if (-not $NoBrowser) { Start-Process $Url }
        exit 0
    }
    if ($proc.HasExited) {
        Write-Host (Get-Content -LiteralPath (Join-Path $logDir "stderr.log") -Tail 20 -ErrorAction SilentlyContinue | Out-String)
        Fail "the app exited during start-up (log: $logDir\stderr.log)"
    }
    Start-Sleep -Milliseconds 500
}
Fail "the app did not answer $Url/api/health within 90 seconds (log: $logDir)"
