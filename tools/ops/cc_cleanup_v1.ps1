[CmdletBinding(SupportsShouldProcess = $true)]
param(
  [string]$ProjectRoot = "C:\projects\NEXT-TRADE",
  [string]$BackupRoot = "C:\backup",
  [string]$ContractBase = "http://127.0.0.1:8100",
  [switch]$SkipBackup,
  [switch]$KeepOpsWeb
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function New-DirIfMissing([string]$Path) {
  if (-not (Test-Path $Path)) {
    New-Item -ItemType Directory -Path $Path -Force | Out-Null
  }
}

function Write-Info([string]$Message) {
  Write-Host "[cc-cleanup] $Message"
}

function Set-ContractBaseEnv([string]$UiRoot, [string]$BaseUrl) {
  $envFile = Join-Path $UiRoot ".env.local"
  $line = "NEXT_PUBLIC_CONTRACT_BASE=$BaseUrl"

  if (-not (Test-Path $envFile)) {
    if ($PSCmdlet.ShouldProcess($envFile, "Create .env.local with contract base")) {
      Set-Content -Path $envFile -Value $line -Encoding utf8
    }
    return
  }

  $lines = Get-Content -Path $envFile -Encoding utf8
  $updated = $false
  for ($i = 0; $i -lt $lines.Count; $i++) {
    if ($lines[$i] -match "^NEXT_PUBLIC_CONTRACT_BASE=") {
      $lines[$i] = $line
      $updated = $true
      break
    }
  }
  if (-not $updated) {
    $lines += $line
  }

  if ($PSCmdlet.ShouldProcess($envFile, "Update NEXT_PUBLIC_CONTRACT_BASE")) {
    Set-Content -Path $envFile -Value $lines -Encoding utf8
  }
}

function Move-ToArchive([string]$SourcePath, [string]$ArchiveDir) {
  if (-not (Test-Path $SourcePath)) {
    return
  }
  New-DirIfMissing $ArchiveDir
  $target = Join-Path $ArchiveDir (Split-Path $SourcePath -Leaf)
  if ($PSCmdlet.ShouldProcess($SourcePath, "Move to $target")) {
    Move-Item -Path $SourcePath -Destination $target -Force
  }
}

$stamp = Get-Date -Format "yyyyMMdd_HHmmss"
Write-Info "START stamp=$stamp"

if (-not (Test-Path $ProjectRoot)) {
  throw "Project root not found: $ProjectRoot"
}

if (-not $SkipBackup) {
  New-DirIfMissing $BackupRoot
  $zipPath = Join-Path $BackupRoot ("NEXT-TRADE_FULL_{0}.zip" -f $stamp)
  if ($PSCmdlet.ShouldProcess($ProjectRoot, "Backup project to $zipPath")) {
    Compress-Archive -Path (Join-Path $ProjectRoot "*") -DestinationPath $zipPath -Force
  }
  Write-Info "BACKUP=$zipPath"
}

# Identify active command-center UI repo.
$uiCandidates = @(
  "C:\projects\NEXT-TRADE-UI",
  "C:\projects\evergreen-ops-ui"
)
$activeUi = $null
foreach ($candidate in $uiCandidates) {
  if (Test-Path (Join-Path $candidate "src\app\command-center\page.tsx")) {
    $activeUi = $candidate
    break
  }
}

if ($null -eq $activeUi) {
  Write-Info "WARN no command-center UI repo detected from candidates"
} else {
  Write-Info "ACTIVE_UI=$activeUi"
  Set-ContractBaseEnv -UiRoot $activeUi -BaseUrl $ContractBase
}

# Move non-active UI repos to archive.
$uiArchive = Join-Path $ProjectRoot "archive_legacy\ui"
foreach ($candidate in $uiCandidates) {
  if (-not (Test-Path $candidate)) {
    continue
  }
  if ($candidate -eq $activeUi) {
    continue
  }
  Move-ToArchive -SourcePath $candidate -ArchiveDir $uiArchive
}

# Move ops_web to backend archive (operationally excluded).
if (-not $KeepOpsWeb) {
  $opsWebPath = Join-Path $ProjectRoot "ops_web"
  $backendArchive = Join-Path $ProjectRoot "archive_legacy\backend"
  Move-ToArchive -SourcePath $opsWebPath -ArchiveDir $backendArchive
}

# Keep a minimal operations set in tools/ops; move others to archive_legacy.
$opsDir = Join-Path $ProjectRoot "tools\ops"
$opsArchive = Join-Path $ProjectRoot "archive_legacy\ops_scripts"
$keepOpsFiles = @(
  "verify_runtime_mix_v2.ps1",
  "runtime_self_report.py",
  "verify_profitmax_v1.ps1",
  "pmx_obs_auto_collect.ps1",
  "cc_cleanup_v1.ps1"
)

if (Test-Path $opsDir) {
  $candidates = Get-ChildItem -Path $opsDir -File | Where-Object { $keepOpsFiles -notcontains $_.Name }
  foreach ($item in $candidates) {
    Move-ToArchive -SourcePath $item.FullName -ArchiveDir $opsArchive
  }
}

Write-Info "DONE"
