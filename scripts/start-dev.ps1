taskkill /F /IM node.exe 2>$null
Set-Location C:\projects\NEXT-TRADE-UI
if (Test-Path .next) { Remove-Item .next -Recurse -Force }
$env:Path = "C:\Program Files\nodejs;" + $env:Path
& "C:\Program Files\nodejs\npm.cmd" run dev -- -p 3001
