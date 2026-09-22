#requires -Version 5.1
<#
  Stops the Daguerre's Hoard instance listening on -Port (default 8814).

  The process is found by the port it listens on and confirmed through
  /api/health before anything is stopped, so other Python programs are
  never touched. A venv's python.exe on Windows is a small launcher that
  starts the real interpreter as a child: the listening child is stopped,
  and the launcher too when it is this repository's .venv python.
  ASCII only: Windows PowerShell 5.1 reads BOM-less scripts as ANSI.
#>
param(
    [int]$Port = 8814
)

# Loopback health checks must not go through a system proxy (PowerShell 5.1).
try { [System.Net.WebRequest]::DefaultWebProxy = New-Object System.Net.WebProxy } catch { }

$RepoRoot = Split-Path -Parent $PSScriptRoot
$VenvPython = Join-Path $RepoRoot ".venv\Scripts\python.exe"
$Url = "http://127.0.0.1:$Port"

try {
    $health = Invoke-RestMethod -Uri "$Url/api/health" -TimeoutSec 3 -UseBasicParsing
} catch {
    Write-Host "Daguerre's Hoard is not running on port $Port."
    exit 0
}
if ($health.service -ne "daguerres-hoard") {
    Write-Host "Port $Port is used by another service ($($health.service)); nothing was stopped."
    exit 1
}

$pids = @()
try {
    $pids = @(Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction Stop |
        Select-Object -ExpandProperty OwningProcess -Unique)
} catch {
    foreach ($line in (netstat -ano | Select-String -Pattern ":$Port\s+\S+\s+LISTENING")) {
        $pids += [int](($line.ToString().Trim() -split "\s+")[-1])
    }
    $pids = @($pids | Select-Object -Unique)
}

if (-not $pids) {
    Write-Host "Could not find the process listening on port $Port."
    exit 1
}

foreach ($procId in $pids) {
    $p = Get-CimInstance Win32_Process -Filter "ProcessId = $procId" -ErrorAction SilentlyContinue
    $parent = $null
    if ($p) {
        $parent = Get-CimInstance Win32_Process -Filter "ProcessId = $($p.ParentProcessId)" -ErrorAction SilentlyContinue
    }
    Write-Host "Stopping Daguerre's Hoard (PID $procId)..."
    Stop-Process -Id $procId -Force -ErrorAction SilentlyContinue
    if ($parent -and $parent.ExecutablePath -and ($parent.ExecutablePath -ieq $VenvPython)) {
        Stop-Process -Id $parent.ProcessId -Force -ErrorAction SilentlyContinue
    }
}
Write-Host "Stopped."
exit 0
