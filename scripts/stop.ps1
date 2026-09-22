#requires -Version 5
<#
  Stops any running Argus's Hoard process (matched by its venv python path
  and the argus_hoard module argument), without touching other Python
  processes on the machine.
#>
$RepoRoot = Split-Path -Parent $PSScriptRoot
$VenvPython = Join-Path $RepoRoot ".venv\Scripts\python.exe"

$procs = Get-CimInstance Win32_Process -Filter "Name = 'python.exe'" | Where-Object {
    $_.ExecutablePath -eq $VenvPython -and $_.CommandLine -like "*argus_hoard*"
}

if (-not $procs) {
    Write-Host "Argus's Hoard is not running."
    exit 0
}

foreach ($p in $procs) {
    Write-Host "Stopping PID $($p.ProcessId)..."
    Stop-Process -Id $p.ProcessId -Force
}
