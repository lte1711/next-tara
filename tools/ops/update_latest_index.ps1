param(
  [string]$ProjectRoot = "C:\projects\NEXT-TRADE",
  [string]$EvidenceDir = "C:\projects\NEXT-TRADE\evidence\pmx",
  [string]$BackupDir = "C:\backup",
  [string]$UiRoot = "C:\projects\NEXT-TRADE-UI"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function LatestFile([string]$Pattern) {
  $file = Get-ChildItem -Path $Pattern -ErrorAction SilentlyContinue |
    Sort-Object LastWriteTime -Descending |
    Select-Object -First 1
  return $file
}

function SafePath($file) {
  if ($null -eq $file) { return "" }
  if ($file.PSObject.Properties["FullName"]) { return [string]$file.FullName }
  return ""
}

New-Item -ItemType Directory -Force -Path $EvidenceDir | Out-Null
$latestPath = Join-Path $EvidenceDir "_LATEST.txt"

$latestBackup = LatestFile (Join-Path $BackupDir "NEXT-TRADE_FULL_SAFE_*.zip")
$latestStart = LatestFile (Join-Path $EvidenceDir "session_start_*.txt")
$latestMid = LatestFile (Join-Path $EvidenceDir "session_mid_15m_*.txt")
$latestEnd = LatestFile (Join-Path $EvidenceDir "session_end_60m_*.txt")
$latestMix = LatestFile (Join-Path $EvidenceDir "runtime_mix_gate_*.txt")
$latestVerdict = LatestFile (Join-Path $EvidenceDir "runtime_mix_verdict_*.txt")

$contractBase = "<MISSING>"
$envLocal = Join-Path $UiRoot ".env.local"
if (Test-Path $envLocal) {
  $line = Get-Content $envLocal | Where-Object { $_ -match "^NEXT_PUBLIC_CONTRACT_BASE=" } | Select-Object -First 1
  if ($line) {
    $contractBase = ($line -split "=", 2)[1]
  }
}

$lines = @()
$lines += "UPDATED_AT_UTC=$((Get-Date).ToUniversalTime().ToString('o'))"
$lines += "PROJECT_ROOT=$ProjectRoot"
$lines += "EVIDENCE_DIR=$EvidenceDir"
$lines += "BACKUP_LATEST=$(SafePath $latestBackup)"
$lines += "SESSION_START_LATEST=$(SafePath $latestStart)"
$lines += "SESSION_MID_LATEST=$(SafePath $latestMid)"
$lines += "SESSION_END_LATEST=$(SafePath $latestEnd)"
$lines += "RUNTIME_MIX_GATE_LATEST=$(SafePath $latestMix)"
$lines += "RUNTIME_MIX_VERDICT_LATEST=$(SafePath $latestVerdict)"
$lines += "CONTRACT_BASE=$contractBase"

Set-Content -Path $latestPath -Value $lines -Encoding utf8
Write-Host "LATEST_INDEX=$latestPath"
