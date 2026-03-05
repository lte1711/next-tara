$ErrorActionPreference = "Stop"

function Invoke-NextTradeBackup {
  param(
    [Parameter(Mandatory=$true)]
    [ValidateSet("PH7B_FREEZE","PH7C_FREEZE","PH7C_DAY3","PH7C_DAY7","PH7D_IMPLANT")]
    [string]$Stage
  )

  $src = "C:\projects\NEXT-TRADE"
  $root = "C:\backup\NEXT-TRADE"
  $ts = Get-Date -Format "yyyyMMdd_HHmmss"

  $stageDir = Join-Path $root $Stage
  $zipPath = Join-Path $stageDir ("NEXT-TRADE_" + $Stage + "_" + $ts + ".zip")
  $shaPath = Join-Path $stageDir ("sha256_" + $Stage + "_" + $ts + ".txt")
  $manifestPath = Join-Path $stageDir ("BACKUP_MANIFEST_" + $Stage + "_" + $ts + ".txt")
  $tmpCopy = Join-Path $stageDir ("_snapshot_" + $ts)

  @("PH7B_FREEZE","PH7C_FREEZE","PH7C_DAY3","PH7C_DAY7","PH7D_IMPLANT") | ForEach-Object {
    New-Item -ItemType Directory -Force -Path (Join-Path $root $_) | Out-Null
  }
  New-Item -ItemType Directory -Force -Path $stageDir | Out-Null

  $excludeDirs = @("venv","node_modules",".next","__pycache__",".git")
  $excludeArgs = @()
  foreach($d in $excludeDirs){ $excludeArgs += @("/XD", (Join-Path $src $d)) }

  robocopy $src $tmpCopy /MIR /R:1 /W:1 /NFL /NDL /NP @excludeArgs | Out-Null
  $rc = $LASTEXITCODE
  if($rc -gt 7){ throw "ROBOCOPY_FAILED exitcode=$rc" }

  if(Test-Path $zipPath){ Remove-Item $zipPath -Force }
  Compress-Archive -Path $tmpCopy -DestinationPath $zipPath -Force

  if(!(Test-Path $zipPath)){ throw "ZIP_NOT_CREATED path=$zipPath" }
  $zipItem = Get-Item $zipPath
  if($zipItem.Length -le 0){ throw "ZIP_EMPTY size=0 path=$zipPath" }

  $hash = (Get-FileHash $zipPath -Algorithm SHA256).Hash
  "ZIP_PATH=$zipPath`nSHA256=$hash`nZIP_SIZE_BYTES=$($zipItem.Length)" | Out-File $shaPath -Encoding utf8

  $requiredExact = @(
    "evidence\evergreen\perf\PH7C_DESIGN_FREEZE_20260304.txt",
    "evidence\evergreen\perf\PH7C_ALERT_POLICY_20260304.txt",
    "docs\PH7D_SAFE_IMPLANT_RUNBOOK.md"
  )
  $requiredPattern = @("evidence\evergreen\perf\ph7c_daily_regression_*.txt")

  "STAMP=$ts" | Out-File $manifestPath -Encoding utf8
  "STAGE=$Stage" | Out-File $manifestPath -Append -Encoding utf8
  "SOURCE=$src" | Out-File $manifestPath -Append -Encoding utf8
  "ZIP_PATH=$zipPath" | Out-File $manifestPath -Append -Encoding utf8
  "ZIP_SIZE_BYTES=$($zipItem.Length)" | Out-File $manifestPath -Append -Encoding utf8
  "SHA256=$hash" | Out-File $manifestPath -Append -Encoding utf8
  "ROBOCOPY_EXITCODE=$rc" | Out-File $manifestPath -Append -Encoding utf8

  "`n[REQUIRED_FILES_EXACT]" | Out-File $manifestPath -Append -Encoding utf8
  $exactLines = foreach($rel in $requiredExact){
    $p = Join-Path $src $rel
    if(Test-Path $p){
      $it = Get-Item $p
      "OK  $rel  size=$($it.Length)  mtime=$($it.LastWriteTime.ToString('yyyy-MM-dd HH:mm:ss'))"
    } else {
      "MISS $rel"
    }
  }
  $exactLines | Out-File $manifestPath -Append -Encoding utf8

  "`n[REQUIRED_FILES_PATTERN]" | Out-File $manifestPath -Append -Encoding utf8
  $patternLines = foreach($pat in $requiredPattern){
    $dir = Split-Path $pat
    $leaf = Split-Path $pat -Leaf
    $fullDir = Join-Path $src $dir
    $found = @()
    if(Test-Path $fullDir){
      $found = Get-ChildItem -Path $fullDir -File -Filter $leaf | Sort-Object LastWriteTime -Descending
    }
    if($found.Count -gt 0){
      $top = $found[0]
      "OK  $pat  latest=$($top.Name)  size=$($top.Length)  mtime=$($top.LastWriteTime.ToString('yyyy-MM-dd HH:mm:ss'))"
    } else {
      "MISS $pat"
    }
  }
  $patternLines | Out-File $manifestPath -Append -Encoding utf8

  Remove-Item $tmpCopy -Recurse -Force

  [PSCustomObject]@{
    BACKUP_DONE = "YES"
    BACKUP_STAGE = $Stage
    ZIP_PATH = $zipPath
    ZIP_SIZE_BYTES = $zipItem.Length
    SHA256 = $hash
    SHA256_LOG = $shaPath
    MANIFEST = $manifestPath
  }
}
