#requires -Version 5
<#
  Starts Argus's Hoard: creates/uses .venv, installs the pinned lock file
  the first time, builds the frontend if dist/ is missing, then runs the
  app bound to 127.0.0.1. Safe to run repeatedly.
#>
param(
    [int]$Port = 8814,
    [switch]$Demo
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $RepoRoot

$VenvPython = Join-Path $RepoRoot ".venv\Scripts\python.exe"

if (-not (Test-Path $VenvPython)) {
    Write-Host "Creating virtual environment..."
    python -m venv .venv
    & $VenvPython -m pip install --upgrade pip
    & $VenvPython -m pip install -r requirements-lock.txt
    & $VenvPython -m pip install --no-deps -e .
}

$FrontendDist = Join-Path $RepoRoot "frontend\dist"
if (-not (Test-Path $FrontendDist)) {
    Write-Host "Building frontend..."
    Push-Location (Join-Path $RepoRoot "frontend")
    npm ci
    npm run build
    Pop-Location
}

$AppArgs = @("-m", "argus_hoard", "--port", $Port)
if ($Demo) { $AppArgs += "--demo" }
& $VenvPython @AppArgs
