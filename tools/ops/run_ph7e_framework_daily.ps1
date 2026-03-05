$ErrorActionPreference = "Stop"

$repo = "C:\projects\NEXT-TRADE"
$runner = Join-Path $repo "tools\ops\run_algorithm_framework.ps1"
$logDir = Join-Path $repo "evidence\analysis\logs"
New-Item -ItemType Directory -Force -Path $logDir | Out-Null

$log = Join-Path $logDir ("ph7e_framework_" + (Get-Date -Format "yyyyMMdd") + ".log")

Set-Location $repo
powershell -NoProfile -ExecutionPolicy Bypass -File $runner 2>&1 | Tee-Object -FilePath $log -Append

