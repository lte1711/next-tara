# ops_checkpoint_sync.ps1 (operational layer only)
param(
  [int]$EnginePid = 0,
  [string]$EnginePidPath = "C:\projects\NEXT-TRADE\logs\runtime\engine.pid",
  [string]$CheckpointPath = "C:\projects\NEXT-TRADE\logs\runtime\checkpoint_log.txt"
)

$ErrorActionPreference = "Stop"

if ($EnginePid -le 0) {
  $procs = Get-CimInstance Win32_Process |
    Where-Object { $_.Name -eq "python.exe" -and $_.CommandLine -match "profitmax_v1_runner\.py" }
  if (-not $procs) { exit 2 }

  $child = $procs | Where-Object { ($procs.ProcessId) -contains $_.ParentProcessId } | Select-Object -First 1
  if (-not $child) {
    $child = $procs | Sort-Object ProcessId -Descending | Select-Object -First 1
  }
  if (-not $child) { exit 2 }

  $EnginePid = [int]$child.ProcessId
}

$dir1 = Split-Path -Parent $EnginePidPath
$dir2 = Split-Path -Parent $CheckpointPath
if ($dir1) { New-Item -ItemType Directory -Force -Path $dir1 | Out-Null }
if ($dir2) { New-Item -ItemType Directory -Force -Path $dir2 | Out-Null }

$now = Get-Date -Format "yyyy-MM-dd HH:mm:ss K"
Set-Content -Path $EnginePidPath -Value "$EnginePid" -Encoding ascii
Add-Content -Path $CheckpointPath -Value "TASK_CHECKPOINT_SYNC pid=$EnginePid ts=$now" -Encoding utf8

exit 0
