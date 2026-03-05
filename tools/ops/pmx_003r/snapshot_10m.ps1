param(
  [string]$Stamp = "",
  [string]$Root = "C:\projects\NEXT-TRADE",
  [string]$OutDir = "C:\projects\NEXT-TRADE\evidence\pmx003r_auto"
)

$ErrorActionPreference = "Stop"
$ts = Get-Date -Format "yyyyMMdd_HHmmss"
$hostName = $env:COMPUTERNAME

# stamp auto-detection from latest RUN_START
if ([string]::IsNullOrWhiteSpace($Stamp)) {
  $ev = Join-Path $Root "logs\runtime\profitmax_v1_events.jsonl"
  if (Test-Path $ev) {
    $lastRunStart = Get-Content $ev -Tail 5000 | Select-String -Pattern '"event_type"\s*:\s*"RUN_START"' | Select-Object -Last 1
    if ($lastRunStart) {
      try {
        $obj = $lastRunStart.Line | ConvertFrom-Json
        $Stamp = [string]$obj.stamp
      } catch { }
    }
  }
}
if ([string]::IsNullOrWhiteSpace($Stamp)) { $Stamp = "UNKNOWN_STAMP" }

$dir = Join-Path $OutDir $Stamp
New-Item -ItemType Directory -Force -Path $dir | Out-Null

# API health/account (continue on error)
$apiHealth = ""
$acct = ""
try { $apiHealth = (Invoke-RestMethod "http://127.0.0.1:8100/api/v1/ops/health" -TimeoutSec 3) | ConvertTo-Json -Compress } catch { $apiHealth = "ERR:" + $_.Exception.Message }
try { $acct = (Invoke-RestMethod "http://127.0.0.1:8100/api/investor/account" -TimeoutSec 3) | ConvertTo-Json -Compress } catch { $acct = "ERR:" + $_.Exception.Message }

# Port status
$port = (netstat -ano | findstr ":8100") -join "`n"

# Recent events tail(200)
$evPath = Join-Path $Root "logs\runtime\profitmax_v1_events.jsonl"
$tail = ""
if (Test-Path $evPath) { $tail = (Get-Content $evPath -Tail 200) -join "`n" }

# Save snapshot
$out = Join-Path $dir ("snap_" + $ts + ".txt")
@"
STAMP=$Stamp
TS=$ts
HOST=$hostName

API_HEALTH=$apiHealth
ACCOUNT=$acct

NETSTAT_8100=
$port

EVENTS_TAIL_200=
$tail
"@ | Out-File -Encoding utf8 $out

Write-Host "OK SNAPSHOT => $out"

